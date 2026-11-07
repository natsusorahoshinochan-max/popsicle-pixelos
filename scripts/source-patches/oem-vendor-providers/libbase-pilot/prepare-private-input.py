#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Copy one official libbase and its mapped notices into the private input area."""

import argparse
import gzip
import html
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

    outputs = {
        destination / "libbase/NOTICE": ("\n\n".join(text) + "\n").encode(),
        destination / "libbase/SOURCE.json": (json.dumps({
            "official_library": str(library),
            "official_notice": str(notices),
            "notice_bindings": bindings,
            "notice_content_ids": "Identifiers supplied by Xiaomi's NOTICE, not generated checksums.",
        }, indent=2) + "\n").encode(),
    }
    target = destination / "libbase/arm64/libbase.so"
    outputs[target] = library.read_bytes()
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
