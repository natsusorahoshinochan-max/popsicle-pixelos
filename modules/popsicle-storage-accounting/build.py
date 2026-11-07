#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build and sign a storage-accounting module locally from the exact 20261014 APK."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import zipfile


BASELINE_SHA256 = "8be0a93fe484db68256555f6e1cec840e381bfb2be7d290d532debe63c948017"
PLATFORM_SHA256 = "c8a2e9bccf597c2fb6dc66bee293fc13f2fc47ec77bc6b2b0d52c11f51192ab8"
HELPER = "Lcom/android/settingslib/deviceinfo/StorageAccounting;"
CALLS = {
    "smali_classes2/com/android/settings/deviceinfo/storage/StorageUsageProgressBarPreferenceController.smali": "Ljava/lang/String;",
    "smali_classes3/com/android/settingslib/applications/StorageStatsSource.smali": "Ljava/util/UUID;",
    "smali_classes3/com/android/settingslib/deviceinfo/StorageManagerVolumeProvider.smali": "Ljava/lang/String;",
}
SIGNATURE_FILE = re.compile(r"META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))$", re.I)


def digest(path):
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def run(arguments, env, *, capture=False):
    return subprocess.run([str(arg) for arg in arguments], check=True, env=env,
                          text=True, stdout=subprocess.PIPE if capture else None).stdout


def signer(apksigner, apk, env):
    result = run([apksigner, "verify", "--print-certs", apk], env, capture=True)
    values = re.findall(r"certificate SHA-256 digest: ([0-9a-f]+)", result)
    if values != [PLATFORM_SHA256]:
        raise ValueError("APK does not have this ROM's single platform signer")
    return values[0]


def patch_smali(decoded):
    patched = []
    for name, descriptor in CALLS.items():
        path = decoded / name
        text = path.read_text()
        pattern = (r"(?m)^(\s*)invoke-virtual (\{[^}]+\}), "
                   r"Landroid/app/usage/StorageStatsManager;->getTotalBytes\("
                   + re.escape(descriptor) + r"\)J$")
        replacement = (r"\1invoke-static \2, " + HELPER
                       + "->getTotalBytes(Landroid/app/usage/StorageStatsManager;"
                       + descriptor + ")J")
        text, count = re.subn(pattern, replacement, text)
        if count != 1:
            raise ValueError("Unexpected original capacity call site: " + name)
        path.write_text(text)
        patched.append(name)
    cache = decoded / "smali_classes2/com/android/settings/deviceinfo/storage/StorageCacheHelper.smali"
    text = cache.read_text()
    if text.count('"StorageCache"') != 1:
        raise ValueError("Unexpected original storage cache name")
    cache.write_text(text.replace('"StorageCache"', '"StorageCacheAccountingV1"'))
    patched.append(cache.relative_to(decoded).as_posix())
    for path in decoded.glob("smali*/**/*.smali"):
        if "Landroid/app/usage/StorageStatsManager;->getTotalBytes(" in path.read_text():
            raise ValueError("Unconverted Settings capacity consumer: " + str(path))
    return patched


def write_apk(baseline, rebuilt, helper_dex, output):
    changed = {"classes2.dex", "classes3.dex"}
    with zipfile.ZipFile(baseline) as original, zipfile.ZipFile(rebuilt) as compiled:
        with zipfile.ZipFile(output, "w") as result:
            for item in original.infolist():
                if SIGNATURE_FILE.fullmatch(item.filename):
                    continue
                data = (compiled if item.filename in changed else original).read(item.filename)
                result.writestr(item, data)
            if "classes4.dex" in original.namelist():
                raise ValueError("Original APK unexpectedly has a fourth DEX")
            item = zipfile.ZipInfo("classes4.dex", (2009, 1, 1, 0, 0, 0))
            item.compress_type = zipfile.ZIP_STORED
            item.external_attr = 0o100644 << 16
            result.writestr(item, helper_dex.read_bytes())


def verify_entries(baseline, candidate):
    changed = {"classes2.dex", "classes3.dex"}
    with zipfile.ZipFile(baseline) as original, zipfile.ZipFile(candidate) as signed:
        original_names = {name for name in original.namelist()
                          if not SIGNATURE_FILE.fullmatch(name)}
        candidate_names = {name for name in signed.namelist()
                           if not SIGNATURE_FILE.fullmatch(name)}
        if candidate_names != original_names | {"classes4.dex"}:
            raise ValueError("Unexpected APK entry set after signing")
        for name in original_names:
            if name not in changed and original.read(name) != signed.read(name):
                raise ValueError("Unrelated APK content changed: " + name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("baseline-apk", "framework-header", "source", "java-home", "build-tools",
                 "cert", "key", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--apktool", default="apktool")
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    args.baseline_apk = args.baseline_apk.resolve(strict=True)
    if digest(args.baseline_apk) != BASELINE_SHA256:
        raise ValueError("Requires Settings from the 20261014 navigation target-files")
    env = dict(os.environ, JAVA_HOME=str(args.java_home.resolve(strict=True)))
    env["PATH"] = str(args.java_home / "bin") + os.pathsep + env.get("PATH", "")
    apksigner = args.build_tools.resolve(strict=True) / "apksigner"
    signer(apksigner, args.baseline_apk, env)
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    decoded = output / "decoded"
    run([args.apktool, "d", "--no-res", "--jobs", "16", "-o", decoded,
         args.baseline_apk], env)
    patched = patch_smali(decoded)
    rebuilt = output / "rebuilt.apk"
    run([args.apktool, "b", "--jobs", "16", "-o", rebuilt, decoded], env)

    helper = args.source / "frameworks/base/packages/SettingsLib/src/com/android/settingslib/deviceinfo/StorageAccounting.java"
    classes = output / "classes"
    classes.mkdir()
    run([args.java_home / "bin/javac", "--release", "17", "-classpath",
         args.framework_header, "-d", classes, helper], env)
    dex = output / "helper-dex"
    dex.mkdir()
    # Match the unmodified APK's minSdkVersion; the installer requires Android 17.
    run([args.build_tools / "d8", "--release", "--min-api", "29", "--lib",
         args.framework_header, "--output", dex, *sorted(classes.rglob("*.class"))], env)
    unsigned = output / "unsigned.apk"
    write_apk(args.baseline_apk, rebuilt, dex / "classes.dex", unsigned)
    aligned = output / "aligned.apk"
    run([args.build_tools / "zipalign", "-P", "16", "-f", "4", unsigned, aligned], env)
    candidate = output / "Settings.apk"
    run([apksigner, "sign", "--cert", args.cert, "--key", args.key,
         "--v4-signing-enabled", "false", "--out", candidate, aligned], env)
    signer(apksigner, candidate, env)
    run([args.build_tools / "zipalign", "-c", "-P", "16", "4", candidate], env)
    verify_entries(args.baseline_apk, candidate)

    staging = output / "module"
    staging.mkdir()
    for name in ("module.prop", "customize.sh", "README.md"):
        shutil.copyfile(here / name, staging / name)
    payload = staging / "system/system_ext/priv-app/Settings/Settings.apk"
    payload.parent.mkdir(parents=True)
    shutil.copyfile(candidate, payload)
    (payload.parent / "oat").mkdir()
    (staging / "customize.sh").chmod(0o755)
    candidate_digest = digest(candidate)
    (staging / "baseline-apk.sha256").write_text(BASELINE_SHA256 + "\n")
    (staging / "candidate-apk.sha256").write_text(candidate_digest + "\n")
    (staging / "payload-files.txt").write_text("system/system_ext/priv-app/Settings/Settings.apk\n")
    archive = output / "popsicle-storage-accounting-v0.1.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=6) as zipped:
        for path in sorted(staging.rglob("*")):
            zipped.write(path, path.relative_to(staging).as_posix())
    archive.with_suffix(".zip.sha256").write_text(digest(archive) + "  " + archive.name + "\n")
    report = {
        "baseline_rom": "PixelOS-popsicle-20261014-navigation_by_Kanoe",
        "baseline_build_datetime": 1791924330,
        "baseline_apk_sha256": BASELINE_SHA256,
        "candidate_apk_sha256": candidate_digest,
        "signer_certificate_sha256": PLATFORM_SHA256,
        "module": archive.name,
        "module_sha256": digest(archive),
        "module_bytes": archive.stat().st_size,
        "patched_smali": patched,
        "helper_source_sha256": digest(helper),
        "unchanged_apk_entries_verified": True,
        "build_host": "local-macos",
        "device_installation": "not-performed",
    }
    (output / "build-result.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
