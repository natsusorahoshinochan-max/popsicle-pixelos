#!/usr/bin/env python3
"""Derive the fixed OEM app_domain ptrace guards for the actual build variant.

Every neverallow remains intact. Only fifteen private, unshared source-set
expressions may acquire the llkd exclusion produced by the fixed AOSP macro for
userdebug/eng. This expands debug watchdog access and is not a strict-policy pass.
The original firmware is never modified; output creation is exclusive.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import subprocess


APPS = {
    "278": "vendor_cacertservice_app", "288": "vendor_cs_app",
    "309": "vendor_embmssl_app", "342": "vendor_imshelper_app",
    "352": "vendor_poweroffalarm_app", "358": "vendor_qtidataservices_app",
    "367": "vendor_timeservice_app", "371": "vendor_tzas_app",
    "451": "vendor_perfdump_app", "455": "vendor_powerservice_app",
    "472": "vendor_qms_app", "513": "vendor_powermodule_app",
    "518": "theme", "544": "mslg_app", "571": "cameramind_app",
}
MACRO_APP = "popsicle_contract_app"


def macro_exclusions(m4: Path, macros: Path, variant: str) -> set[str]:
    """Read the actual m4 producer, including its user-build suppression markers."""
    if variant not in {"user", "userdebug", "eng"}:
        raise ValueError("unknown build variant")
    result = subprocess.run(
        [str(m4), "-Dtarget_build_variant=" + variant, str(macros), "-"],
        input=f"app_domain({MACRO_APP})\n", capture_output=True, text=True, check=True,
    )
    policy = re.sub(r"#[^\n]*", "", result.stdout)
    guards = re.findall(
        r"neverallow\s*\{([^{}]+)\}\s*" + MACRO_APP + r":process\s+ptrace\s*;",
        policy,
    )
    if len(guards) != 1:
        raise ValueError("app_domain must produce exactly one ptrace guard")
    tokens = guards[0].split()
    expected = {"domain", "-" + MACRO_APP, "-crash_dump", "-runas_app", "-simpleperf"}
    if variant != "user":
        expected.add("-llkd")
    if set(tokens) != expected or len(tokens) != len(expected):
        raise ValueError("fixed app_domain ptrace contract changed")
    return {token[1:] for token in tokens if token.startswith("-")}


def derive(data: bytes, variant: str) -> tuple[bytes, int]:
    if variant not in {"user", "userdebug", "eng"}:
        raise ValueError("unknown build variant")
    lines = data.splitlines(keepends=True)
    tokens = Counter(re.findall(rb"[A-Za-z_][A-Za-z_0-9]*", data))
    replacements = {}
    for number, app in APPS.items():
        attribute = f"base_typeattr_{number}_202504"
        declaration = f"(typeattribute {attribute})\n".encode()
        expression = (f"(typeattributeset {attribute} (and (domain) (not "
                      f"(crash_dump_202504 runas_app_202504 simpleperf_202504 {app}))))\n").encode()
        guard = f"(neverallow {attribute} {app} (process (ptrace)))\n".encode()
        # Exactly the declaration, set definition and single guard may refer to
        # this attribute. Never broaden a set also used by another policy rule.
        if tokens[attribute.encode()] != 3 or any(lines.count(line) != 1 for line in
                                                (declaration, expression, guard)):
            raise ValueError(f"unexpected or shared OEM app guard: {app}")
        if variant != "user":
            replacements[expression] = expression.replace(b"(not (", b"(not (llkd ", 1)
    return b"".join(replacements.get(line, line) for line in lines), len(replacements)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m4", type=Path, required=True)
    parser.add_argument("--macros", type=Path, required=True)
    parser.add_argument("--build-variant", choices=("user", "userdebug", "eng"), required=True)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    # Verify both sides of the producer contract, not just the requested variant.
    macro_exclusions(args.m4, args.macros, "user")
    macro_exclusions(args.m4, args.macros, "userdebug")
    if args.build_variant == "eng":
        macro_exclusions(args.m4, args.macros, "eng")
    candidate, changed = derive(args.source.read_bytes(), args.build_variant)
    with args.output.open("xb") as output:
        output.write(candidate)
    print(json.dumps({"changed_private_sets": changed, "variant": args.build_variant,
                      "status": "candidate; full strict and device validation pending"}))


if __name__ == "__main__":
    main()
