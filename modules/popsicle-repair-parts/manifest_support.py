#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Sign a baseline BuildManifest with only one module's framework entries replaced."""

import argparse
from pathlib import Path, PurePosixPath
import re
import subprocess
import tempfile
import zipfile

from google.protobuf import descriptor_pb2, descriptor_pool, message_factory


def run(arguments):
    return subprocess.check_output([str(arg) for arg in arguments], text=True)


def load_manifest_type(android, host, work):
    """Use the Android tree's proto with the host's protobuf runtime."""
    proto_dir = android / "system/security/fsverity"
    descriptor = work / "fsverity.pb"
    run([host / "bin/aprotoc", "--proto_path=" + str(proto_dir),
         "--descriptor_set_out=" + str(descriptor),
         proto_dir / "fsverity_digests.proto"])
    files = descriptor_pb2.FileDescriptorSet()
    files.ParseFromString(descriptor.read_bytes())
    pool = descriptor_pool.DescriptorPool()
    for file_descriptor in files.file:
        pool.Add(file_descriptor)
    message = pool.FindMessageTypeByName("android.security.fsverity.FSVerityDigests")
    # Android's generated Python uses protobuf 6; the build host may have protobuf 3.
    # Descriptor-based construction retains the upstream schema without importing
    # generated code that requires a different runtime version.
    if hasattr(message_factory, "GetMessageClass"):
        return message_factory.GetMessageClass(message)
    return message_factory.MessageFactory(pool).GetPrototype(message)


def baseline_versions(aapt2, baseline, partition="system"):
    badging = run([aapt2, "dump", "badging", baseline])
    package = re.search(r"^package: name='([^']+)' versionCode='([0-9]+)' "
                        r"versionName='([^']*)'", badging, re.MULTILINE)
    sdk = re.search(r"^minSdkVersion:'([0-9]+)'", badging, re.MULTILINE)
    if package is None or sdk is None:
        raise ValueError("Cannot read the baseline BuildManifest package/version")
    if package.group(1) != "com.android.security.fsverity_metadata." + partition:
        raise ValueError("Expected the " + partition + " partition's baseline BuildManifest")
    return package.group(2), package.group(3), sdk.group(1)


def payload_files(root, names, partition="system"):
    if partition not in ("system", "system_ext"):
        raise ValueError("Unsupported BuildManifest partition: " + partition)
    selected = {}
    for name in names:
        relative = PurePosixPath(name)
        if (relative.is_absolute() or ".." in relative.parts
                or relative.as_posix() != name
                or (relative.parts[:2] != (partition, "framework")
                    and not (partition == "system" and name == "system/etc/boot-image.prof"))
                or name.endswith(".fsv_meta")):
            raise ValueError("Expected a product-relative framework input: " + name)
        if name in selected:
            raise ValueError("Duplicate framework input: " + name)
        source = root / name
        if root not in source.resolve().parents or not source.is_file():
            raise ValueError("Framework input is missing or outside the payload: " + name)
        # Inputs are staged regular files. Do not modify a source through a link.
        metadata = Path(str(source) + ".fsv_meta")
        if source.is_symlink() or metadata.is_symlink():
            raise ValueError("Framework payload and metadata must not be symlinks: " + name)
        selected[name] = source
    return selected


def build_manifest(android, out, baseline, payload_root, names, output, key_base,
                   partition="system"):
    android = android.resolve()
    out = out.resolve()
    baseline = baseline.resolve()
    payload_root = payload_root.resolve()
    output = output.absolute()
    key_base = key_base.resolve()
    host = out / "host/linux-x86"
    apk_signature = Path(str(output) + ".idsig")
    if output.exists() or apk_signature.exists():
        raise FileExistsError("BuildManifest output already exists: " + str(output))
    selected = payload_files(payload_root, names, partition)
    if not selected:
        raise ValueError("At least one framework input is required")
    version_code, version_name, min_sdk = baseline_versions(host / "bin/aapt2", baseline, partition)
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".manifest-", dir=output.parent) as temporary:
        work = Path(temporary)
        manifest = load_manifest_type(android, host, work)()
        with zipfile.ZipFile(baseline) as archive:
            manifest.ParseFromString(archive.read("assets/build_manifest.pb"))
        # A narrow replacement must not silently add a new framework dependency.
        for name in selected:
            if name not in manifest.digests:
                raise ValueError("Framework input is absent from the baseline manifest: " + name)
            if manifest.digests[name].hash_alg != "sha256":
                raise ValueError("Unsupported baseline digest algorithm: " + name)
        for name, source in selected.items():
            run([host / "bin/fsverity_metadata_generator", "--fsverity-path",
                 host / "bin/fsverity", "--signature", "none", "--hash-alg", "sha256",
                 "--output", str(source) + ".fsv_meta", source])
            digest = bytes.fromhex(run([host / "bin/fsverity", "digest", source,
                                        "--compact", "--hash-alg", "sha256"]).strip())
            if len(digest) != 32:
                raise ValueError("Invalid fs-verity digest for " + name)
            manifest.digests[name].digest = digest
        assets = work / "assets"
        assets.mkdir()
        (assets / "build_manifest.pb").write_bytes(
            manifest.SerializeToString(deterministic=True))
        signed = work / "BuildManifest.apk"
        run([host / "bin/aapt2", "link", "-o", signed, "-A", assets,
             "-I", out / "target/common/obj/APPS/framework-res_intermediates/package-export.apk",
             "--min-sdk-version", min_sdk, "--version-code", version_code,
             "--version-name", version_name,
             "--manifest", android / "system/security/fsverity/AndroidManifest.xml",
             "--rename-manifest-package", "com.android.security.fsverity_metadata." + partition])
        # Use the same signer and certificate inputs as the normal Android rule.
        # V4 also emits the idsig consumed with BuildManifest by CompOS.
        run([android / "prebuilts/jdk/jdk21/linux-x86/bin/java", "-jar",
             host / "framework/apksigner.jar", "sign", "--in", signed,
             "--cert", str(key_base) + ".x509.pem", "--key", str(key_base) + ".pk8",
             "--v4-signing-enabled", "true"])
        signature = Path(str(signed) + ".idsig")
        if not signature.is_file():
            raise FileNotFoundError("apksigner did not produce the BuildManifest idsig")
        signed.replace(output)
        signature.replace(apk_signature)
    return output, apk_signature


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android", type=Path, required=True)
    parser.add_argument("--out-dir", type=Path,
                        help="Android output directory; defaults to TREE/out-pixelos-user")
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--payload-root", type=Path, required=True)
    parser.add_argument("--framework-file", action="append", required=True,
                        help="Product-relative staged file, repeat for each replacement")
    parser.add_argument("--output", type=Path, required=True,
                        help="New BuildManifest.apk path; .idsig is emitted beside it")
    parser.add_argument("--key-base", type=Path,
                        help="Android signing key basename; defaults to this ROM's testkey")
    parser.add_argument("--partition", choices=("system", "system_ext"), default="system")
    args = parser.parse_args()
    paths = build_manifest(
        args.android, args.out_dir or args.android / "out-pixelos-user", args.baseline,
        args.payload_root, args.framework_file, args.output,
        args.key_base or args.android / "build/make/target/product/security/testkey", args.partition)
    for path in paths:
        print(path)


if __name__ == "__main__":
    main()
