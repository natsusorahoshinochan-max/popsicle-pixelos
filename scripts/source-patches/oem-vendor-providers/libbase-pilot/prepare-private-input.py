#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Copy one official libbase and its mapped notices into the private input area."""

import argparse
import gzip
import html
import hashlib
import json
from pathlib import Path
import shutil
import xml.etree.ElementTree as ET


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--official-filesystems", required=True, type=Path)
    parser.add_argument("--private-root", required=True, type=Path)
    args = parser.parse_args()
    source_root = args.official_filesystems.resolve(strict=True)
    destination = args.private_root.resolve()
    firmware_version = "OS4.0.0.23.XPBCNXM"
    versions = [line.split("=", 1)[1].strip()
                for line in (source_root / "product/etc/build.prop").read_text().splitlines()
                if line.startswith("ro.product.build.version.incremental=")]
    if versions != [firmware_version]:
        parser.error("expected the " + firmware_version + " official filesystem cohort")
    required_suffix = ("vendor", "xiaomi", "popsicle-private", "prebuilt", "oem-abi")
    if destination.parts[-len(required_suffix):] != required_suffix:
        parser.error("private-root must end in vendor/xiaomi/popsicle-private/prebuilt/oem-abi")
    if source_root == destination or source_root in destination.parents:
        parser.error("official input tree must remain read-only")

    library = source_root / "vendor/lib64/libbase.so"
    notices = source_root / "vendor/etc/NOTICE.xml.gz"
    with library.open("rb") as stream:
        if stream.read(6) != b"\x7fELF\x02\x01":
            parser.error("expected an ELF64 little-endian official libbase")
    with gzip.open(notices, "rb") as stream:
        root = ET.parse(stream).getroot()
    bindings = [dict(node.attrib) for node in root.findall("file-name")
                if node.text == "/vendor/lib64/libbase.so"]
    if not bindings:
        parser.error("official NOTICE has no exact /vendor/lib64/libbase.so mapping")
    contents = {node.attrib["contentId"]: node.text or ""
                for node in root.findall("file-content")}
    text = []
    for binding in bindings:
        content_id = binding["contentId"]
        if content_id not in contents or not contents[content_id].strip():
            parser.error("official NOTICE mapping is missing its license text")
        # The official file-content CDATA still contains HTML character
        # references after XML parsing (including every newline as &#xA;).
        # Decode that remaining layer exactly once for the plain-text NOTICE.
        text.append("Official /vendor/lib64/libbase.so notice: "
                    + binding.get("lib", "") + " [" + content_id + "]\n\n"
                    + html.unescape(contents[content_id]))

    target = destination / "libbase/arm64/libbase.so"
    notice_target = destination / "libbase/NOTICE"
    source_target = destination / "libbase/SOURCE.json"
    library_bytes = library.read_bytes()
    notice_bytes = ("\n\n".join(text) + "\n").encode()
    record = {
        "schema_version": 2,
        "firmware_version": firmware_version,
        "official_library": "vendor/lib64/libbase.so",
        "official_notice": "vendor/etc/NOTICE.xml.gz",
        "sha256": {
            "official_library": hashlib.sha256(library_bytes).hexdigest(),
            "official_notice": hashlib.sha256(notices.read_bytes()).hexdigest(),
        },
        "preparer": {
            "version": 2,
            "script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "template_sha256": hashlib.sha256(Path(__file__).with_name("Android.bp").read_bytes()).hexdigest(),
        },
        "notice_bindings": bindings,
        "notice_content_ids": "Identifiers supplied by Xiaomi's NOTICE, not generated checksums.",
    }
    source_bytes = (json.dumps(record, indent=2) + "\n").encode()
    if source_target.is_file() and not source_target.is_symlink():
        existing_bytes = source_target.read_bytes()
        existing = json.loads(existing_bytes)
        if isinstance(existing, dict) and "schema_version" not in existing:
            legacy_library = Path(existing.get("official_library", ""))
            legacy_notice = Path(existing.get("official_notice", ""))
            legacy = {key: record[key] for key in ("notice_bindings", "notice_content_ids")}
            legacy.update(official_library=str(legacy_library), official_notice=str(legacy_notice))
            if (existing != legacy or not legacy_library.is_absolute() or not legacy_notice.is_absolute()
                    or legacy_library.parts[-3:] != ("vendor", "lib64", "libbase.so")
                    or legacy_notice.parts[-3:] != ("vendor", "etc", "NOTICE.xml.gz")
                    or legacy_library.parents[2] != legacy_notice.parents[2]):
                parser.error("unrecognized legacy source record: " + str(source_target))
            if (not target.is_file() or target.is_symlink() or target.read_bytes() != library_bytes
                    or not notice_target.is_file() or notice_target.is_symlink()
                    or notice_target.read_bytes() != notice_bytes):
                parser.error("legacy source record requires matching private ELF and NOTICE")
            # Retain verified legacy provenance until an explicit metadata migration.
            source_bytes = existing_bytes
    outputs = {notice_target: notice_bytes, source_target: source_bytes, target: library_bytes}
    pending = {}
    for path, data in outputs.items():
        if path.is_symlink() or not path.resolve().is_relative_to(destination):
            parser.error("output symlink or parent path escapes private destination: " + str(path))
        if path.exists():
            if not path.is_file() or path.read_bytes() != data:
                parser.error("refusing to replace a different private input: " + str(path))
            # Reuse equal files without opening for write. They may be hardlinked
            # to a read-only input, and their existing timestamps must survive.
            continue
        pending[path] = data
    for path, data in pending.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        if path == target:
            shutil.copyfile(library, target)
        else:
            path.write_bytes(data)
    if target.read_bytes() != library.read_bytes():
        raise SystemExit("private copy differs from official input")
    print(f"Verified libbase byte for byte and {len(bindings)} mapped notice texts; wrote {len(pending)} new files.")


if __name__ == "__main__":
    main()
