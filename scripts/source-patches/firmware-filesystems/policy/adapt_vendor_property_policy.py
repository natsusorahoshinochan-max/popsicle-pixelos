#!/usr/bin/env python3
"""Adapt four old public property guards to their actual current providers.

The current platform grants init_dev_config three configuration-property writes
and vendor_init the 16-KiB property write. Old versioned guards predate those
providers. Preserve every guard, its target/permission, and shared source sets;
only four guards receive private source sets excluding the proven new writer.
No allow rule is added. This changes writer restrictions and is only a candidate.
"""
import argparse
import json
from pathlib import Path
import re


CONTRACTS = {
    "apexd_select_prop": ("base_typeattr_233_202504", "init_dev_config",
                          "popsicle_config_prop_forbidden_writers"),
    "media_variant_prop": ("base_typeattr_233_202504", "init_dev_config",
                           "popsicle_config_prop_forbidden_writers"),
    "telephony_config_prop": ("base_typeattr_233_202504", "init_dev_config",
                              "popsicle_config_prop_forbidden_writers"),
    "enable_16k_pages_prop": ("base_typeattr_232_202504", "vendor_init",
                              "popsicle_16k_prop_forbidden_writers"),
}
SOURCE_SETS = (
    b"(typeattributeset base_typeattr_233_202504 (and (domain) (not (init_202504 vendor_init_202504))))\n",
    b"(typeattributeset base_typeattr_232_202504 (and (domain) (not (coredomain))))\n",
)


def sole_set(data: bytes, attribute: str, expected: bytes) -> bool:
    # CIL accepts multiple additive definitions. Inspect every occurrence of the
    # named set, including noncanonical whitespace and comments between tokens.
    # Preserve strings while removing line comments from this parsing view only.
    parsing = re.sub(rb'"(?:\\.|[^"\\])*"|;[^\n]*',
                     lambda match: b" " if match[0].startswith(b";") else match[0], data)
    definitions = re.findall(rb"\(\s*typeattributeset\s+" + re.escape(attribute.encode())
                             + rb"(?=[\s()])", parsing)
    return len(definitions) == 1 and data.splitlines(keepends=True).count(expected) == 1


def adapt(data: bytes, platform: bytes, mapping: bytes) -> tuple[bytes, int]:
    if not data.endswith(b"\n"):
        raise ValueError("OEM CIL must end with a newline before new definitions")
    lines = data.splitlines(keepends=True)
    platform_lines = platform.splitlines(keepends=True)
    if any(not sole_set(data, expression.split()[1].decode(), expression)
           for expression in SOURCE_SETS):
        raise ValueError("old public property source sets changed")
    replacements = {}
    declarations = {}
    for prop, (source, writer, private) in CONTRACTS.items():
        if private.encode() in data:
            raise ValueError("derived property source set already exists")
        allow = f"(allow {writer} {prop} (property_service (set)))\n".encode()
        mapped = f"(typeattributeset {prop}_202504 ({prop}))\n".encode()
        if platform_lines.count(allow) != 1 or not sole_set(mapping, prop + "_202504", mapped):
            raise ValueError(f"actual provider or 202504 property mapping changed: {prop}")
        guard = f"(neverallow {source} {prop}_202504 (property_service (set)))\n".encode()
        if lines.count(guard) != 1:
            raise ValueError(f"old property guard changed: {prop}")
        replacements[guard] = guard.replace(source.encode(), private.encode(), 1)
        declarations[private] = (
            f"(typeattribute {private})\n"
            f"(typeattributeset {private} (and ({source}) (not ({writer}))))\n"
        ).encode()
    # Definitions can follow their references in CIL. The old shared sets and all
    # other guards retain their bytes, including restrictions on other properties.
    result = b"".join(replacements.get(line, line) for line in lines)
    return result + b"".join(declarations.values()), len(replacements)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--platform-cil", required=True, type=Path)
    parser.add_argument("--mapping", required=True, type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result, count = adapt(args.source.read_bytes(), args.platform_cil.read_bytes(),
                          args.mapping.read_bytes())
    with args.output.open("xb") as output:
        output.write(result)
    print(json.dumps({"adapted_property_guards": count,
                      "status": "candidate; full strict and device validation pending"}))


if __name__ == "__main__":
    main()
