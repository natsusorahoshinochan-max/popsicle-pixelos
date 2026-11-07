#!/usr/bin/env python3
"""Build a popsicle installation super from completed target-files.

Uses the fixed releasetools lpmake layout, selecting which slot receives images.
This does not flash, choose the device's active slot, or run offline image verification.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import struct

PARTITIONS = {"system", "system_ext", "product", "vendor", "odm", "mi_product",
              "system_dlkm", "vendor_dlkm"}
GROUP = "qti_dynamic_partitions"
SUPER_SIZE = 13421772800
GROUP_SIZE = 13411287040


def require(value, message):
    if not value:
        raise ValueError(message)


def image_size(path):
    """Read the logical extent needed by lpmake from a raw or sparse image."""
    with path.open("rb") as stream:
        header = stream.read(28)
    if header[:4] != b"\x3a\xff\x26\xed":
        return path.stat().st_size
    require(len(header) == 28, f"truncated sparse image: {path}")
    _, major, _, file_header, chunk_header, block_size, blocks, _, _ = struct.unpack(
        "<IHHHHIIII", header)
    require(major == 1 and file_header >= 28 and chunk_header >= 12 and block_size,
            f"invalid sparse image header: {path}")
    return block_size * blocks


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target-files-dir", required=True, type=Path)
    parser.add_argument("--tools-bin", required=True, type=Path)
    parser.add_argument("--slot", required=True, choices=("a", "b"))
    parser.add_argument("--work-dir", required=True, type=Path)
    args = parser.parse_args()
    args.target_files_dir = args.target_files_dir.resolve()
    args.tools_bin = args.tools_bin.resolve()
    args.work_dir = args.work_dir.resolve()
    require(not args.target_files_dir.is_relative_to(args.work_dir) and
            not args.work_dir.is_relative_to(args.target_files_dir), "work directory aliases inputs")
    args.work_dir.mkdir(parents=True, exist_ok=False)
    report = {"complete": False, "slot": args.slot, "scope": __doc__}
    try:
        metadata = args.target_files_dir / "META/misc_info.txt"
        info = {}
        for line in metadata.read_text().splitlines():
            if not line or line.startswith("#"):
                continue
            key, value = line.split("=", 1)
            require(key not in info, f"duplicate metadata: {key}")
            info[key] = value
        require(info.get("ab_update") == "true" and info.get("virtual_ab") == "true", "expected launch virtual A/B")
        require(info.get("super_metadata_device") == "super" and info.get("super_block_devices") == "super", "unexpected physical super layout")
        require(info.get("super_partition_groups") == GROUP, "unexpected dynamic group")
        require(int(info["super_super_device_size"]) == SUPER_SIZE and
                int(info[f"super_{GROUP}_group_size"]) == GROUP_SIZE, "unexpected partition capacity")
        for key in ("dynamic_partition_list", f"super_{GROUP}_partition_list"):
            names = info[key].split()
            require(len(names) == len(PARTITIONS) and set(names) == PARTITIONS, f"incomplete {key}")
        require(not (args.target_files_dir / "IMAGES/system_other.img").exists(), "unexpected system_other image")
        images = {name: args.target_files_dir / "IMAGES" / (name + ".img") for name in sorted(PARTITIONS)}
        sizes = {name: image_size(p) for name, p in images.items()}
        require(all(size > 0 and size % 4096 == 0 for size in sizes.values()), "invalid image extent size")
        require(sum(sizes.values()) <= GROUP_SIZE, "images exceed group")
        output = args.work_dir / ("super-layout-" + args.slot + ".img")
        command = [str(args.tools_bin / "lpmake"), "--metadata-size", "65536", "--super-name", "super",
                   "--metadata-slots", "3", "--virtual-ab", "--device", f"super:{SUPER_SIZE}"]
        for slot in ("a", "b"):
            command += ["--group", f"{GROUP}_{slot}:{GROUP_SIZE}"]
        for name, path in images.items():
            for slot in ("a", "b"):
                size = sizes[name] if slot == args.slot else 0
                command += ["--partition", f"{name}_{slot}:readonly:{size}:{GROUP}_{slot}"]
                if slot == args.slot:
                    command += ["--image", f"{name}_{slot}={path}"]
        command += ["--sparse", "--output", str(output)]
        report["command"] = command
        subprocess.run(command, check=True)
        raw = args.work_dir / "super.raw.img"
        subprocess.run([str(args.tools_bin / "simg2img"), str(output), str(raw)], check=True)
        # lpmake leaves unallocated ranges as DONT_CARE. Write explicit zero
        # fills instead, so installation writes the entire device, including gaps.
        install = args.work_dir / ("super-install-" + args.slot + ".img")
        subprocess.run([str(args.tools_bin / "img2simg"), str(raw), str(install)], check=True)
        report["raw_reference"] = str(raw)
        report["full_device_write_bytes"] = SUPER_SIZE
        report["complete"] = True
        report["output"] = str(install)
        report["layout_image"] = str(output)
    finally:
        (args.work_dir / "results.json").write_text(json.dumps(report, indent=2) + "\n")


if __name__ == "__main__":
    main()
