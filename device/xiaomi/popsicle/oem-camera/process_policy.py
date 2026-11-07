#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract ordinary-edition process-policy arrays for popsicle private inputs."""
import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import zipfile


ARRAYS = {
    'package_static_white_list': 0x110300ac,
    'package_static_white_list_base': 0x110300ad,
    'process_secretly_protect_list': 0x110300b9,
    'process_static_white_list': 0x110300ba,
    'process_static_white_list_base': 0x110300bb,
}


def parse_arrays(dump):
    arrays = {}
    blocks = re.split(r'(?m)^\s*resource ', dump)[1:]
    for block in blocks:
        header, _, body = block.partition('\n')
        match = re.fullmatch(r'(0x[0-9a-f]+) array/(\w+)', header.strip())
        if not match or match[2] not in ARRAYS:
            continue
        name = match[2]
        if name in arrays or int(match[1], 16) != ARRAYS[name]:
            raise ValueError('Unexpected or duplicate resource: ' + name)
        value = re.fullmatch(r'\s*\(\) \(array\) size=(\d+)\s+(\[.*\])\s*', body, re.S)
        if not value:
            raise ValueError('Expected one default literal array: ' + name)
        items = json.loads(value[2])
        if len(items) != int(value[1]) or any(type(item) is not str for item in items):
            raise ValueError('Unexpected array contents: ' + name)
        arrays[name] = items
    if arrays.keys() != ARRAYS.keys():
        raise ValueError('Missing process-policy arrays: ' + ', '.join(ARRAYS.keys() - arrays.keys()))
    return arrays


def reject_related_overlays(source):
    patterns = [value for name in ARRAYS for value in (name.encode(), name.encode('utf-16le'))]
    patterns += [value.to_bytes(4, 'little') for value in ARRAYS.values()]
    for partition in ('system/system', 'system_ext', 'product', 'vendor', 'odm', 'oem',
                      'mi_ext/product', 'mi_ext/system_ext', 'mi_ext/system'):
        for apk in (source / partition / 'overlay').rglob('*.apk'):
            with zipfile.ZipFile(apk) as archive:
                for entry in archive.namelist():
                    if entry != 'resources.arsc' and not (
                            entry.startswith('res/xml/') and entry.endswith('.xml')):
                        continue
                    data = archive.read(entry)
                    if any(pattern in data for pattern in patterns):
                        raise ValueError('Resolve process-policy overlay before extraction: '
                                         + str(apk.relative_to(source)))


def aapt2_path(host_bin):
    tool = Path(host_bin).resolve(strict=True) / 'aapt2'
    if not tool.is_file() or not os.access(tool, os.X_OK):
        raise ValueError('Expected executable host tool: ' + str(tool))
    return tool


def prepare(android, source, check=False, *, host_bin):
    tool = aapt2_path(host_bin)
    android = Path(android).resolve(strict=True)
    source = Path(source).resolve(strict=True)
    if not (android / 'build/envsetup.sh').is_file():
        raise ValueError('Expected PixelOS Android tree')
    if 'OS4.0.0.23.XPBCNXM' not in (source / 'product/etc/build.prop').read_text():
        raise ValueError('Expected matching original A17 input')
    destination = android / 'vendor/xiaomi/popsicle-private/prebuilt/oem-camera/process-policy.json'
    if any(path.is_symlink() for path in (destination, *destination.parents)):
        raise ValueError('Private output must not contain symlinks')
    if source == destination.parent or source in destination.parents \
            or destination.parent in source.parents:
        raise ValueError('Original input and private output must be separate')
    reject_related_overlays(source)
    apk = source / 'system_ext/framework/framework-ext-res/framework-ext-res.apk'
    dump = subprocess.check_output([
        str(tool), 'dump', 'resources', str(apk)],
        text=True)
    arrays = parse_arrays(dump)
    result = json.dumps({'format': 1, 'arrays': arrays}, ensure_ascii=False, indent=2) + '\n'
    if destination.exists():
        if destination.read_text() != result:
            raise ValueError('Conflicting private process-policy input')
    elif check:
        raise ValueError('Missing private process-policy input')
    else:
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(result)
    return {name: len(items) for name, items in arrays.items()}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('android', type=Path)
    parser.add_argument('filesystems', type=Path)
    parser.add_argument('--host-bin', type=Path, required=True,
                        help='explicit directory containing the Android host aapt2')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    print(prepare(args.android, args.filesystems, args.check, host_bin=args.host_bin))


if __name__ == '__main__':
    main()
