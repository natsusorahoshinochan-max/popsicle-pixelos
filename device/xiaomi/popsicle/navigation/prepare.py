#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Generate navigation-only resources from the product's original Pixel Launcher."""
import argparse
from pathlib import Path
import re
import subprocess
import xml.etree.ElementTree as ET
import zipfile

ANDROID = 'http://schemas.android.com/apk/res/android'
LAUNCHER = 'com.google.android.apps.nexuslauncher'
ET.register_namespace('android', ANDROID)


def dump(aapt, apk, *arguments):
    return subprocess.run([str(aapt), 'dump', *arguments, str(apk)],
                          check=True, text=True, stdout=subprocess.PIPE).stdout


def navigation_layout(text, names):
    stack = []
    root = None
    handles = []
    references = {}
    for line in text.splitlines():
        element = re.fullmatch(r'(\s*)E: (\S+) \(line=\d+\)', line)
        if element:
            depth = len(element[1])
            while stack and stack[-1][0] >= depth:
                stack.pop()
            node = ET.Element(element[2])
            if stack:
                stack[-1][1].append(node)
            elif root is None:
                root = node
            else:
                raise ValueError('Multiple layout roots')
            stack.append((depth, node))
            if element[2] == 'com.android.launcher3.taskbar.StashedHandleView':
                handles.append(node)
            continue
        attribute = re.fullmatch(r'\s*A: ' + ANDROID + r':(\w+)\(0x[0-9a-f]+\)=(.*)', line)
        if attribute:
            key, value = attribute.groups()
            if value.startswith('@0x'):
                identifier = int(value[1:], 16)
                references[identifier] = names[identifier]
                value = '@*' + LAUNCHER + ':' + names[identifier]
            elif key in ('layout_width', 'layout_height') and value in ('-1', '-2'):
                value = {'-1': 'match_parent', '-2': 'wrap_content'}[value]
            elif key == 'visibility':
                value = {'0': 'visible', '1': 'invisible', '2': 'gone'}[value]
            elif key == 'orientation':
                value = {'0': 'horizontal', '1': 'vertical'}[value]
            elif key in ('gravity', 'layout_gravity'):
                value = {
                    '0x00000011': 'center',
                    '0x00000010': 'center_vertical',
                    '0x00000050': 'bottom',
                    '0x00000051': 'bottom|center_horizontal',
                    '0x00800003': 'start',
                    '0x00800005': 'end',
                }[value]
            elif value not in ('true', 'false') and not re.fullmatch(r'0x[0-9a-fA-F]+', value):
                raise ValueError('Unsupported layout attribute: ' + line)
            stack[-1][1].set('{' + ANDROID + '}' + key, value)
        elif line.strip() and not element and not line.lstrip().startswith('N: '):
            raise ValueError('Unsupported layout content: ' + line)
    if root is None or len(handles) != 1:
        raise ValueError('Expected one navigation StashedHandleView')
    handle = handles[0]
    if handle.get('{' + ANDROID + '}id') != '@*' + LAUNCHER + ':id/stashed_handle':
        raise ValueError('Unexpected navigation handle identity')
    # Preserve visibility, alpha, dimensions, outline and long-press source bounds.
    handle.set('{' + ANDROID + '}backgroundTint', '#00000000')
    handle.set('{' + ANDROID + '}backgroundTintMode', 'src_in')
    # These IDs describe the link input as well as keeping generated resources
    # dependent on target symbol changes when names remain unchanged.
    root.insert(0, ET.Comment('Launcher reference IDs: ' + ', '.join(
        f'{name}=0x{identifier:08x}' for identifier, name in sorted(references.items()))))
    return root


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--launcher', type=Path, required=True)
    parser.add_argument('--aapt', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    target, aapt = args.launcher, args.aapt
    table = dump(aapt, target, 'resources')
    if not re.search(r'^Package name=' + re.escape(LAUNCHER) + r' id=7f$', table, re.M):
        parser.error('Expected original product Pixel Launcher')
    names = {int(key, 16): name for key, name in
             re.findall(r'^\s*resource (0x[0-9a-f]+) (\S+)', table, re.M)}
    tree = navigation_layout(dump(aapt, target, 'xmltree', '--file', 'res/layout/taskbar.xml'), names)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    ET.indent(tree)
    resources = {
        'layout/hidden_taskbar.xml': ET.tostring(tree, encoding='utf-8', xml_declaration=True),
        'xml/overlays.xml': b'<overlay><item target="layout/taskbar" value="@layout/hidden_taskbar" /></overlay>\n',
    }
    with zipfile.ZipFile(args.output, 'w', compression=zipfile.ZIP_DEFLATED) as archive:
        for name, data in resources.items():
            entry = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(entry, data)
    print('Prepared navigation resources from original Pixel Launcher')


if __name__ == '__main__':
    main()
