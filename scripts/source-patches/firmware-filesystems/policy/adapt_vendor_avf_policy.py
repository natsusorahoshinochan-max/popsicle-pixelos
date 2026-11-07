#!/usr/bin/env python3
"""Restore the fixed A17 AVF vendor launcher contract in a separate OEM candidate.

Update four old transition rules to the real *_vendor domains. Add the fixed
vendor-use macro's process-group cleanup and crashdump-read permissions. All
existing communication, mappings and neverallow rules remain. The complementary
platform HAL client macros live in the device product policy and must be built;
this transform alone is not a complete AVF or strict-policy acceptance result.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

CALLER = "vendor_avf_qcvm_manager"
MANAGERS = ("virtualizationmanager", "early_virtmgr")
ADDITIONS = (
    f"(allow {CALLER} crosvm_domain (process (sigkill)))\n".encode(),
    f"(allow {CALLER} virtualizationservice_data_file (file (read getattr)))\n".encode(),
)


def validate_producer(m4: Path, globals_file: Path, macros: Path) -> None:
    result = subprocess.run([str(m4), "-Dtarget_build_variant=userdebug",
                             "-Dtarget_full_treble=true", str(globals_file), str(macros), "-"],
        input=f"virtualizationservice_vendor_use({CALLER})\nearly_virtmgr_vendor_use({CALLER})\n",
        capture_output=True, text=True, check=True)
    source = re.sub(r"#[^\n]*", "", result.stdout)
    statements = [" ".join(statement.split()) for statement in source.split(";")]
    expected = [f"allow {CALLER} crosvm_domain:process sigkill",
                f"allow {CALLER} virtualizationservice_data_file:file {{ getattr read }}"]
    for manager in MANAGERS:
        expected.extend([f"allow {CALLER} {manager}_vendor:process transition",
            f"type_transition {CALLER} {manager}_exec:process {manager}_vendor"])
    if any(statements.count(statement) != 1 for statement in expected):
        raise ValueError("fixed AVF vendor-use producer contract changed")


def adapt(data: bytes) -> tuple[bytes, int]:
    if not data.endswith(b"\n"):
        raise ValueError("OEM CIL must end with a newline")
    lines = data.splitlines(keepends=True)
    replacements = {}
    for manager in MANAGERS:
        allow = f"(allow {CALLER} {manager}_202504 (process (transition)))\n".encode()
        transition = f"(typetransition {CALLER} {manager}_exec_202504 process {manager})\n".encode()
        if lines.count(allow) != 1 or lines.count(transition) != 1:
            raise ValueError(f"unexpected OEM launcher transition: {manager}")
        replacements[allow] = allow.replace(f"{manager}_202504".encode(), f"{manager}_vendor".encode())
        replacements[transition] = transition.replace(f"process {manager})".encode(),
                                                      f"process {manager}_vendor)".encode())
    if any(rule in lines for rule in ADDITIONS):
        raise ValueError("AVF supplementary contract already present")
    return b"".join(replacements.get(line, line) for line in lines) + b"".join(ADDITIONS), 4


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m4", required=True, type=Path)
    parser.add_argument("--global-macros", required=True, type=Path)
    parser.add_argument("--macros", required=True, type=Path)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    validate_producer(args.m4, args.global_macros, args.macros)
    result, count = adapt(args.source.read_bytes())
    with args.output.open("xb") as output:
        output.write(result)
    print(json.dumps({"changed_transition_rules": count, "added_macro_rules": len(ADDITIONS),
                      "status": "candidate; platform HAL macros, strict and runtime checks required"}))


if __name__ == "__main__":
    main()
