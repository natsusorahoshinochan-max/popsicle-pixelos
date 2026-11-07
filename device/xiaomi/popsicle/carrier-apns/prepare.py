#!/usr/bin/env python3
"""Merge compatible stock APNs with the current PixelOS source baseline.

Run on the Linux build host with --android ANDROID --stock EXTRACTED_A17_ROOT.
The stock root must contain product/etc/apns-conf.xml from OS4.0.0.23.XPBCNXM.
Only private generated inputs are written; the public APN sources stay unchanged.
"""

import argparse
import copy
import gzip
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET


def document(rows):
    root = ET.Element("apns", version="8")
    root.extend(copy.deepcopy(row) for row in rows)
    ET.indent(root, space="  ")
    return ET.tostring(root, encoding="utf-8", xml_declaration=True)


def validate(data, schema, xmllint):
    return subprocess.run(
        [xmllint, "--nonet", "--noout", "--schema", str(schema), "-"],
        input=data, capture_output=True, check=False,
    )


def row_reference(index, row):
    # Report identity and reasons, not APN credentials.
    return {"stock_row": index, **{
        key: row.get(key, "")
        for key in ("carrier", "mcc", "mnc", "apn", "mvno_type", "mvno_match_data")
    }}


def endpoint(row):
    # This deliberately groups protocol/type/network variants together. Adding
    # a stock variant can otherwise merge into an existing TelephonyProvider
    # database row and overwrite baseline values. Keep the source baseline.
    return tuple(row.get(key, default) for key, default in (
        ("mcc", ""), ("mnc", ""), ("carrier_id", "-1"), ("apn", ""),
        ("mvno_type", ""), ("mvno_match_data", ""),
    ))


def schema_compatible(rows, schema, xmllint, excluded):
    """Validate batches, bisect only failed batches to identify rejected rows."""
    if not rows:
        return []
    result = validate(document([row for _, row in rows]), schema, xmllint)
    if result.returncode == 0:
        return rows
    if len(rows) == 1:
        index, row = rows[0]
        errors = result.stderr.decode("utf-8", errors="replace").splitlines()
        excluded.append({**row_reference(index, row), "reason": "schema_rejected",
                         "detail": errors[0] if errors else "XML schema validation failed"})
        return []
    middle = len(rows) // 2
    return (schema_compatible(rows[:middle], schema, xmllint, excluded)
            + schema_compatible(rows[middle:], schema, xmllint, excluded))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--android", required=True, type=Path)
    parser.add_argument("--stock", required=True, type=Path)
    parser.add_argument("--xmllint", default="xmllint")
    args = parser.parse_args()
    android = args.android.resolve()
    source = android / "vendor/apn"
    stock = args.stock.resolve() / "product/etc/apns-conf.xml"
    schema = source / "apns-conf.xsd"
    xmllint = shutil.which(args.xmllint)
    if not xmllint:
        parser.error("xmllint is required (the normal APN schema validator)")
    source_files = sorted(source.glob("*.xml"))
    if not source_files or not stock.is_file() or not schema.is_file():
        parser.error("missing vendor/apn sources, schema or stock product/etc/apns-conf.xml")

    # Use the same source expansion as the normal build, never its previous
    # output; repeat preparation therefore cannot import its own additions.
    env = dict(os.environ, XMLLINT=xmllint)
    baseline = subprocess.run(
        ["bash", str(source / "make-apns.sh"), *map(str, source_files)],
        capture_output=True, check=True, env=env,
    ).stdout
    result = validate(baseline, schema, xmllint)
    if result.returncode:
        raise RuntimeError("PixelOS source APNs fail their original schema:\n"
                           + result.stderr.decode("utf-8", errors="replace"))
    baseline_root = ET.fromstring(baseline)
    stock_root = ET.parse(stock).getroot()
    if baseline_root.tag != "apns" or stock_root.tag != "apns":
        raise ValueError("expected apns document roots")

    namespace = {"xs": "http://www.w3.org/2001/XMLSchema"}
    schema_root = ET.parse(schema).getroot()
    allowed = {item.attrib["name"] for item in schema_root.findall(
        "xs:complexType[@name='apn']/xs:attribute", namespace)}
    excluded = []
    candidates = []
    normalized = []
    for index, original in enumerate(stock_root, 1):
        row = copy.deepcopy(original)
        unsupported = sorted(set(row.attrib) - allowed)
        if row.tag != "apn" or len(row):
            excluded.append({**row_reference(index, row), "reason": "unsupported_node"})
            continue
        if unsupported:
            # Do not drop an OEM condition and accidentally broaden matching.
            excluded.append({**row_reference(index, row), "reason": "unsupported_attributes",
                             "attributes": unsupported})
            continue
        if bool(row.get("mvno_type")) != bool(row.get("mvno_match_data")):
            excluded.append({**row_reference(index, row), "reason": "incomplete_mvno_selector"})
            continue
        if "type" in row.attrib:
            # TelephonyProvider.getRow explicitly removes whitespace from type.
            value = re.sub(r"\s+", "", row.attrib["type"])
            if value != row.attrib["type"]:
                normalized.append({**row_reference(index, row), "field": "type",
                                   "reason": "TelephonyProvider removes whitespace"})
                row.set("type", value)
        candidates.append((index, row))

    compatible = schema_compatible(candidates, schema, xmllint, excluded)
    rows = list(baseline_root)
    baseline_endpoints = {endpoint(row) for row in rows}
    seen = {tuple(sorted(row.attrib.items())) for row in rows}
    added = []
    for index, row in compatible:
        exact = tuple(sorted(row.attrib.items()))
        if exact in seen:
            excluded.append({**row_reference(index, row), "reason": "duplicate"})
        elif endpoint(row) in baseline_endpoints:
            excluded.append({**row_reference(index, row),
                             "reason": "baseline_endpoint_preserved"})
        else:
            rows.append(row)
            seen.add(exact)
            added.append(row_reference(index, row))

    output = document(rows)
    result = validate(output, schema, xmllint)
    if result.returncode:
        raise RuntimeError("Merged APNs fail the original schema:\n"
                           + result.stderr.decode("utf-8", errors="replace"))
    output_dir = android / "vendor/xiaomi/popsicle-private/prebuilt/carrier-apns"
    output_dir.mkdir(parents=True, exist_ok=True)
    report = {
        "stock": str(stock), "baseline": [str(path) for path in source_files],
        "baseline_rows": len(baseline_root), "stock_rows": len(stock_root),
        "added_rows": len(added), "output_rows": len(rows),
        "policy": "Preserve baseline endpoints; append compatible stock endpoints. "
                  "Unsupported OEM conditions and schema-invalid rows are not widened. "
                  "Counts describe configuration, not tested carrier service.",
        "added": added, "excluded": excluded, "normalized": normalized,
    }
    outputs = {
        "apns-conf.xml": output,
        "NOTICE": (source / "LICENSES/Apache-2.0.txt").read_bytes() + b"\n"
                  + gzip.decompress((args.stock.resolve()
                                     / "product/etc/NOTICE.xml.gz").read_bytes()) + b"\n",
        "conversion-report.json": (json.dumps(report, indent=2, ensure_ascii=False) + "\n").encode(),
        "Android.bp": b'// Generated by device/xiaomi/popsicle/carrier-apns/prepare.py\n'
                      b'package {\n'
                      b'    default_applicable_licenses: ["popsicle_carrier_apns_notice"],\n'
                      b'}\n\n'
                      b'license {\n    name: "popsicle_carrier_apns_notice",\n'
                      b'    visibility: [":__subpackages__"],\n'
                      b'    license_kinds: ["SPDX-license-identifier-Apache-2.0", "legacy_notice"],\n'
                      b'    license_text: ["NOTICE"],\n}\n\n'
                      b'filegroup {\n    name: "popsicle_carrier_apns_data",\n'
                      b'    srcs: ["apns-conf.xml"],\n'
                      b'    visibility: ["//visibility:public"],\n}\n',
    }
    for name, data in outputs.items():
        with tempfile.NamedTemporaryFile(dir=output_dir, delete=False) as stream:
            temp_path = Path(stream.name)
            stream.write(data)
        temp_path.chmod(0o644)
        temp_path.replace(output_dir / name)
    print(f"APNs: baseline={len(baseline_root)}, added={len(added)}, "
          f"excluded={len(excluded)}, output={len(rows)}")
    print(f"Generated {output_dir}")


if __name__ == "__main__":
    main()
