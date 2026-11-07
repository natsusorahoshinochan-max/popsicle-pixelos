#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compare camera-versus-priv_app_36 deltas in two compiled canonical CIL files.

Input must be output of the same tree's binary-policy-to-CIL exporter. This is
not a source CIL compiler or a global policy verifier. Unknown forms fail closed.
The caller separately proves that the candidate preserves every original live
form and that both binaries passed the real compiler/neverallow checks.

Attribute identifiers are expanded. AV permissions and xperm intervals are
unioned, including reverse edges. Roles, named transitions and partially
evaluated type projections of constraints are compared too. Camera and baseline
namespaces are SWAPPED for the camera footprint: collapsing both names would
hide missing new-to-old edges. Each policy's own baseline is then subtracted,
so unrelated live/KSU baseline permissions need not equal the formal policy.
"""
import argparse
from collections import defaultdict
from dataclasses import dataclass, field
import json
from pathlib import Path
import re
import sys


SUFFIXES = ("", "_block_io_uring", "_devpts", "_userfaultfd", "_wrapfd")
BASE = frozenset("priv_app_36" + suffix for suffix in SUFFIXES)
CAMERA = frozenset("popsicle_camera_app" + suffix for suffix in SUFFIXES)
SWAP = dict(zip(sorted(BASE), sorted(CAMERA)))
SWAP.update({value: key for key, value in list(SWAP.items())})
AV = frozenset(("allow", "auditallow", "dontaudit"))
XAV = frozenset(("allowx", "auditallowx", "dontauditx"))
TRANSITIONS = frozenset(("typetransition", "typechange", "typemember"))
CONSTRAINTS = frozenset(("constrain", "mlsconstrain", "validatetrans", "mlsvalidatetrans"))
DECLARATIONS = frozenset(("type", "typeattribute", "typeattributeset", "typealias", "typealiasactual"))
# These canonical binary declarations cannot add per-type access. Context forms
# are accepted only when they contain no focal type, alias or attribute member.
INDEPENDENT = frozenset((
    "handleunknown", "mls", "policycap", "class", "classorder", "common",
    "classcommon", "sid", "sidorder", "role", "user", "userrole", "userlevel",
    "userrange", "sensitivity", "sensitivityorder", "category", "categoryorder",
    "sensitivitycategory", "defaultuser", "defaultrole", "defaulttype", "defaultrange",
    "sidcontext", "fsuse", "genfscon", "portcon", "nodecon", "netifcon",
    "ibpkeycon", "ibendportcon",
))
SUPPORTED = AV | XAV | TRANSITIONS | CONSTRAINTS | DECLARATIONS | INDEPENDENT | {"roletype", "typepermissive"}
TOKEN = re.compile(r'\s+|;[^\n]*|"(?:\\.|[^"\\])*"|[()]|[^\s();"]+')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def forms(text):
    """Strict tokenization; quoted atoms remain quoted and are never type names."""
    stack, offset = [], 0
    for match in TOKEN.finditer(text):
        require(match.start() == offset, "invalid CIL token")
        offset = match.end()
        token = match.group()
        if token.isspace() or token.startswith(";"):
            continue
        if token == "(":
            stack.append([])
        elif token == ")":
            require(stack, "unbalanced CIL close")
            value = tuple(stack.pop())
            if stack:
                stack[-1].append(value)
            else:
                require(value, "empty top-level CIL form")
                yield value
        else:
            require(stack, "atom outside CIL form")
            stack[-1].append(token)
    require(offset == len(text) and not stack, "incomplete CIL form")


def atoms(value):
    if isinstance(value, str):
        yield value
    else:
        for item in value:
            yield from atoms(item)


def merge(intervals):
    result = []
    for low, high in sorted(intervals):
        if result and low <= result[-1][1] + 1:
            result[-1] = (result[-1][0], max(high, result[-1][1]))
        else:
            result.append((low, high))
    return tuple(result)


def subtract(left, right):
    result = []
    for low, high in merge(left):
        for start, end in merge(right):
            if end < low:
                continue
            if start > high:
                break
            if start > low:
                result.append((low, start - 1))
            low = max(low, end + 1)
        if low <= high:
            result.append((low, high))
    return tuple(result)


def xintervals(expr):
    if isinstance(expr, str):
        require(re.fullmatch(r"0x[0-9a-fA-F]+|[0-9]+", expr), "unsupported xperm atom")
        value = int(expr, 16 if expr.startswith("0x") else 10)
        require(0 <= value <= 0xffff, "xperm out of range")
        return ((value, value),)
    if expr[0] == "range":
        require(len(expr) == 3, "invalid xperm range")
        low, high = xintervals(expr[1])[0][0], xintervals(expr[2])[0][0]
        require(low <= high, "reversed xperm range")
        return ((low, high),)
    return merge(pair for item in expr for pair in xintervals(item))


def boolean(operator, values):
    """Sound canonical simplifications; unrecognized equivalences reject safely."""
    if operator == "not":
        require(len(values) == 1, "invalid constraint not")
        return not values[0] if isinstance(values[0], bool) else ("not", values[0])
    identity = operator == "and"
    flattened = set()
    for value in values:
        if isinstance(value, bool):
            if value != identity:
                return value
        elif isinstance(value, tuple) and value[0] == operator:
            flattened.update(value[1:])
        else:
            flattened.add(value)
    if not flattened:
        return identity
    ordered = tuple(sorted(flattened, key=repr))
    return ordered[0] if len(ordered) == 1 else (operator,) + ordered


@dataclass
class Footprint:
    facts: set = field(default_factory=set)
    xperms: dict = field(default_factory=lambda: defaultdict(list))

    def minus(self, other):
        result = set(self.facts - other.facts)
        for key, intervals in self.xperms.items():
            difference = subtract(intervals, other.xperms.get(key, ()))
            if difference:
                result.add(key + (difference,))
        return result


class Policy:
    def __init__(self, text):
        self.forms = list(forms(text))
        self.types, self.attributes, self.aliases = set(), {}, {}
        self.cache, self.resolving = {}, set()
        for form in self.forms:
            kind = form[0]
            require(kind in SUPPORTED, "unsupported canonical construct: " + str(kind))
            if kind in ("type", "typeattribute", "typealias"):
                require(len(form) == 2 and isinstance(form[1], str), "invalid type declaration")
                name = form[1]
                require(name not in self.types and name not in self.attributes and name not in self.aliases,
                        "duplicate type/attribute/alias: " + name)
                if kind == "type":
                    self.types.add(name)
                elif kind == "typeattribute":
                    self.attributes[name] = []
                else:
                    self.aliases[name] = None
        for form in self.forms:
            if form[0] == "typeattributeset":
                require(len(form) == 3 and form[1] in self.attributes, "undeclared attribute")
                self.attributes[form[1]].append(form[2])
            elif form[0] == "typealiasactual":
                require(len(form) == 3 and form[1] in self.aliases and self.aliases[form[1]] is None,
                        "invalid type alias definition")
                self.aliases[form[1]] = form[2]
        for name in self.types | set(self.attributes) | set(self.aliases):
            self.select(name)
            if name.startswith(("priv_app_36", "popsicle_camera_app")):
                require(name in BASE | CAMERA, "unexpected camera/baseline namespace member: " + name)

    def select(self, value):
        if isinstance(value, str):
            if value in self.types:
                return frozenset((value,))
            if value in self.cache:
                return self.cache[value]
            require(value not in self.resolving, "recursive type attribute/alias")
            self.resolving.add(value)
            if value in self.aliases:
                require(self.aliases[value] is not None, "undefined type alias")
                result = self.select(self.aliases[value])
            else:
                require(value in self.attributes, "unknown type selector: " + value)
                result = frozenset().union(*(self.select(expr) for expr in self.attributes[value]))
            self.resolving.remove(value)
            self.cache[value] = result
            return result
        require(value, "empty type expression")
        operator = value[0]
        if operator == "all":
            require(len(value) == 1, "invalid all type expression")
            return frozenset(self.types)
        if operator == "not":
            require(len(value) == 2, "invalid type complement")
            return frozenset(self.types) - self.select(value[1])
        if operator in ("and", "or", "xor"):
            require(len(value) >= 3, "invalid type boolean expression")
            result = self.select(value[1])
            for item in value[2:]:
                next_set = self.select(item)
                result = result & next_set if operator == "and" else result | next_set if operator == "or" else result ^ next_set
            return result
        return frozenset().union(*(self.select(item) for item in value))

    def condition(self, expr, variable, focal_type, normalize):
        require(isinstance(expr, tuple) and expr, "invalid constraint expression")
        operator = expr[0]
        if operator in ("and", "or", "not"):
            require(len(expr) >= 2, "empty constraint expression")
            return boolean(operator, [self.condition(item, variable, focal_type, normalize) for item in expr[1:]])
        require(operator in ("eq", "neq", "dom", "domby", "incomp") and len(expr) == 3,
                "unsupported constraint operator")
        left, right = expr[1:]
        if isinstance(left, str) and left in ("t1", "t2", "t3"):
            require(operator in ("eq", "neq"), "unsupported type comparison")
            if right in ("t1", "t2", "t3"):
                if left == right:
                    result = True
                elif left == variable or right == variable:
                    remaining = right if left == variable else left
                    result = ("in", remaining, (normalize(focal_type),))
                else:
                    result = ("eq",) + tuple(sorted((left, right)))
            else:
                members = self.select(right)
                result = focal_type in members if left == variable else ("in", left, tuple(sorted(map(normalize, members))))
            return boolean("not", [result]) if operator == "neq" else result
        require(isinstance(left, str) and isinstance(right, str)
                and re.fullmatch(r"[urhl][123]", left) and re.fullmatch(r"[urhl][123]", right),
                "unsupported non-type constraint operands")
        if operator in ("eq", "neq"):
            left, right = sorted((left, right))
        return (operator, left, right)

    def footprint(self, namespace, swap=False):
        require(namespace <= self.types, "incomplete five-type camera/baseline namespace")
        normalize = (lambda name: SWAP.get(name, name)) if swap else (lambda name: name)
        result = Footprint()

        def pairs(source, target):
            sources = self.select(source)
            if target == "self":
                return ((item, item) for item in sources & namespace)
            targets = self.select(target)
            return ((s, t) for s, t in
                    ({(s, t) for s in sources & namespace for t in targets}
                     | {(s, t) for s in sources for t in targets & namespace}))

        for form in self.forms:
            kind = form[0]
            if kind in AV | XAV:
                require(len(form) == 4 and isinstance(form[3], tuple), "invalid AV form")
                if kind in AV:
                    require(len(form[3]) == 2 and isinstance(form[3][1], tuple)
                            and all(isinstance(p, str) for p in form[3][1]), "invalid AV permissions")
                    object_class, permissions = form[3]
                    for source, target in pairs(form[1], form[2]):
                        result.facts.update((kind, normalize(source), normalize(target), object_class, p) for p in permissions)
                else:
                    require(len(form[3]) == 3 and form[3][0] in ("ioctl", "nlmsg"), "unsupported extended permission")
                    operation, object_class, expr = form[3]
                    intervals = xintervals(expr)
                    for source, target in pairs(form[1], form[2]):
                        result.xperms[(kind, normalize(source), normalize(target), operation, object_class)].extend(intervals)
            elif kind in TRANSITIONS:
                require(len(form) in (5, 6) and (kind == "typetransition" or len(form) == 5), "invalid type transition")
                require(len(form) == 5 or form[4].startswith('"'), "unquoted transition filename")
                output = self.select(form[-1])
                require(len(output) == 1, "transition output is not a concrete type")
                output_type = next(iter(output))
                edges = pairs(form[1], form[2])
                if output_type in namespace:
                    edges = ((s, t) for s in self.select(form[1]) for t in self.select(form[2]))
                for source, target in edges:
                    result.facts.add((kind, normalize(source), normalize(target), form[3],
                                      form[4] if len(form) == 6 else None, normalize(output_type)))
            elif kind == "roletype":
                require(len(form) == 3, "invalid roletype")
                for member in self.select(form[2]) & namespace:
                    result.facts.add((kind, form[1], normalize(member)))
            elif kind == "typepermissive":
                require(len(form) == 2, "invalid typepermissive")
                require(not self.select(form[1]) & namespace, "camera/baseline must be enforcing")
            elif kind in CONSTRAINTS:
                require(len(form) == 3, "invalid constraint form")
                if kind.endswith("validatetrans"):
                    require(isinstance(form[1], str), "invalid validatetrans class")
                    classes = ((form[1], None),)
                else:
                    require(isinstance(form[1], tuple) and len(form[1]) == 2
                            and isinstance(form[1][1], tuple), "invalid constraint permissions")
                    classes = tuple((form[1][0], perm) for perm in form[1][1])
                for member in namespace:
                    for variable in ("t1", "t2", "t3"):
                        projected = self.condition(form[2], variable, member, normalize)
                        for object_class, permission in classes:
                            result.facts.add((kind, object_class, permission, variable, normalize(member), projected))
            elif kind in INDEPENDENT:
                for atom in atoms(form[1:]):
                    if atom in self.types or atom in self.attributes or atom in self.aliases:
                        require(not self.select(atom) & namespace, "unsupported focal context/declaration: " + kind)
        return result

    def delta(self):
        baseline = self.footprint(BASE)
        camera = self.footprint(CAMERA, swap=True)
        return {"added": camera.minus(baseline), "removed": baseline.minus(camera)}


def compare(target, candidate):
    expected, actual = target.delta(), candidate.delta()
    differences = {}
    for direction in ("added", "removed"):
        for label, values in (("missing", expected[direction] - actual[direction]),
                              ("unexpected", actual[direction] - expected[direction])):
            if values:
                differences[direction + "_" + label] = sorted(values, key=repr)
    return expected, differences


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--candidate", required=True, type=Path)
    args = parser.parse_args()
    try:
        expected, differences = compare(Policy(args.target.read_text()), Policy(args.candidate.read_text()))
        report = {"status": "mismatch" if differences else "matched", "scope": "camera-relative-semantic-delta",
                  "expected_added": len(expected["added"]), "expected_removed": len(expected["removed"]),
                  "differences": {key: {"count": len(value), "examples": value[:12]} for key, value in differences.items()}}
        print(json.dumps(report, indent=2))
        return 1 if differences else 0
    except (ValueError, OSError) as error:
        print("camera policy comparison rejected: " + str(error), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
