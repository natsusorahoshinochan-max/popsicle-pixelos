#!/usr/bin/env python3
"""Repair the fixed OEM display-config Binder process endpoints in a private copy.

The actual composer executable registers the display-config AIDL service in
hal_graphics_composer_default. Its broader HAL server attribute has four domains
and is not an equivalent endpoint. Preserve old HIDL discovery and every guard;
this correction does not establish that the legacy HIDL service is registered.
"""
import argparse
from collections import Counter
import json
import re
from pathlib import Path

SERVICE = "vendor_hal_display_config_hwservice"
PROVIDER = "hal_graphics_composer_default"
CLIENTS = {"vendor_hal_citsensorservice_xiaomi_default": 1,
           "rild": 1, "vendor_hal_displayfeature_xiaomi_default": 2}


def expected_rules() -> Counter:
    result = Counter()
    for client, count in CLIENTS.items():
        for rule in (f"(allow {client} {SERVICE} (binder (call transfer)))\n",
                     f"(allow {SERVICE} {client} (binder (transfer)))\n",
                     f"(allow {client} {SERVICE} (fd (use)))\n"):
            result[rule.encode()] = count
    return result


def repair(data: bytes) -> bytes:
    lines = data.splitlines(keepends=True)
    expected = expected_rules()
    actual = Counter(line for line in lines if line in expected)
    if actual != expected:
        raise ValueError("fixed OEM display-config client contract changed")
    # Reject an unrecognized additional process rule instead of partially fixing
    # a different firmware. Service discovery/registration is deliberately kept.
    # Parse balanced CIL expressions, including nested permission expressions.
    # Quoted strings keep embedded semicolons; comments are parse-only omissions.
    stack = []
    found = Counter()
    token_pattern = rb'"(?:\\.|[^"\\])*"|;[^\n]*|[()]|[^\s();"]+'
    def render(form):
        return b"(" + b" ".join(render(x) if isinstance(x, list) else x for x in form) + b")"
    for match in re.finditer(token_pattern, data):
        token = match.group()
        if token.startswith(b";"):
            continue
        if token == b"(":
            stack.append([])
        elif token == b")":
            if not stack:
                raise ValueError("unbalanced CIL input")
            form = stack.pop()
            if (len(form) >= 4 and form[0] == b"allow"
                    and SERVICE.encode() in form[1:3]):
                for permission in form[3:]:
                    if (isinstance(permission, list) and permission
                            and permission[0] in (b"binder", b"fd")):
                        found[render(form) + b"\n"] += 1
            if stack:
                stack[-1].append(form)
        elif stack:
            stack[-1].append(token)
        else:
            raise ValueError("token outside CIL expression")
    if stack:
        raise ValueError("unbalanced CIL input")
    if found != expected:
        raise ValueError("unknown display-config process rule")
    return b"".join(line.replace(SERVICE.encode(), PROVIDER.encode())
                    if line in expected else line for line in lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    result = repair(args.source.read_bytes())
    with args.output.open("xb") as output:
        output.write(result)
    print(json.dumps({"changed_rules": 12, "provider": PROVIDER,
                      "status": "candidate; strict and real client validation required"}))


if __name__ == "__main__":
    main()
