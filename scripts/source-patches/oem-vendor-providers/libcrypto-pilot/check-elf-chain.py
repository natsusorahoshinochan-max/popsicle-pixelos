#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Check the OEM crypto pair and current staged direct consumers with Android's checker."""

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--official-filesystems", required=True, type=Path)
    parser.add_argument("--soong-variables", required=True, type=Path,
                        help="actual product-generated Soong variables used by this build")
    args = parser.parse_args()
    top = args.source_root.resolve(strict=True)
    official = args.official_filesystems.resolve(strict=True)
    product = top / "out-user-clean-20260909/target/product/popsicle"
    stage = product / "vendor"
    checker = top / "build/make/tools/check_elf_file.py"
    llvm = top / "prebuilts/clang/host/linux-x86/clang-r596125/bin/llvm-readobj"
    spec = importlib.util.spec_from_file_location("android_elf", checker)
    android_elf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(android_elf)
    candidate = official / "vendor/lib64/libcrypto.so"
    inputs = {}

    def remember(path):
        stamp = (path.stat().st_size, path.stat().st_mtime_ns)
        if path in inputs and inputs[path] != stamp:
            raise SystemExit("an ELF input changed during the check")
        inputs[path] = stamp
        return path

    def read(path):
        return android_elf.ELFParser.open(str(remember(path)), str(llvm))

    variables_path = remember(args.soong_variables.resolve(strict=True))
    variables = json.loads(variables_path.read_text())
    page_size = variables.get("DeviceMaxPageSizeSupported")
    if (page_size not in ("4096", "16384", "65536")
            or variables.get("DeviceCheckPrebuiltMaxPageSize") is not True):
        raise SystemExit("missing/unsupported product page size or disabled strict ELF check")

    def dependency(name):
        if name == "libcrypto.so":
            return remember(candidate)
        if name in {"libc.so", "libm.so", "libdl.so"}:
            library = name.removesuffix(".so")
            return remember(top / "out-user-clean-20260909/soong/.intermediates/bionic" / library / library
                            / "android_arm64_armv8-a-branchprot_oryon_shared" / name)
        for partition in ("vendor", "system"):
            path = product / partition / "lib64" / name
            if path.is_file() and not path.is_symlink():
                return remember(path)
        raise SystemExit("missing actual built dependency input: " + name)

    paths = sorted(p for p in stage.rglob("*") if p.is_file() and not p.is_symlink())
    tests = [candidate, official / "vendor/lib64/libssl.so"]
    scanned = 0
    for path in paths:
        remember(path)
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        elf = read(path)
        scanned += 1
        if "libcrypto.so" in elf.dt_needed:
            tests.append(path)
    results = []
    for path in tests:
        elf = read(path)
        command = [sys.executable, str(checker), "--llvm-readobj", str(llvm),
                   "--max-page-size", page_size]
        if path.suffix == ".so":
            command += ["--soname", path.name]
        for name in elf.dt_needed:
            command += ["--shared-lib", str(dependency(name))]
        command.append(str(path))
        run = subprocess.run(command, capture_output=True, text=True, check=False)
        results.append({"path": str(path), "command": command,
                        "exit_code": run.returncode, "stdout": run.stdout, "stderr": run.stderr})
    if paths != sorted(p for p in stage.rglob("*") if p.is_file() and not p.is_symlink()):
        raise SystemExit("staging membership changed during the check; discard this run")
    for path, stamp in inputs.items():
        if (path.stat().st_size, path.stat().st_mtime_ns) != stamp:
            raise SystemExit("an input changed during the check; discard this run")
    print(json.dumps({"scope": "OEM crypto/SSL plus current staging direct ELF consumers; "
                     "not a product linker namespace or runtime test",
                      "stage_elf_scanned": scanned, "tests": results,
                      "soong_variables": str(variables_path), "max_page_size": page_size,
                      "inputs_stable_during_read": True}, indent=2))
    if any(result["exit_code"] for result in results):
        raise SystemExit("one or more strict ELF checks failed")


if __name__ == "__main__":
    main()
