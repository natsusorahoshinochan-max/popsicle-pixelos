#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""List or package the narrow ROM runtime payload; no device operations or hashes."""
import argparse
import shutil
import struct
import subprocess
import sys
import zipfile
from pathlib import Path

FIXED = [
    "vendor/etc/displayconfig/display_layout_configuration.xml",
    "product/etc/displayconfig/display_id_4630946457447247252.xml",
    "system/bin/installd",
    "system/framework/framework.jar", "system/framework/framework-res.apk",
    "system/framework/services.jar", "system/framework/services.jar.prof",
    "system/framework/arm64/boot-framework.art", "system/framework/arm64/boot-framework.oat",
    "system/framework/boot-framework.vdex",
    "system_ext/priv-app/SystemUI/SystemUI.apk",
    "system_ext/priv-app/PopsicleMiuiCamera/PopsicleMiuiCamera.apk",
    "system_ext/app/PopsicleSubscreenCenter/PopsicleSubscreenCenter.apk",
    "system/etc/classpaths/systemserverclasspath.pb",
    "system/etc/security/fsverity/BuildManifest.apk",
    "system/etc/security/fsverity/BuildManifest.apk.idsig",
    "system_ext/etc/security/fsverity/BuildManifestSystemExt.apk",
    "system_ext/etc/security/fsverity/BuildManifestSystemExt.apk.idsig",
    "system/etc/selinux/plat_service_contexts",
    "system_ext/etc/selinux/system_ext_property_contexts",
    "system_ext/etc/selinux/system_ext_seapp_contexts",
    "system_ext/framework/miui-cameraopt.jar",
    "system_ext/framework/pag-hyperos-release.jar",
    "system_ext/etc/permissions/miui-cameraopt.xml",
    "system_ext/etc/permissions/privapp-permissions-popsicle-camera.xml",
    "system_ext/etc/permissions/privapp-permissions-popsicle-systemui.xml",
    "system_ext/etc/permissions/com.android.systemui.libpag.xml",
    "system_ext/etc/public.libraries-hyperos.txt",
]
FIXED += [f"system/lib64/{name}.so" for name in
          ["libandroid_runtime", "libmedia_jni_utils", "libprocessgroup", "libstagefright"]]
FIXED += [f"system_ext/lib64/{name}.so" for name in [
    "libcamera_algoup_jni.xiaomi", "libcamera_mianode_jni.xiaomi", "libcameraopt",
    "libcameraopt_jni", "libpag.hyperos", "libffavc.hyperos"]]
FIXED += [f"system_ext/etc/{name}.json" for name in [
    "cameraopt", "cameraopt_perf", "cameraopt_reclaim", "cameraopt_thirdParty", "camerascene",
    "popsicle-process-policy"]]
APP_DIRS = ["system_ext/priv-app/SystemUI", "system_ext/priv-app/PopsicleMiuiCamera",
            "system_ext/app/PopsicleSubscreenCenter"]
PATTERNS = ["system/framework/arm64/boot*.art", "system/framework/arm64/boot*.oat",
            "system/framework/arm64/boot*.vdex", "system/framework/boot*.vdex",
            "system/framework/oat/arm64/services.*",
            "system_ext/framework/oat/arm64/miui-cameraopt.*",
            "system_ext/framework/oat/arm64/pag-hyperos-release.*"]


def payload(product):
    files = set(FIXED)
    for directory in APP_DIRS:
        files.update(str(p.relative_to(product)) for p in (product / directory).rglob("*")
                     if p.is_file())
    for pattern in PATTERNS:
        files.update(str(p.relative_to(product)) for p in product.glob(pattern) if p.is_file())
    files = {p for p in files if not p.endswith(".fsv_meta")}
    for name in list(files):
        path = product / name
        # Match build/make/core/Makefile fsverity-metadata-targets-patterns.
        if name.startswith(("system/framework/", "system_ext/framework/")) \
                or name.startswith("system/etc/classpaths/") and path.suffix == ".pb":
            files.add(name + ".fsv_meta")
    return sorted(files)


def validate_camera_policy(tree, baseline, output):
    """Check the exact module extension against the strictly compiled ROM policy."""
    host = tree / "out-pixelos-user/host/linux-x86/bin"
    target = tree / ("out-pixelos-user/soong/.intermediates/system/sepolicy/"
                     "precompiled_sepolicy/android_common/popsicle/precompiled_sepolicy")
    here = Path(__file__).resolve().parent / "tools"
    work = output / "policy-validation"
    work.mkdir()
    for source, name in [(baseline, "live"), (target, "target")]:
        subprocess.run([str(host / "checkpolicy"), "-b", "-C", "-M", "-o",
                        str(work / (name + ".cil")), str(source)], check=True)
    with baseline.open("rb") as stream:
        magic, length = struct.unpack("<II", stream.read(8))
        if magic != 0xF97CFF8C or length != 8 or stream.read(length) != b"SE Linux":
            raise ValueError("Expected the captured Android kernel policy header")
        version, = struct.unpack("<I", stream.read(4))
    with (work / "clone.cil").open("w") as stream:
        subprocess.run(["awk", "-f", str(here / "clone-camera-policy.awk"),
                        str(work / "live.cil")], stdout=stream, check=True)
    subprocess.run([str(host / "secilc"), "-m", "-M", "true", "-c", str(version),
                    str(work / "live.cil"), str(work / "clone.cil"),
                    str(here / "camera-extra.cil"), "-o", str(work / "candidate.bin"),
                    "-f", str(work / "file_contexts")], check=True)
    subprocess.run([str(host / "checkpolicy"), "-b", "-C", "-M", "-o",
                    str(work / "candidate.cil"), str(work / "candidate.bin")], check=True)
    with (output / "policy-validation.json").open("w") as stream:
        subprocess.run([sys.executable, str(here / "check-camera-policy.py"),
                        "--target", str(work / "target.cil"),
                        "--candidate", str(work / "candidate.cil")], stdout=stream, check=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    parser.add_argument("action", choices=["targets", "package"])
    parser.add_argument("--output", type=Path)
    parser.add_argument("--trace-brightness", action="store_true",
                        help="Enable temporary brightness diagnostics in this test module")
    parser.add_argument("--native-rom", action="store_true",
                        help="Use the integrated ROM policy without loading a module policy")
    parser.add_argument("--policy-baseline", type=Path,
                        help="Fresh complete live policy captured from the matching KSU device")
    parser.add_argument("--policy-export", type=Path,
                        help="Same-tree arm64 popsicle-policy-export diagnostic binary")
    args = parser.parse_args()
    tree = args.tree.resolve()
    product = tree / "out-pixelos-user/target/product/popsicle"
    files = payload(product)
    resources = tree / 'vendor/xiaomi/popsicle-private/prebuilt/oem-rear/resources/resource-files.txt'
    resource_files = resources.read_text().splitlines()
    for name in resource_files:
        if not name.startswith(('system/media/rearscreen/',
                                'product/etc/precust_theme/theme/.data/')) \
                or '..' in Path(name).parts:
            raise ValueError(f'Unexpected rear resource output: {name}')
    files = sorted(set(files) | set(resource_files))
    if args.action == "targets":
        for name in files:
            # APK v4 sidecars are generated by the APK signing target itself.
            if not name.endswith(".idsig"):
                print((product / name).relative_to(tree))
        return
    if args.output is None:
        parser.error("package requires --output")
    if not args.native_rom and (args.policy_baseline is None or args.policy_export is None):
        parser.error("package requires --policy-baseline and --policy-export")
    if not args.native_rom:
        with args.policy_export.open("rb") as stream:
            header = stream.read(20)
            if len(header) != 20 or header[:6] != b"\x7fELF\x02\x01" \
                    or struct.unpack_from("<H", header, 18)[0] != 183:
                raise ValueError("Expected the built arm64 policy exporter")
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    if not args.native_rom:
        validate_camera_policy(tree, args.policy_baseline.resolve(strict=True), output)
    staging = output / "staging"
    staging.mkdir()
    for name in files:
        source = product / name
        if not source.is_file():
            raise FileNotFoundError(source)
        if name.endswith(".fsv_meta"):
            original = product / name.removesuffix(".fsv_meta")
            if original.stat().st_mtime > source.stat().st_mtime:
                raise RuntimeError(f"Rebuild matching fs-verity metadata: {name}")
        destination = staging / (name if name.startswith("system/") else "system/" + name)
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    here = Path(__file__).resolve().parent
    for name in ["module.prop", "customize.sh", "README.md"]:
        shutil.copy2(here / name, staging / name)
    if args.native_rom:
        # This payload targets the integrated ROM; policy is already installed there.
        properties = dict(line.split("=", 1) for line in
                          (product / "system/build.prop").read_text().splitlines()
                          if line and not line.startswith("#") and "=" in line)
        (staging / "native-rom").write_text(properties["ro.system.build.date.utc"] + "\n")
    else:
        for name in ["sepolicy.rule", "post-mount.sh"]:
            shutil.copy2(here / name, staging / name)
        (staging / "tools").mkdir()
        for name in ["clone-camera-policy.awk", "camera-extra.cil", "load-camera-policy.sh"]:
            shutil.copy2(here / "tools" / name, staging / "tools" / name)
        shutil.copy2(args.policy_export, staging / "tools/policy-export")
        shutil.copy2(args.policy_baseline, staging / "tools/policy-baseline.bin")
        shutil.copy2(output / "policy-validation/candidate.bin", staging / "tools/camera-policy.bin")
        shutil.copy2(output / "policy-validation.json", staging / "policy-validation.json")
    if args.trace_brightness:
        (staging / "system.prop").write_text("log.tag.BrightnessRampTrace=DEBUG\n")
    (staging / "payload-files.txt").write_text("\n".join(files) + "\n")
    # soong_zip -D omits hidden entries, including the original .data themes.
    # Use an explicit list and verify names, not content hashes, after packaging.
    zip_inputs = sorted(p for p in staging.rglob("*") if p.is_file())
    input_list = output / "zip-inputs.txt"
    input_list.write_text("\n".join(str(p) for p in zip_inputs) + "\n")
    archive = output / "popsicle-oem-app-port.zip"
    subprocess.run([str(tree / "out-pixelos-user/host/linux-x86/bin/soong_zip"),
                    "-parallel", "16", "-o", str(archive),
                    "-C", str(staging), "-l", str(input_list)], check=True)
    expected = {str(p.relative_to(staging)) for p in zip_inputs}
    with zipfile.ZipFile(archive) as zipped:
        actual = [p.filename for p in zipped.infolist() if not p.is_dir()]
    if set(actual) != expected or len(actual) != len(expected):
        raise RuntimeError("ZIP entries differ from the complete staged file list")


if __name__ == "__main__":
    main()
