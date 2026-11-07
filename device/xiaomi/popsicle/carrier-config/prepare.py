#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Convert matching stock popsicle carrier data into a private PixelOS RRO.

Usage: prepare.py ANDROID PROJECT STOCK
STOCK is the extracted, read-only OS4.0.0.23.XPBCNXM filesystem root.
The generated report records every omitted rule/value; it is not a device test.
"""

import argparse
import copy
import gzip
import itertools
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile


POLICY_KEYS = {"carrier_volte_globalization_enable", "carrier_volte_unavailable_bool"}
FILTERS = {"mcc", "mnc", "gid1", "gid2", "spn", "imsi", "device",
           "vendorSku", "hardwareSku", "board", "cid", "name", "sku"}


def decoded_xml(aapt, apk, resource):
    """Read aapt2's XML tree, preferring raw strings (not coerced MNC integers)."""
    result = subprocess.run(
        [str(aapt), "dump", "xmltree", str(apk), "--file", resource],
        check=True, text=True, capture_output=True,
    )
    stack = []
    root = None
    for line in result.stdout.splitlines():
        match = re.match(r"(\s*)E: (\S+)(?: .*)?$", line)
        if match:
            depth = len(match[1])
            node = ET.Element(match[2])
            while stack and stack[-1][0] >= depth:
                stack.pop()
            if stack:
                stack[-1][1].append(node)
            elif root is None:
                root = node
            else:
                raise ValueError("Multiple XML roots: " + resource)
            stack.append((depth, node))
            continue
        match = re.match(r'\s*A: ([\w-]+)=(.*)$', line)
        if match and stack:
            value = match[2]
            raw = re.search(r'\(Raw: "(.*)"\)$', value)
            if raw:
                value = raw[1]
            elif value.startswith('"') and value.endswith('"'):
                value = value[1:-1]
            elif not re.fullmatch(r"-?\d+|true|false", value):
                raise ValueError("Unsupported compiled value: " + line)
            stack[-1][1].set(match[1], value)
            continue
        match = re.match(r"\s*T: '(.*)'$", line)
        if match and stack:
            node = stack[-1][1]
            node.text = (node.text or "") + match[1]
            continue
        if line.strip():
            raise ValueError("Unsupported aapt XML syntax: " + line)
    if root is None or root.tag != "carrier_config_list":
        raise ValueError("Expected carrier_config_list: " + resource)
    return root


def convert_layer(root, source, supported, output, report, studio=False):
    for index, rule in enumerate(root):
        if rule.tag != "carrier_config":
            raise ValueError("Unknown carrier node in " + source)
        context = {"source": source, "index": index, "filters": dict(rule.attrib)}
        attrs = dict(rule.attrib)
        unknown = set(attrs) - FILTERS - {"iccid"}
        if unknown:
            report["omitted"].append({**context, "reason": "unsupported filters",
                                      "attributes": sorted(unknown),
                                      "xml": ET.tostring(rule, encoding="unicode")})
            continue
        if studio and "gid1" in attrs:
            attrs["gid1_prefix"] = attrs.pop("gid1")
        if "iccid" in attrs:
            attrs["iccid_prefix"] = attrs.pop("iccid")
        children = []
        for original in rule:
            child = copy.deepcopy(original)
            key = child.get("name")
            reason = None
            if key not in supported and key not in POLICY_KEYS:
                reason = "no standard CarrierConfigManager key or supported policy consumer"
            elif not attrs and key not in POLICY_KEYS:
                reason = "preserve PixelOS carrier assets; omit OEM unconditional defaults"
            elif key in {"carrier_default_wfc_ims_mode_int",
                         "carrier_default_wfc_ims_roaming_mode_int"} and child.get("value") not in {"0", "1", "2"}:
                reason = "unsupported WFC mode; no inferred mapping"
            elif child.tag == "bool":
                # External stock XML uses this spelling; do not silently repair
                # a value the stock PersistableBundle parser may not accept.
                reason = "unsupported stock bool tag; actual stock parsing not established"
            if reason:
                report["omitted"].append({**context, "reason": reason,
                                          "xml": ET.tostring(original, encoding="unicode")})
            else:
                children.append(child)
        if not children:
            continue
        mccs = attrs.pop("mcc", None)
        mncs = attrs.pop("mnc", None)
        iccids = attrs.pop("iccid_prefix", None)
        for mcc, mnc, iccid in itertools.product(
                mccs.split(",") if mccs else [None],
                mncs.split(",") if mncs else [None],
                iccids.split(",") if iccids else [None]):
            expanded = dict(attrs)
            if mcc is not None:
                expanded["mcc"] = mcc
            if mnc is not None:
                expanded["mnc"] = mnc
            if iccid is not None:
                if not iccid:
                    raise ValueError("Empty ICCID prefix in " + source)
                expanded["iccid_prefix"] = iccid
            new_rule = ET.SubElement(output, "carrier_config", expanded)
            new_rule.extend(copy.deepcopy(children))
            report["emitted"].append({**context, "output_index": len(output) - 1,
                                      "output_filters": expanded,
                                      "keys": [c.get("name") for c in children]})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("android", type=Path)
    parser.add_argument("project", type=Path)
    parser.add_argument("stock", type=Path)
    args = parser.parse_args()
    android = args.android.resolve(strict=True)
    project = args.project.resolve(strict=True)
    stock = args.stock.resolve(strict=True)
    if not (android / "build/envsetup.sh").is_file():
        parser.error("Expected Android source tree")
    if not (project / "device/xiaomi/popsicle").is_dir():
        parser.error("Expected popsicle project")
    destination = android / "vendor/xiaomi/popsicle-private/prebuilt/carrier-config"
    if destination.is_relative_to(stock) or stock.is_relative_to(destination):
        parser.error("Stock input and private output must be separate")
    if any(p.is_symlink() for p in [destination, *destination.parents]):
        parser.error("Private output path must not contain symlinks")
    aapt = android / "prebuilts/sdk/tools/linux/bin/aapt2"
    manager = android / "frameworks/base/telephony/java/android/telephony/CarrierConfigManager.java"
    supported = set(re.findall(r'"([^"\n]+)"', manager.read_text()))
    common_apk = stock / "product/overlay/CarrierConfigResCommon_Sys.apk"
    studio_apk = stock / "system_ext/priv-app/CarrierStudioCarrierConfig/CarrierStudioCarrierConfig.apk"
    report = {"format": 1, "stock_release": "OS4.0.0.23.XPBCNXM",
              "layers": [], "emitted": [], "omitted": []}
    output = ET.Element("carrier_config_list")

    def layer(root, source, studio=False):
        report["layers"].append(source)
        convert_layer(root, source, supported, output, report, studio)

    layer(decoded_xml(aapt, common_apk, "res/xml/vendor.xml"), "Common/res/xml/vendor.xml")
    layer(decoded_xml(aapt, studio_apk, "res/xml/vendor_miui.xml"), "CarrierStudio/res/xml/vendor_miui.xml", True)
    extension = stock / "mi_ext/product/etc/vendor_miui.xml"
    if extension.is_file():
        layer(ET.parse(extension).getroot(), "mi_ext/product/etc/vendor_miui.xml", True)
    with zipfile.ZipFile(studio_apk) as archive:
        device = ET.fromstring(archive.read("assets/device/popsicle/res/xml/vendor_device.xml"))
        includes = [r.get("include") for r in device if "include" in r.attrib]
        if includes != ["globalization.xml", "default_v2.9.7.xml"]:
            raise ValueError("Unexpected popsicle includes: " + repr(includes))
        for name in includes:
            layer(ET.fromstring(archive.read("assets/default/" + name)), "CarrierStudio/assets/default/" + name, True)
        for rule in list(device):
            if "include" in rule.attrib:
                device.remove(rule)
        layer(device, "CarrierStudio/assets/device/popsicle/res/xml/vendor_device.xml", True)
    extension = stock / "mi_ext/product/etc/vendor_device.xml"
    if extension.is_file():
        layer(ET.parse(extension).getroot(), "mi_ext/product/etc/vendor_device.xml", True)
    ET.indent(output, space="    ")
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".carrier-config-", dir=destination.parent) as temp:
        staging = Path(temp)
        (staging / "res/xml").mkdir(parents=True)
        ET.ElementTree(output).write(staging / "res/xml/vendor.xml", encoding="utf-8", xml_declaration=True)
        (staging / "conversion-report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n")
        (staging / "Android.bp").write_text('''// SPDX-License-Identifier: Apache-2.0
package { default_applicable_licenses: ["popsicle_carrier_config_notice"], }
license {
    name: "popsicle_carrier_config_notice",
    license_kinds: ["legacy_notice"],
    license_text: ["NOTICE"],
}
runtime_resource_overlay {
    name: "PopsicleImsCarrier",
    product_specific: true,
    sdk_version: "current",
    certificate: "platform",
    aaptflags: ["--keep-raw-values"],
}
''')
        (staging / "AndroidManifest.xml").write_text('''<manifest xmlns:android="http://schemas.android.com/apk/res/android" package="org.lineageos.popsicle.ims.carrier">
    <uses-sdk android:minSdkVersion="36" android:targetSdkVersion="37" />
    <overlay android:targetPackage="com.android.carrierconfig" android:isStatic="true" android:priority="999" />
    <application android:hasCode="false" />
</manifest>
''')
        with (staging / "NOTICE").open("wb") as notice:
            for partition in ["product", "system_ext"]:
                notice.write(gzip.decompress((stock / partition / "etc/NOTICE.xml.gz").read_bytes()))
                notice.write(b"\n")
        # Only the generated files are owned here. Keep any unrelated files intact.
        for source in staging.rglob("*"):
            if source.is_file():
                target = destination / source.relative_to(staging)
                if any(p.is_symlink() for p in [target, *target.parents]):
                    raise ValueError("Output path contains a symlink: " + str(target))
                target.parent.mkdir(parents=True, exist_ok=True)
                source.replace(target)
    print(f"Prepared {len(output)} carrier rules in {destination}")
    print(f"Recorded {len(report['omitted'])} omitted values/rules in conversion-report.json")


if __name__ == "__main__":
    main()
