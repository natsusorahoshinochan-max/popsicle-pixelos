#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build targets and KernelSU packaging for device NR_CA registration compatibility."""

import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess


# Installed boot image components share dex2oat's image layout. Keep the complete
# system boot image set together, including both installed VDEX paths and their
# metadata. The module materializes the arm64 aliases as matching regular files.
BOOT_STEMS = (
    "boot", "boot-apache-xml", "boot-bouncycastle", "boot-core-icu4j",
    "boot-core-libart", "boot-ext", "boot-framework", "boot-framework-adservices",
    "boot-framework-graphics", "boot-framework-location",
    "boot-framework-ondeviceintelligence-platform", "boot-ims-common",
    "boot-okhttp", "boot-telephony-common", "boot-voip-common",
)
FRAMEWORK_FILES = ["system/framework/telephony-common.jar", "system/etc/boot-image.prof"]
EXTRA_FILES = ["system/etc/boot-image.bprof"]
for stem in BOOT_STEMS:
    FRAMEWORK_FILES.extend((f"system/framework/arm64/{stem}.art",
                            f"system/framework/arm64/{stem}.oat",
                            f"system/framework/arm64/{stem}.vdex",
                            f"system/framework/{stem}.vdex"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=("targets", "package"))
    parser.add_argument("tree", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--baseline-manifest", type=Path)
    args = parser.parse_args()
    tree = args.tree.resolve()
    out = tree / "out-pixelos-user"
    product = out / "target/product/popsicle"
    if args.action == "targets":
        for name in FRAMEWORK_FILES + EXTRA_FILES:
            print((product / name).relative_to(tree))
        return
    if args.output is None or args.baseline_manifest is None:
        parser.error("package requires --output and --baseline-manifest")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    staging = output / "module"
    staging.mkdir()
    here = Path(__file__).resolve().parent
    for name in ("module.prop", "customize.sh", "README.md"):
        shutil.copy2(here / name, staging / name)
    for name in FRAMEWORK_FILES + EXTRA_FILES:
        dest = staging / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(product / name, dest)

    # Reuse the existing normal fs-verity metadata/signing implementation. Only
    # these replacements are merged into the accepted ROM's manifest.
    spec = importlib.util.spec_from_file_location(
        "manifest_support", here.parent / "popsicle-repair-parts/manifest_support.py")
    support = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(support)
    manifest = "system/etc/security/fsverity/BuildManifest.apk"
    support.build_manifest(
        tree, out, args.baseline_manifest, staging, FRAMEWORK_FILES,
        staging / manifest, tree / "build/make/target/product/security/testkey")
    files = [entry for name in FRAMEWORK_FILES for entry in (name, name + ".fsv_meta")]
    files.extend(EXTRA_FILES)
    files.extend((manifest, manifest + ".idsig"))
    (staging / "payload-map.tsv").write_text("".join(
        f"{name}\t/{name}\t0644\n" for name in files))
    # Retain the existing NOTICE shipped with the matching ROM.
    shutil.copy2(product / "system/etc/NOTICE.xml.gz", staging / "NOTICE.xml.gz")
    listing = output / "zip-inputs.txt"
    listing.write_text("\n".join(str(p) for p in sorted(staging.rglob("*"))
                                 if p.is_file()) + "\n")
    archive = output / "popsicle_nr_registration-v0.1.zip"
    subprocess.run([str(out / "host/linux-x86/bin/soong_zip"), "-parallel", "16",
                    "-o", str(archive), "-C", str(staging), "-l", str(listing)], check=True)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    archive.with_suffix(".zip.sha256").write_text(
        digest.hexdigest() + "  " + archive.name + "\n")
    print(archive)


if __name__ == "__main__":
    main()
