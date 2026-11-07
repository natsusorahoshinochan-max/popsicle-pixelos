#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Wrap the verified Play-delivered split set for Soong without changing any APK."""
import argparse
import ctypes
import os
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

SPLITS = ["base.apk", "split_config.arm64_v8a.apk", "split_config.en.apk",
          "split_config.es.apk", "split_config.xxhdpi.apk", "split_config.zh.apk"]
GOOGLE_CERT = "b7971ccc10a03932e14a3557a1b4c2a84be0ecb506777f0c72dd46cf5d7093c6"
AICORE_PACKAGE = "com.google.android.aicore"
AICORE_VERSION = "0.release.prod_aicore_20260723.00_RC11.964081323"


def archive_path(name):
    suffix = "master" if name == "base.apk" else name.removeprefix("split_").removesuffix(".apk")
    return "splits/base-" + suffix + ".apk"


def publish_directory(source, target):
    """Publish on Linux without replacing a concurrently created destination."""
    libc = ctypes.CDLL(None, use_errno=True)
    rename = getattr(libc, "renameat2", None)
    if rename is None:
        raise RuntimeError("AICore preparation requires Linux renameat2 support")
    rename.argtypes = [ctypes.c_int, ctypes.c_char_p, ctypes.c_int, ctypes.c_char_p, ctypes.c_uint]
    rename.restype = ctypes.c_int
    at_fdcwd = -100
    rename_noreplace = 1
    if rename(at_fdcwd, os.fsencode(source), at_fdcwd, os.fsencode(target), rename_noreplace):
        error = ctypes.get_errno()
        raise OSError(error, os.strerror(error), str(target))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tree", type=Path)
    parser.add_argument("inputs", type=Path)
    parser.add_argument("--host-bin", type=Path, required=True,
                        help="directory containing aapt2 and an APK signer, including the SDK JAR layout")
    parser.add_argument("--protoc", type=Path,
                        help="protobuf compiler executable, defaulting to HOST_BIN/aprotoc")
    args = parser.parse_args()
    requested_tree = args.tree.absolute()
    if any(path.is_symlink() for path in [requested_tree, *requested_tree.parents]):
        parser.error("Android tree must not use symlink paths")
    tree = requested_tree.resolve(strict=True)
    if not (tree / "build/envsetup.sh").is_file():
        parser.error("Expected an Android source tree")
    target = tree / "vendor/xiaomi/popsicle-private/prebuilt/aicore"
    if any(path.is_symlink() for path in [target, *target.parents]):
        parser.error("Private output path must not use symlinks")
    if target.exists():
        parser.error("Refusing to overwrite a prepared AICore input")
    inputs = args.inputs.resolve(strict=True)
    if target.is_relative_to(inputs) or inputs.is_relative_to(target):
        parser.error("Original APK inputs and private output must be separate")
    host = args.host_bin.resolve(strict=True)
    java = tree / "prebuilts/jdk/jdk21/linux-x86/bin/java"
    signer_jar = host.parent / "lib/apksigner.jar"
    required_tools = [java, host / "aapt2"]
    if signer_jar.is_file():
        signer = [str(java), "-jar", str(signer_jar)]
    else:
        signer = [str(host / "apksigner")]
        required_tools.append(host / "apksigner")
    for tool in required_tools:
        if not tool.is_file() or not os.access(tool, os.X_OK):
            raise ValueError("Expected executable host tool: " + str(tool))
    protoc = (args.protoc or host / "aprotoc").resolve(strict=True)
    if not protoc.is_file() or not os.access(protoc, os.X_OK):
        raise ValueError("Expected executable protobuf compiler: " + str(protoc))
    env = dict(os.environ, JAVA_HOME=str(tree / "prebuilts/jdk/jdk21/linux-x86"))
    env["PATH"] = env["JAVA_HOME"] + "/bin:" + env.get("PATH", "")
    packages = {}
    for name in SPLITS:
        apk = inputs / name
        if apk.is_symlink() or not apk.is_file():
            raise ValueError("Expected an original regular APK: " + name)
        output = subprocess.check_output([*signer, "verify", "--print-certs", str(apk)], env=env, text=True)
        if "certificate SHA-256 digest: " + GOOGLE_CERT not in output:
            raise ValueError("Unexpected AICore signer: " + name)
        badging = subprocess.check_output([str(host / "aapt2"), "dump", "badging", str(apk)], text=True)
        package_line = next((line for line in badging.splitlines() if line.startswith("package: ")), "")
        metadata = dict(re.findall(r"([A-Za-z][A-Za-z0-9_]*)='([^']*)'", package_line))
        expected_split = "" if name == "base.apk" else name.removeprefix("split_").removesuffix(".apk")
        if metadata.get("name") != AICORE_PACKAGE or metadata.get("split", "") != expected_split:
            raise ValueError("Unexpected AICore package or split identity: " + name)
        packages[name] = metadata
    base = packages["base.apk"]
    if base.get("versionName") != AICORE_VERSION or not base.get("versionCode", "").isdecimal():
        raise ValueError("Expected the fixed complete AICore version")
    if any(package.get("versionCode") != base["versionCode"] for package in packages.values()):
        raise ValueError("AICore split versionCode differs from base APK")
    manifest = subprocess.check_output([str(host / "aapt2"), "dump", "xmltree", "--file",
                                        "AndroidManifest.xml", str(inputs / "base.apk")], text=True)
    if 'package="com.google.android.aicore"' not in manifest or "0.stub." in manifest:
        raise ValueError("Expected complete AICore, not a stub")
    for service in ["AiCoreIntelligenceService", "AiCoreIsolatedService"]:
        if service not in manifest:
            raise ValueError("Missing " + service)
    entries = []
    for name in SPLITS:
        metadata = 'is_master_split: true' if name == "base.apk" else (
            'split_id: "' + name.removeprefix("split_").removesuffix(".apk") + '"')
        entries.append('apk_description { path: "' + archive_path(name)
                       + '" split_apk_metadata { ' + metadata + ' } }')
    toc = ('package_name: "com.google.android.aicore" variant { '
           'targeting { abi_targeting { value { alias: ARM64_V8A } } } '
           'apk_set { module_metadata { name: "base" delivery_type: INSTALL_TIME } '
           + " ".join(entries) + " } }")
    proto = tree / "build/soong/cmd/extract_apks/bundle_proto"
    encoded = subprocess.check_output([str(protoc), "-I", str(proto),
                                       "--encode=android.bundle.BuildApksResult",
                                       str(proto / "commands.proto")], input=toc.encode())
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = Path(tempfile.mkdtemp(prefix=".aicore-", dir=target.parent))
    try:
        with zipfile.ZipFile(temporary / "aicore.apks", "w", zipfile.ZIP_STORED) as archive:
            archive.writestr("toc.pb", encoded)
            for name in SPLITS:
                archive.write(inputs / name, archive_path(name))
        shutil.copy2(Path(__file__).with_name("Android.bp.in"), temporary / "Android.bp")
        (temporary / "source.txt").write_text(
            "Google Play delivery reference, 2026-09-15. Original signatures retained.\n"
            + base["versionName"] + "\nversionCode=" + base["versionCode"] + "\n")
        publish_directory(temporary, target)
    finally:
        if temporary.exists():
            shutil.rmtree(temporary)
    print(target)


if __name__ == "__main__":
    main()
