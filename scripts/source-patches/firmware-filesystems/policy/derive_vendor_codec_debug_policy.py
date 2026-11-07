#!/usr/bin/env python3
"""Preserve the OEM codec network guards while restoring its debug su exception.

The same-version QSSI mediacodec.te is the producer: user forbids all TCP peers,
userdebug/eng excludes su for Binder-over-TCP debugging. No permission is added;
all existing neverallow permissions, UDP/raw-IP and execution guards remain.
Only separate candidate output is permitted. Full strict/runtime checks follow.
"""
import argparse
import json
from pathlib import Path
import re
import subprocess

PEERS = "popsicle_mediacodec_tcp_peers"
PERMISSIONS = ("ioctl read write create getattr setattr lock relabelfrom relabelto append map "
               "bind connect listen accept getopt setopt shutdown recvfrom sendto name_bind "
               "node_bind name_connect")
GUARD = f"(neverallow mediacodec domain (tcp_socket ({PERMISSIONS})))\n".encode()


def validate_producer(m4: Path, macros: Path, codec: Path, variant: str) -> None:
    if variant not in {"user", "userdebug", "eng"}:
        raise ValueError("unknown build variant")
    result = subprocess.run([str(m4), "-Dtarget_build_variant=" + variant,
                             str(macros), str(codec)], capture_output=True, text=True, check=True)
    policy = re.sub(r"#[^\n]*", "", result.stdout)
    guards = re.findall(r"neverallow\s+mediacodec\s*\{([^{}]*)\}:tcp_socket\s*\*\s*;", policy)
    expected = ["domain"] if variant == "user" else ["domain", "-su"]
    if len(guards) != 1 or guards[0].split() != expected:
        raise ValueError("same-version codec network producer contract changed")


def derive(data: bytes, variant: str) -> tuple[bytes, int]:
    if variant not in {"user", "userdebug", "eng"}:
        raise ValueError("unknown build variant")
    if data.splitlines(keepends=True).count(GUARD) != 1 or PEERS.encode() in data:
        raise ValueError("unexpected OEM codec guard or existing derived peer attribute")
    if variant == "user":
        return data, 0
    declaration = (f"(typeattribute {PEERS})\n"
                   f"(typeattributeset {PEERS} (and (domain) (not (su))))\n").encode()
    guard = GUARD.replace(b"mediacodec domain ", f"mediacodec {PEERS} ".encode(), 1)
    return b"".join(declaration + guard if line == GUARD else line
                    for line in data.splitlines(keepends=True)), 1


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--m4", required=True, type=Path)
    parser.add_argument("--macros", required=True, type=Path)
    parser.add_argument("--codec-source", required=True, type=Path)
    parser.add_argument("--build-variant", choices=("user", "userdebug", "eng"), required=True)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    for variant in {"user", "userdebug", args.build_variant}:
        validate_producer(args.m4, args.macros, args.codec_source, variant)
    data, changed = derive(args.source.read_bytes(), args.build_variant)
    with args.output.open("xb") as output:
        output.write(data)
    print(json.dumps({"changed_peer_guards": changed, "variant": args.build_variant,
                      "status": "candidate; full strict and device validation pending"}))


if __name__ == "__main__":
    main()
