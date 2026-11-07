#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare the four matching QCC HAL ELF inputs in this Android tree's private area."""

import argparse
import json
from pathlib import Path
import shutil
import struct
import tempfile


ELF_FILES = (
    "bin/qccsyshal_aidl-service",
    "lib64/vendor.qti.qccsyshal_aidl-V1-ndk.so",
    "lib64/vendor.qti.qccsyshal_aidl-halimpl.so",
    "lib64/libqcc_file_agent_sys.so",
)
RC_NAME = "qccsyshal_aidl-service.rc"
OLD_INTERFACE = b"    interface aidl vendor.qti.qccsyshal_aidl"
NEW_INTERFACE = b"    interface aidl vendor.qti.qccsyshal_aidl.IQccsyshal/default"


def adapt_rc(official: bytes) -> bytes:
    """Change one exact interface line; keep every other byte and OEM notice."""
    lines = official.splitlines(keepends=True)
    matches = [i for i, line in enumerate(lines)
               if line.rstrip(b"\r\n") == OLD_INTERFACE]
    if len(matches) != 1:
        raise ValueError("Official QCC interface contract changed")
    index = matches[0]
    lines[index] = lines[index].replace(OLD_INTERFACE, NEW_INTERFACE, 1)
    return b"".join(lines)


def read_regular(path: Path) -> bytes:
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected a regular input file: {path}")
    return path.read_bytes()


def collect_inputs(firmware: Path, templates: Path) -> dict[str, bytes]:
    contents = {}
    for name in ELF_FILES:
        data = read_regular(firmware / "system_ext" / name)
        if (len(data) < 64 or data[:6] != b"\x7fELF\x02\x01"
                or struct.unpack_from("<H", data, 18)[0] != 183):
            raise ValueError(f"Expected ELF64 little-endian AArch64: {name}")
        contents[name] = data
    official_rc = read_regular(
        firmware / "system_ext/etc/init/vendor.qti.qccsyshal_aidl-service.rc"
    )
    contents[RC_NAME] = adapt_rc(official_rc)
    contents["Android.bp"] = read_regular(templates / "Android.bp.in")
    return contents


def prepare(firmware: Path, templates: Path, output: Path) -> dict:
    # Only this designated private area may receive proprietary bytes. Resolving
    # first also rejects symlink escapes into the clean source or official input.
    firmware = firmware.resolve(strict=True)
    templates = templates.resolve(strict=True)
    resolved = output.resolve()
    product_suffix = ("vendor", "xiaomi", "popsicle-private", "prebuilt", "qcc-hal")
    product_output = resolved.parts[-len(product_suffix):] == product_suffix
    if (not product_output
            or resolved.is_relative_to(firmware)
            or resolved.is_relative_to(templates)
            or output.is_symlink()):
        raise ValueError("Output must be vendor/xiaomi/popsicle-private/prebuilt/qcc-hal")
    if any(parent.is_symlink() for parent in [output, *output.parents]):
        raise ValueError("Private output path must not contain symlinks")
    contents = collect_inputs(firmware, templates)
    if resolved.exists():
        actual = {
            str(p.relative_to(resolved))
            for p in resolved.rglob("*") if not p.is_dir() or p.is_symlink()
        }
        if actual != set(contents):
            raise ValueError("Existing output does not contain exactly the QCC bundle")
        for name, data in contents.items():
            if read_regular(resolved / name) != data:
                raise ValueError(f"Refusing to replace changed private output: {name}")
        status = "already-identical"
    else:
        resolved.parent.mkdir(parents=True, exist_ok=True)
        temporary = Path(tempfile.mkdtemp(prefix=".qcc-hal-", dir=resolved.parent))
        try:
            for name, data in contents.items():
                target = temporary / name
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_bytes(data)
                target.chmod(0o755 if name.startswith("bin/") else 0o644)
                if target.read_bytes() != data:
                    raise ValueError(f"Private copy differs from input: {name}")
            temporary.rename(resolved)
        finally:
            if temporary.exists():
                shutil.rmtree(temporary)
        status = "prepared"
    return {
        "status": status,
        "firmware_root": str(firmware),
        "output": str(resolved),
        "files": {name: len(data) for name, data in contents.items()},
        "rc_contract": "only the exact AIDL interface line changes; all other bytes retained",
        "scope": "private inputs only; product graph and ROM acceptance remain required",
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--firmware-root", type=Path, required=True)
    parser.add_argument("--template-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = prepare(args.firmware_root, args.template_dir, args.output)
    except (OSError, ValueError) as error:
        parser.exit(1, f"QCC preparation failed: {error}\n")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
