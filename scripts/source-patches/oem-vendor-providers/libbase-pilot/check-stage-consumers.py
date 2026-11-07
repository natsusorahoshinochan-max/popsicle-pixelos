#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Read-only libbase import/export comparison for the existing vendor staging."""

import argparse
import importlib.util
import json
from pathlib import Path
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--vendor-stage", required=True, type=Path)
    parser.add_argument("--official-filesystems", required=True, type=Path)
    args = parser.parse_args()
    top = args.source_root.resolve(strict=True)
    stage = args.vendor_stage.resolve(strict=True)
    official = args.official_filesystems.resolve(strict=True)
    llvm = top / "prebuilts/clang/host/linux-x86/clang-r596125/bin/llvm-readobj"
    spec = importlib.util.spec_from_file_location(
        "android_elf", top / "build/make/tools/check_elf_file.py")
    android_elf = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(android_elf)

    def read(path):
        return android_elf.ELFParser.open(str(path), str(llvm))

    def files():
        return sorted(p for p in stage.rglob("*") if p.is_file() and not p.is_symlink())

    def stamps(paths):
        return {str(p): (p.stat().st_size, p.stat().st_mtime_ns) for p in paths}

    def exports(elf):
        return sorted(name + ("@" + version if version else "")
                      for name, versions in elf.exported.items() for version in versions)

    candidate_path = official / "vendor/lib64/libbase.so"
    paths = files()
    before = stamps(paths + [candidate_path])
    source = read(stage / "lib64/libbase.so")
    candidate = read(candidate_path)
    result = {
        "stage": str(stage),
        "candidate": str(candidate_path),
        "candidate_soname": candidate.dt_soname,
        "candidate_needed": candidate.dt_needed,
        "candidate_exports": exports(candidate),
        "source_exports": exports(source),
        "elf_scanned": 0,
        "direct_consumers": [],
        "apex_inputs": [],
        "scope": "Import/export set compatibility, not runtime symbol binding or behavior. "
                 "APEX payloads, absent outputs, dlopen/dlsym and linker namespaces are separate.",
    }
    missing_any = False
    for path in paths:
        if path.suffix in {".apex", ".capex"}:
            result["apex_inputs"].append(str(path))
        with path.open("rb") as stream:
            if stream.read(4) != b"\x7fELF":
                continue
        elf = read(path)
        result["elf_scanned"] += 1
        if "libbase.so" not in elf.dt_needed:
            continue
        required = {"strong": [], "weak": []}
        missing = {"strong": [], "weak": []}
        # The fixed checker's public imported map intentionally omits WEAK.
        # Reuse its raw symbol/name parser to inspect both binding categories.
        dump = subprocess.check_output([str(llvm), "--dyn-symbols", str(path)], text=True)
        for symbol in android_elf.ELFParser._parse_dynamic_symbols_internal(iter(dump.splitlines())):
            if symbol["Section"] != "Undefined":
                continue
            name, version = android_elf.ELFParser._parse_symbol_name(symbol["Name"])
            if not name or not android_elf.Checker._find_symbol(source, name, version):
                continue
            binding = "weak" if symbol["Binding"] == "Weak" else "strong"
            display = name + ("@" + version if version else "")
            required[binding].append(display)
            if not android_elf.Checker._find_symbol(candidate, name, version):
                missing[binding].append(display)
                missing_any = True
        result["direct_consumers"].append({
            "path": str(path.relative_to(stage)),
            "needed": elf.dt_needed,
            "imports_exported_by_source_libbase": {k: sorted(v) for k, v in required.items()},
            "missing_from_oem_libbase": {k: sorted(v) for k, v in missing.items()},
        })
    if paths != files() or before != stamps(paths + [candidate_path]):
        raise SystemExit("inputs changed during the read-only audit; discard this run")
    result["inputs_stable_during_read"] = True
    print(json.dumps(result, indent=2))
    if missing_any:
        raise SystemExit("current staging imports source-libbase symbols missing from the OEM input")


if __name__ == "__main__":
    main()
