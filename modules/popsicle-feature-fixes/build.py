#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package only this feature delta from matching PixelOS build outputs."""
import argparse
import hashlib
import shutil
import subprocess
import zipfile
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--baseline-date", required=True)
    parser.add_argument("--baseline-framework-hashes", required=True, type=Path)
    args = parser.parse_args()
    if not args.baseline_date.isdecimal():
        parser.error("baseline-date must be a UTC epoch integer")
    product = args.tree / "out-pixelos-user/target/product/popsicle"
    files = {
        "system/framework/services.jar", "system/framework/services.jar.prof",
        "system/framework/framework-res.apk",
        "product/etc/sysconfig/popsicle-private-compute.xml",
        "product/overlay/PopsicleStatusbarSystemUI.apk",
        "system/etc/security/fsverity/BuildManifest.apk",
        "system/etc/security/fsverity/BuildManifest.apk.idsig",
    }
    # services.jar is part of APEX system-server services' class-loader context.
    # Carry their rebuilt preoptimization and matching verity metadata together.
    for line in args.baseline_framework_hashes.read_text().splitlines():
        digest, absolute = line.split(None, 1)
        relative = absolute.lstrip("/")
        if not relative.startswith("system/framework/") or ".." in Path(relative).parts:
            raise ValueError("Unexpected baseline path: " + absolute)
        source = product / relative
        if relative.endswith(".fsv_meta") or not source.is_file():
            continue
        if hashlib.sha256(source.read_bytes()).hexdigest() == digest:
            continue
        if relative not in files and not (
                relative.startswith("system/framework/oat/arm64/")
                and source.suffix in {".art", ".odex", ".vdex"}):
            raise ValueError("Unexpected framework delta: " + relative)
        files.add(relative)
    for folder in ["system_ext/priv-app/Settings", "product/priv-app/PopsicleAICore"]:
        directory = product / folder
        if not directory.is_dir():
            raise FileNotFoundError(directory)
        files.update(str(p.relative_to(product)) for p in directory.rglob("*") if p.is_file())
    files.update(str(p.relative_to(product)) for p in
                 (product / "system/framework/oat/arm64").glob("services.*") if p.is_file())
    files = {p for p in files if not p.endswith(".fsv_meta")}
    files.update(p + ".fsv_meta" for p in list(files) if p.startswith("system/framework/"))
    for name in files:
        if not (product / name).is_file():
            raise FileNotFoundError(product / name)
    args.output.mkdir(parents=True, exist_ok=True)
    staging = args.output / "module"
    staging.mkdir()  # Never overwrite a previously assembled candidate.
    here = Path(__file__).resolve().parent
    for name in ["module.prop", "customize.sh"]:
        shutil.copy2(here / name, staging / name)
    installed = []
    for name in sorted(files):
        relative = name if name.startswith("system/") else "system/" + name
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(product / name, target)
        installed.append(relative)
    (staging / "baseline-date").write_text(args.baseline_date + "\n")
    (staging / "payload-files.txt").write_text("\n".join(installed) + "\n")
    paths = sorted(p for p in staging.rglob("*") if p.is_file())
    listing = args.output / "zip-inputs.txt"
    listing.write_text("\n".join(str(p) for p in paths) + "\n")
    archive = args.output / "popsicle-feature-fixes.zip"
    subprocess.run([str(args.tree / "out-pixelos-user/host/linux-x86/bin/soong_zip"),
                    "-parallel", "16", "-o", str(archive), "-C", str(staging),
                    "-l", str(listing)], check=True)
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        if len(names) != len(paths) or set(names) != {str(p.relative_to(staging)) for p in paths}:
            raise RuntimeError("ZIP contents differ from staged payload")
    print(archive)


if __name__ == "__main__":
    main()
