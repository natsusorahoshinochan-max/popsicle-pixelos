#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package one independently prepared ROM repair as a KernelSU module."""

import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess


MANIFEST_FILES = (
    "system/etc/security/fsverity/BuildManifest.apk",
    "system/etc/security/fsverity/BuildManifest.apk.idsig",
)


def framework_files(*files):
    """Each framework artifact travels with its normal fs-verity metadata."""
    return tuple(path for file in files for path in (file, file + ".fsv_meta"))


PARTS = {
    "audio-reconfigure": {
        "id": "popsicle_audio_reconfigure",
        "name": "Popsicle Bluetooth offload reconfiguration",
        "description": "Forward valid offload notifications to the real Bluetooth HAL.",
        "files": ("system_ext/bin/popsicle_ims_audio_adapter",),
    },
    "ims-locked-boot": {
        "id": "popsicle_ims_locked_boot",
        "name": "Popsicle IMS locked boot initialization",
        "description": "Initialize the official audio controller before first unlock on its worker thread.",
        "files": (
            "system_ext/priv-app/PopsicleImsAudioBridge/PopsicleImsAudioBridge.apk",
            "system_ext/priv-app/PopsicleImsAudioBridge/oat/arm64/PopsicleImsAudioBridge.odex",
            "system_ext/priv-app/PopsicleImsAudioBridge/oat/arm64/PopsicleImsAudioBridge.vdex",
        ),
    },
    "brightness-event-order": {
        "id": "popsicle_brightness_event_order",
        "name": "Popsicle startup brightness event ordering",
        "description": "Compare queued light samples using their original timestamps. Mutually exclusive with the VPN ingress module.",
        "files": framework_files(
            "system/framework/services.jar",
            "system/framework/services.jar.prof",
            "system/framework/oat/arm64/services.art",
            "system/framework/oat/arm64/services.odex",
            "system/framework/oat/arm64/services.vdex",
        ) + MANIFEST_FILES,
    },
    "rear-notice-eligibility": {
        "id": "popsicle_rear_notice_eligibility",
        "name": "Popsicle rear notification eligibility",
        "description": "Reconcile rear notification updates and snapshots, including revoked eligibility.",
        "files": (
            "system_ext/priv-app/SystemUI/SystemUI.apk",
            "system_ext/priv-app/SystemUI/oat/arm64/SystemUI.odex",
            "system_ext/priv-app/SystemUI/oat/arm64/SystemUI.vdex",
        ),
    },
    "vpn-ingress-owner": {
        "id": "popsicle_vpn_ingress_owner",
        "name": "Popsicle VPN ingress ownership",
        "description": "Retire VPN ingress sources by network ownership. Mutually exclusive with the brightness event module.",
        "files": (
            "apex/com.android.tethering/javalib/service-connectivity.jar",
            "apex/com.android.tethering/javalib/service-connectivity.jar.prof",
        ) + framework_files(
            "system/framework/oat/arm64/apex@com.android.tethering@javalib@service-connectivity.jar@classes.art",
            "system/framework/oat/arm64/apex@com.android.tethering@javalib@service-connectivity.jar@classes.odex",
            "system/framework/oat/arm64/apex@com.android.tethering@javalib@service-connectivity.jar@classes.vdex",
        ) + MANIFEST_FILES,
    },
}


def module_path(relative):
    if relative.startswith("apex/"):
        return "connectivity/" + Path(relative).name
    if relative.startswith("system/"):
        return relative
    return "system/" + relative


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=PARTS)
    parser.add_argument("payload", type=Path, help="Prepared product-relative files for this part")
    parser.add_argument("output", type=Path, help="New directory for this part's module and ZIP")
    parser.add_argument("--soong-zip", required=True, type=Path)
    args = parser.parse_args()
    payload = args.payload.resolve(strict=True)
    soong_zip = args.soong_zip.resolve(strict=True)
    part = PARTS[args.part]
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    staging = output / "module"
    staging.mkdir()
    here = Path(__file__).resolve().parent

    (staging / "module.prop").write_text(
        "id={id}\nname={name}\nversion=0.1\nversionCode=1\nauthor=Kanoe\n"
        "description={description}\n".format(**part)
    )
    for name in ("customize.sh", "README.md"):
        shutil.copy2(here / name, staging / name)
    if args.part == "vpn-ingress-owner":
        for name in ("post-mount.sh", "mount-connectivity.sh"):
            shutil.copy2(here / name, staging / name)
            (staging / name).chmod(0o755)

    paths = []
    for relative in part["files"]:
        # Copy only this part's explicit files, never unrelated staged output.
        target_name = module_path(relative)
        target = staging / target_name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(payload / relative, target)
        mode = "0755" if relative == "system_ext/bin/popsicle_ims_audio_adapter" else "0644"
        target.chmod(int(mode, 8))
        paths.append(f"{target_name}\t/{relative}\t{mode}\n")
    (staging / "payload-map.tsv").write_text("".join(paths))

    listing = output / "zip-inputs.txt"
    listing.write_text("\n".join(str(path) for path in sorted(staging.rglob("*"))
                                 if path.is_file()) + "\n")
    archive = output / (part["id"] + "-v0.1.zip")
    subprocess.run([str(soong_zip), "-parallel", "16", "-o", str(archive),
                    "-C", str(staging), "-l", str(listing)], check=True)
    digest = hashlib.sha256()
    with archive.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    archive.with_suffix(".zip.sha256").write_text(
        digest.hexdigest() + "  " + archive.name + "\n")
    print(archive)


if __name__ == "__main__":
    main()
