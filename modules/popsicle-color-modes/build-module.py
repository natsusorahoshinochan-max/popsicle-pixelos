#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package the matching source-built color repair with normal ART/verity companions."""

import argparse
import hashlib
from pathlib import Path
import runpy
import shutil
import subprocess


FRAMEWORK = (
    "system/framework/services.jar",
    "system/framework/services.jar.prof",
    "system/framework/oat/arm64/services.art",
    "system/framework/oat/arm64/services.odex",
    "system/framework/oat/arm64/services.vdex",
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android", type=Path, required=True)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    android = args.android.resolve(strict=True)
    out = android / "out-pixelos-user"
    product = out / "target/product/popsicle"
    here = Path(__file__).resolve().parent
    baseline = args.baseline_manifest.resolve(strict=True)
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    staging = output / "module"
    staging.mkdir()
    for name in ("module.prop", "customize.sh", "README.md"):
        shutil.copy2(here / name, staging / name)
    for name in (*FRAMEWORK, "system/bin/surfaceflinger"):
        target = staging / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(product / name, target)
        target.chmod(0o755 if name == "system/bin/surfaceflinger" else 0o644)

    # Retain every baseline entry except the framework files replaced by this module.
    helper = runpy.run_path(str(here.parent / "popsicle-repair-parts/manifest_support.py"))
    helper["build_manifest"](
        android, out, baseline, staging, FRAMEWORK,
        staging / "system/etc/security/fsverity/BuildManifest.apk",
        android / "build/make/target/product/security/testkey",
    )
    payload = sorted(p.relative_to(staging).as_posix()
                     for p in (staging / "system").rglob("*") if p.is_file())
    (staging / "payload-files.txt").write_text("\n".join(payload) + "\n")
    (staging / "customize.sh").chmod(0o755)
    listing = output / "zip-inputs.txt"
    listing.write_text("\n".join(str(p) for p in sorted(staging.rglob("*"))
                                 if p.is_file()) + "\n")
    archive = output / "popsicle-color-modes-v0.2.zip"
    subprocess.run([str(out / "host/linux-x86/bin/soong_zip"), "-parallel", "16",
                    "-o", str(archive), "-C", str(staging), "-l", str(listing)], check=True)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    archive.with_suffix(".zip.sha256").write_text(
        digest.hexdigest() + "  " + archive.name + "\n")
    print(archive)


if __name__ == "__main__":
    main()
