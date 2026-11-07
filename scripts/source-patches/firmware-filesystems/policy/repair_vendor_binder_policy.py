#!/usr/bin/env python3
"""Repair two proven service-label/process-domain mixups in the fixed OEM CIL.

This creates a separate candidate, never edits the firmware input. It does not
remove assertions or grant a service label domain membership. Full strict policy
compilation and device validation remain separate, mandatory checks.
"""

import argparse
from collections import Counter
import json
from pathlib import Path
import re


SERVERS = {
    "hal_mediaeventgatherservice_service": "hal_mediaeventgatherservice_default",
    "hal_visdisplaysrv_service": "hal_visdisplaysrv_default",
}
EXPECTED = Counter({
    ("hal_mediaeventgatherservice_service", "binder"): 52,
    ("hal_mediaeventgatherservice_service", "fd"): 26,
    ("hal_visdisplaysrv_service", "binder"): 2,
})
ALLOW = re.compile(rb"\(allow (\S+) (\S+) \((binder|fd) \(([^()]*)\)\)\)")


def rewrite_rule(line: bytes) -> tuple[bytes, tuple[str, str] | None]:
    """Change only process endpoints; retain permissions and all other bytes."""
    body = line.removesuffix(b"\n")
    match = ALLOW.fullmatch(body)
    if match is None:
        return line, None
    source, target, kind, _ = match.groups()
    replacements = [key for key in SERVERS if key.encode() in (source, target)]
    if not replacements:
        return line, None
    if len(replacements) != 1 or source == target:
        raise ValueError("unexpected service-to-service process rule")
    key = replacements[0]
    start, end = match.span(1 if source == key.encode() else 2)
    return line[:start] + SERVERS[key].encode() + line[end:], (key, kind.decode())


def repair(data: bytes) -> tuple[bytes, Counter]:
    for service, server in SERVERS.items():
        declaration = f"(typeattributeset {service.removesuffix('_service')}_server ({server}))\n"
        if data.count(declaration.encode()) != 1:
            raise ValueError(f"unexpected OEM server declaration for {service}")
    counts = Counter()
    result = []
    for line in data.splitlines(keepends=True):
        changed, key = rewrite_rule(line)
        result.append(changed)
        if key is not None:
            counts[key] += 1
    if counts != EXPECTED:
        raise ValueError(f"unexpected fixed-OEM process rule counts: {dict(counts)}")
    return b"".join(result), counts


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    candidate, counts = repair(args.source.read_bytes())
    # Exclusive creation rejects existing outputs, aliases and dangling symlinks.
    with args.output.open("xb") as output:
        output.write(candidate)
    print(json.dumps({"changed_rules": sum(counts.values()),
                      "status": "candidate; strict compilation and runtime validation pending"}))


if __name__ == "__main__":
    main()
