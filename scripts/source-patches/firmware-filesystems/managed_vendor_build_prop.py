# SPDX-License-Identifier: MIT
"""Publish an unchanged OEM vendor/ODM/DLKM build.prop after checking inputs.

The OEM image identifies its own vendor implementation. Framework-generated
identity/default properties do not describe that prebuilt implementation. Product
requests and property files still have to be satisfied, or the build fails.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import tempfile


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def properties(text: str, origin: str, optional: bool = True,
               preserve_unassigned_names: bool = False) -> list[tuple[str, str, bool]]:
    result = []
    require("\0" not in text, f"NUL in {origin}")
    for number, line in enumerate(text.splitlines(), 1):
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if preserve_unassigned_names and re.fullmatch(r"[A-Za-z0-9_.-]+", line):
            # Official ODM contains an unassigned name. Fixed init LoadProperties
            # ignores lines with no '='; keep its bytes, but never treat it as an
            # effective property or let it satisfy an explicit product request.
            continue
        match = re.fullmatch(r"([A-Za-z0-9_.-]+)\s*(\?=|=)\s*(.*)", line)
        require(match is not None, f"invalid property at {origin}:{number}")
        name, assignment, value = match.groups()
        require(optional or assignment == "=", f"unresolved optional property in {origin}: {name}")
        result.append((name, value.strip(), assignment == "?="))
    return result


def group(values: list[tuple[str, str, bool]]) -> dict[str, list[tuple[str, bool]]]:
    result = {}
    for name, value, optional in values:
        result.setdefault(name, []).append((value, optional))
    return result


def resolved(values: list[tuple[str, str, bool]], origin: str) -> dict[str, str]:
    result = {}
    for name, assignments in group(values).items():
        required = {value for value, optional in assignments if not optional}
        require(len(required) <= 1, f"conflicting explicit values in {origin}: {name}")
        result[name] = next(iter(required)) if required else assignments[-1][0]
    return result


def validate(source: bytes, config: dict, prop_files: list[Path], system_prop: Path | None,
             partition: str = "vendor") -> None:
    require(partition in {"vendor", "odm", "odm_dlkm", "vendor_dlkm", "system_dlkm"}, "unsupported managed property partition")
    require(partition != "vendor" or system_prop is not None,
            "managed OEM vendor properties require actual system_build_prop")
    require(type(config.get("Debuggable", False)) is bool and not config.get("Eng"),
            f"managed OEM {partition} properties require user or userdebug")
    require(config.get("PropertySplitEnabled") is True,
            f"managed OEM {partition} properties require split partition properties")
    require(not config.get("BuildBrokenDupSysprop"), "ambiguous duplicate-property mode is unsupported")
    require(partition != "vendor" or not config.get("VendorPropertyBlacklist"),
            "a vendor property blacklist conflicts with preserving OEM bytes")
    original = resolved(properties(source.decode("utf-8"), "OEM build.prop", optional=False,
                                   preserve_unassigned_names=partition == "odm"), "OEM build.prop")
    identity = [f"ro.{partition}.build.version.release", f"ro.{partition}.build.version.sdk",
                f"ro.{partition}.build.fingerprint"]
    if partition == "vendor":
        identity.append("ro.vendor.build.security_patch")
    # The original ODM has no SPL property. Do not invent a newer framework SPL.
    for name in identity:
        require(bool(original.get(name)), f"missing OEM {partition} identity: {name}")
    requests = []
    for path in prop_files:
        requests.extend(properties(path.read_text(), str(path)))
    if partition.endswith("_dlkm"):
        # The fixed generator has no product-variable or TARGET prop-file channel
        # for this partition. Do not silently accept a caller inventing one.
        for name in (f"PRODUCT_{partition.upper()}_PROPERTIES", f"TARGET_{partition.upper()}_PROP"):
            require(not config.get(name), f"unsupported {partition} request channel: {name}")
        variables = []
    elif partition == "odm":
        variables = ["PRODUCT_ODM_PROPERTIES"]
    else:
        variables = ["PRODUCT_VENDOR_PROPERTIES", "PRODUCT_DEFAULT_PROPERTY_OVERRIDES",
                     "PRODUCT_PROPERTY_OVERRIDES"]
    for name in variables:
        values = config.get(name, [])
        require(isinstance(values, list) and all(isinstance(value, str) for value in values),
                f"invalid property list: {name}")
        for value in values:
            require("\n" not in value and "\r" not in value, f"multiline property in {name}")
        requests.extend(properties("\n".join(values), name))
    if partition == "vendor":
        # This single platform setting has a verified system/core/tombstoned consumer.
        # Both its explicit product request and its actual generated system file must
        # retain the same value. This is not a general cross-partition exemption.
        system_requests = resolved(properties("\n".join(config.get("PRODUCT_SYSTEM_PROPERTIES", [])),
                                              "PRODUCT_SYSTEM_PROPERTIES"), "system requests")
        actual_system = resolved(properties(system_prop.read_text(), str(system_prop), optional=False),
                                 str(system_prop))
    for name, assignments in group(requests).items():
        required = {value for value, optional in assignments if not optional}
        require(len(required) <= 1, f"conflicting explicit {partition} values: {name}")
        if not required and name in original:
            # A default assignment is already satisfied by the OEM's explicit value.
            continue
        expected = next(iter(required)) if required else assignments[-1][0]
        if partition == "vendor" and name == "tombstoned.max_tombstone_count" and name not in original:
            require(expected == "50" and system_requests.get(name) == expected
                    and actual_system.get(name) == expected,
                    "tombstoned migration requires explicit and actual system value 50")
            continue
        require(original.get(name) == expected,
                f"explicit {partition} property is not satisfied by OEM: {name}={expected!r}, "
                f"OEM={original.get(name)!r}")


def publish(source: Path, output: Path, config_paths: list[Path], prop_files: list[Path],
            system_prop: Path | None, partition: str = "vendor") -> None:
    inputs = [source, *config_paths, *prop_files]
    if system_prop is not None:
        inputs.append(system_prop)
    require(all(path.is_file() for path in inputs), "all property/config inputs must be files")
    require(not output.is_symlink(), "property output must not be a symlink")
    for path in inputs:
        require(output.resolve() != path.resolve()
                and (not output.exists() or not os.path.samefile(output, path)),
                "property output aliases a read-only input")
    config = {}
    for path in config_paths:
        values = json.loads(path.read_text())
        require(isinstance(values, dict), "product config must be an object")
        config.update(values)
    source_bytes = source.read_bytes()
    validate(source_bytes, config, prop_files, system_prop, partition)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(prefix=f".{partition}-build-prop-", dir=output.parent,
                                     delete=False) as destination:
        temporary = Path(destination.name)
        try:
            destination.write(source_bytes)
            destination.flush()
            os.fsync(destination.fileno())
            os.fchmod(destination.fileno(), 0o644)
            os.replace(temporary, output)
        finally:
            temporary.unlink(missing_ok=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--product-config", type=Path, action="append", required=True)
    parser.add_argument("--prop-file", type=Path, action="append", default=[])
    parser.add_argument("--system-prop", type=Path)
    parser.add_argument("--partition", choices=("vendor", "odm", "odm_dlkm", "vendor_dlkm", "system_dlkm"), default="vendor")
    args = parser.parse_args()
    try:
        publish(args.source, args.out, args.product_config, args.prop_file, args.system_prop, args.partition)
    except (ValueError, OSError, UnicodeError) as error:
        parser.exit(1, f"managed {args.partition} build.prop: {error}\n")


if __name__ == "__main__":
    main()
