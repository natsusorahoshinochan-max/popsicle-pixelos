#!/usr/bin/env python3
"""Export an A16-direct fastboot package from a completed user target-files.

Run on the cloud Linux host. Firmware inputs are read-only. No device commands.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import struct
import subprocess
import sys
import zipfile

SUPPORT = Path(__file__).resolve().parent
CHUNK = 4 * 1024 * 1024
SUPER_SIZE = 13421772800
FIRMWARE = tuple("""abl xbl xbl_config multiimgqti tme_seq_patch tme_fw tme_config
xbl_ac_config uefi aop aop_config tz hyp modem modemfirmware bluetooth dsp keymaster
spuservice devcfg qupfw uefisecapp imagefv shrm cpucp idmanager featenabler xbl_ramdump
cpucp_dtb soccp soccp_debug soccp_dcd pdp pdp_cdb tz_ac_config hyp_ac_config dcp
tz_qti_config secretkeeper vm-bootsys qtvm_dtbo pvmfw""".split())
ROM_PRODUCTS = {"pixelos": "custom_popsicle"}

PRODUCT = ("boot", "dtbo", "vendor_boot", "vbmeta", "recovery", "vbmeta_system", "init_boot")
OFFICIAL_LOGICAL = set("odm product system system_dlkm system_ext vendor vendor_dlkm mi_product mi_ext".split())


def require(condition, message):
    if not condition:
        raise ValueError(message)


def verify_product_identity(props, rom):
    require(rom in ROM_PRODUCTS, "unsupported ROM identity")
    expected = ROM_PRODUCTS[rom]
    require(props.get("ro.product.system.device") == "popsicle" and
            props.get("ro.system.build.type", props.get("ro.build.type")) == "user" and
            props.get("ro.product.system.name") == expected and
            props.get("ro.build.flavor") == expected + "-user",
            f"target-files is not the selected {rom} popsicle user product")


def read_product_props(z):
    return dict(line.split("=", 1) for line in z.read("SYSTEM/build.prop").decode().splitlines()
                if "=" in line and not line.startswith("#"))


def digest(path):
    value = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(CHUNK), b""):
            value.update(block)
    return value.digest()


def copy_file(source, target):
    # Copies are never edited afterward. Do not hard-link mutable build outputs.
    with source.open("rb") as src, target.open("xb") as dst:
        shutil.copyfileobj(src, dst, CHUNK)


def firmware_inputs(args):
    explicit = (args.payload, args.firmware_images, args.a16_flash_script)
    if args.firmware_root is not None:
        require(not any(explicit), "Use --firmware-root or all three explicit firmware inputs")
        root = args.firmware_root.resolve()
        return (root / "inputs/popsicle_official_OTA_A17/payload.bin",
                root / "extracted/a17-payload",
                root / "inputs/popsicle_official_images_A16/flash_all_macos.sh")
    require(all(explicit), "Provide --payload, --firmware-images and --a16-flash-script")
    return tuple(path.resolve() for path in explicit)


def read_firmware(payload, images, script):
    from payload_schema import update_metadata_pb2 as pb

    with payload.open("rb") as stream:
        header = stream.read(24)
        require(len(header) == 24, "truncated payload header")
        magic, major, length, signature = struct.unpack(">4sQQI", header)
        require(magic == b"CrAU" and major == 2 and 0 < length < 64 * 1024**2,
                "unexpected payload header")
        require(24 + length + signature < payload.stat().st_size, "truncated payload")
        raw = stream.read(length)
    manifest = pb.DeltaArchiveManifest()
    manifest.ParseFromString(raw)
    names = [p.partition_name for p in manifest.partitions]
    expected = OFFICIAL_LOGICAL | set(PRODUCT) | set(FIRMWARE)
    require(manifest.minor_version == 0 and not manifest.partial_update and
            len(names) == len(set(names)) == 58 and set(names) == expected,
            "expected the complete selected 58-partition A17 payload")
    logical = {n for g in manifest.dynamic_partition_metadata.groups for n in g.partition_names}
    require(logical == OFFICIAL_LOGICAL, "unexpected official logical inventory")
    require(manifest.security_patch_level == "2026-08-01" and
            manifest.max_timestamp == 1786987373, "wrong official A17 cohort")
    allowed = {pb.InstallOperation.REPLACE, pb.InstallOperation.REPLACE_BZ, pb.InstallOperation.REPLACE_XZ}
    for p in manifest.partitions:
        require(not p.HasField("old_partition_info") and all(o.type in allowed for o in p.operations),
                f"partition requires an old input: {p.partition_name}")
    rows = re.findall(r"flash\s+(\S+)_ab\s+`dirname \$0`/images/(\S+)", script.read_text())
    selected = [(n, f) for n, f in rows if n in FIRMWARE]
    require([n for n, _ in selected] == list(FIRMWARE), "A16 firmware order/targets changed")
    partition_map = {p.partition_name: p for p in manifest.partitions}
    results = []
    for name, a16_file in selected:
        image = images / (name + ".img")
        p = partition_map[name]
        require(image.stat().st_size == p.new_partition_info.size > 0, f"wrong firmware length: {name}")
        require(len(p.new_partition_info.hash) == 32 and digest(image) == p.new_partition_info.hash,
                f"firmware differs from payload new_partition_info: {name}")
        results.append({"partition": name, "file": image.name, "bytes": image.stat().st_size,
                        "source": str(image), "a16_input": a16_file, "target": name + "_b",
                        "payload_content_verified": True})
    return payload, script, results


def export(args):
    require(args.rom in ROM_PRODUCTS, "unsupported ROM identity")
    source = args.source_release.resolve()
    output = args.output.resolve()
    require(not output.exists(), "output must be a new release directory")
    tf_zip = source / "target_files.zip"
    require(tf_zip.is_file(), "source release needs target_files.zip")
    # Reject another ROM before copying images or reading the large firmware input.
    with zipfile.ZipFile(tf_zip) as z:
        verify_product_identity(read_product_props(z), args.rom)
    install_readme = SUPPORT.parents[1] / "docs/pixelos/fastboot-install.md"
    require(install_readme.is_file(), "missing selected ROM installation instructions")
    firmware_paths = firmware_inputs(args)
    tools = args.tools_bin.resolve()
    for name in ("lpmake", "simg2img", "img2simg"):
        require(os.access(tools / name, os.X_OK), f"missing host tool: {name}")
    _, _, firmware = read_firmware(*firmware_paths)
    output.mkdir(parents=True)
    report = {"complete": False, "device_acceptance": "pending-user-test-from-A16",
              "source_release": str(source), "rom": args.rom, "firmware": firmware,
              "supported_base": "OS3.0.318.0", "official_firmware": "OS4.0.0.23.XPBCNXM"}
    try:
        copy_file(tf_zip, output / "target_files.zip")
        tf_dir = output / "target-files"
        tf_dir.mkdir()
        image_dir = output / "images"
        image_dir.mkdir()
        with zipfile.ZipFile(output / "target_files.zip") as z:
            members = [n for n in z.namelist() if n.startswith("IMAGES/") and n.endswith(".img")]
            members += ["META/misc_info.txt", "META/ab_partitions.txt", "SYSTEM/build.prop"]
            for member in members:
                require(".." not in Path(member).parts and not Path(member).is_absolute(), "unsafe ZIP path")
                if member.startswith("IMAGES/"):
                    require(member.count("/") == 1 and re.fullmatch(r"[a-z0-9_]+\.img", Path(member).name),
                            "unexpected image filename")
                dest = tf_dir / member
                dest.parent.mkdir(parents=True, exist_ok=True)
                with z.open(member) as src, dest.open("xb") as dst:
                    shutil.copyfileobj(src, dst, CHUNK)
                if member.startswith("IMAGES/"):
                    os.link(dest, image_dir / dest.name)
        # Assemble super from the selected target-files logical images.
        subprocess.run([sys.executable, str(SUPPORT / "build-install-super.py"),
                        "--target-files-dir", str(tf_dir), "--tools-bin", str(tools),
                        "--slot", "b", "--work-dir", str(output / "install-super")], check=True)
        super_report = json.loads((output / "install-super/results.json").read_text())
        package = output / "fastboot"
        package.mkdir()
        rows = []
        for row in firmware:
            dest = package / row["file"]
            copy_file(Path(row["source"]), dest)
            rows.append((row["target"], dest.name, row["bytes"], row["bytes"], "a17-payload"))
        super_image = Path(super_report["output"])
        copy_file(super_image, package / "super-install-b.img")
        rows.append(("super", "super-install-b.img", super_image.stat().st_size, SUPER_SIZE, args.rom + "-super"))
        for name in PRODUCT:
            dest = package / (name + ".img")
            copy_file(image_dir / dest.name, dest)
            rows.append((name + "_b", dest.name, dest.stat().st_size, dest.stat().st_size, args.rom + "-target-files"))
        (package / "flash-manifest.tsv").write_text("".join("\t".join(map(str, row)) + "\n" for row in rows))
        copy_file(SUPPORT / "flash-fastboot.sh", package / "flash-fastboot.sh")
        copy_file(install_readme, package / "README.md")
        os.chmod(package / "flash-fastboot.sh", 0o755)
        files = sorted([row[1] for row in rows] + ["flash-manifest.tsv", "flash-fastboot.sh", "README.md"])
        (package / "SHA256SUMS").write_text("".join(f"{digest(package / n).hex()}  {n}\n" for n in files))
        report.update(complete=True, image_count=len(rows), firmware_bytes=sum(r["bytes"] for r in firmware),
                      package=str(package), target_files_firmware_included=False)
        (output / "READY.txt").write_text("Release artifacts generated. Device acceptance is pending user testing.\n")
    finally:
        (output / "release-result.json").write_text(json.dumps(report, indent=2) + "\n")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rom", choices=tuple(ROM_PRODUCTS), default="pixelos")
    parser.add_argument("--source-release", required=True, type=Path)
    parser.add_argument("--tools-bin", required=True, type=Path)
    parser.add_argument("--firmware-root", type=Path, help="Legacy firmware directory layout")
    parser.add_argument("--payload", type=Path)
    parser.add_argument("--firmware-images", type=Path)
    parser.add_argument("--a16-flash-script", type=Path)
    parser.add_argument("--output", required=True, type=Path)
    export(parser.parse_args())


if __name__ == "__main__":
    main()
