#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Assemble the module from its explicit product-relative payload list."""
import argparse
import shutil
import subprocess
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path, help="Built product directory")
    parser.add_argument("output", type=Path, help="New output directory")
    parser.add_argument("--soong-zip", required=True, type=Path)
    parser.add_argument("--bluetooth-library", required=True, type=Path)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    files = (here / "payload-files.txt").read_text().splitlines()
    args.output.mkdir(parents=True, exist_ok=False)
    staging = args.output / "module"
    staging.mkdir()
    for name in ('module.prop', 'customize.sh', 'post-mount.sh', 'mount-bluetooth.sh'):
        shutil.copy2(here / name, staging / name)
    installed = []
    for relative in files:
        target_name = relative if relative.startswith("system/") else "system/" + relative
        target = staging / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(args.candidate / relative, target)
        installed.append(target_name)
    (staging / "payload-files.txt").write_text("\n".join(installed) + "\n")
    library = staging / "bluetooth/libbluetooth_jni.so"
    library.parent.mkdir()
    shutil.copy2(args.bluetooth_library, library)
    paths = sorted(path for path in staging.rglob("*") if path.is_file())
    listing = args.output / "zip-inputs.txt"
    listing.write_text("\n".join(str(path.resolve()) for path in paths) + "\n")
    output = args.output / 'popsicle-media-shade-fixes-v0.2.zip'
    subprocess.run([str(args.soong_zip.resolve()), "-parallel", "16", "-o", str(output.resolve()),
                    "-C", str(staging.resolve()), "-l", str(listing.resolve())], check=True)
    print(output)


if __name__ == "__main__":
    main()
