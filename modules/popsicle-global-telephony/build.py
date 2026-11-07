#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package ROM-built global telephony files for a reversible KernelSU trial."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("android", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    android = args.android.resolve(strict=True)
    product = android / "out-pixelos-user/target/product/popsicle"
    files = [
        "system_ext/priv-app/CarrierConfig/CarrierConfig.apk",
        "system_ext/priv-app/CarrierConfig/oat/arm64/CarrierConfig.odex",
        "system_ext/priv-app/CarrierConfig/oat/arm64/CarrierConfig.vdex",
        "product/overlay/PopsicleImsCarrier.apk",
        "product/etc/apns-conf.xml",
    ]
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    staging = output / "module"
    staging.mkdir()
    here = Path(__file__).resolve().parent
    for name in ("module.prop", "customize.sh", "README.md"):
        shutil.copy2(here / name, staging / name)
    payload = []
    for relative in files:
        target = staging / "system" / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(product / relative, target)
        payload.append("system/" + relative)
    for directory in ("carrier-config", "carrier-apns"):
        source = android / "vendor/xiaomi/popsicle-private/prebuilt" / directory
        shutil.copy2(source / "NOTICE", staging / ("NOTICE." + directory))
    (staging / "payload-files.txt").write_text("\n".join(payload) + "\n")
    listing = output / "zip-inputs.txt"
    listing.write_text("\n".join(str(p) for p in sorted(staging.rglob("*"))
                                 if p.is_file()) + "\n")
    archive = output / "popsicle-global-telephony-v0.1.zip"
    subprocess.run([str(android / "out-pixelos-user/host/linux-x86/bin/soong_zip"),
                    "-parallel", "16", "-o", str(archive), "-C", str(staging),
                    "-l", str(listing)], check=True)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    archive.with_suffix(".zip.sha256").write_text(
        digest.hexdigest() + "  " + archive.name + "\n")
    print(archive)


if __name__ == "__main__":
    main()
