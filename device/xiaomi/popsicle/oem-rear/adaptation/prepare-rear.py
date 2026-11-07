#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare a private candidate from matching official inputs; original APK entries stay intact."""
import argparse
import gzip
import html
import json
from pathlib import Path
import re
import subprocess
import zipfile


def prepare_notice(stock, work):
    # Reuse the exact existing OEM mapping for the bundled native backend.
    with gzip.open(stock / 'system_ext/etc/NOTICE.xml.gz', 'rt') as stream:
        notice = stream.read()
    contents = dict(re.findall(r'<file-content contentId="([^"]+)"[^>]*><!\[CDATA\[(.*?)\]\]></file-content>', notice, re.S))
    ids = set()
    for attrs, path in re.findall(r'<file-name([^>]*)>([^<]*)</file-name>', notice):
        if path == '/system_ext/lib64/libmisight.so':
            match = re.search(r'contentId="([^"]+)"', attrs)
            if match:
                ids.add(match[1])
    if not ids or any(not contents.get(key, '').strip() for key in ids):
        raise ValueError('Missing original libmisight NOTICE mapping')
    (work / 'NOTICE').write_text('Official /system_ext/lib64/libmisight.so\n\n'
                                + '\n\n'.join(html.unescape(contents[key]) for key in sorted(ids))
                                + '\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('android', type=Path)
    parser.add_argument('stock', type=Path)
    parser.add_argument('--dex-tools', type=Path, required=True)
    parser.add_argument('--private-dir', type=Path,
                        help='isolated output directory for the rear preparation chain')
    args = parser.parse_args()
    android, stock = args.android.resolve(), args.stock.resolve()
    if 'OS4.0.0.23.XPBCNXM' not in (stock / 'product/etc/build.prop').read_text():
        raise ValueError('Requires matching official firmware')
    out = args.private_dir or android / 'vendor/xiaomi/popsicle-private/prebuilt/oem-rear'
    if not out.resolve().is_relative_to(android / 'vendor/xiaomi/popsicle-private/prebuilt'):
        raise ValueError('Rear outputs must remain in this Android tree private inputs')
    if any(path.is_symlink() for path in [out, *out.parents]):
        raise ValueError('Private output directory must not use symlinks')
    work = out / 'misight-work'
    work.mkdir(exist_ok=False)
    prepare_notice(stock, work)
    original = stock / 'product/app/subscreencenter/subscreencenter.apk'
    framework = stock / 'system_ext/framework/miui-framework.jar'
    with zipfile.ZipFile(framework) as z:
        (work / 'original.dex').write_bytes(z.read('classes.dex'))
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin'
    cp = str(args.dex_tools.resolve() / 'lib/*')
    subprocess.run([str(java / 'javac'), '-cp', cp, '-d', str(work),
                    str(Path(__file__).with_name('ExtractMiSight.java'))], check=True)
    subprocess.run([str(java / 'java'), '-cp', str(work) + ':' + cp, 'ExtractMiSight',
                    str(work / 'original.dex'), str(work / 'misight.dex')], check=True)
    additions = {}
    with zipfile.ZipFile(original) as src:
        names = src.namelist()
        if len(names) != len(set(names)):
            raise ValueError('Duplicate original APK entries')
        indices = [1 if name == 'classes.dex' else int(name[7:-4])
                   for name in names if re.fullmatch(r'classes(?:[1-9][0-9]*)?\.dex', name)]
        if not indices:
            raise ValueError('Original APK has no DEX')
        additions[f'classes{max(indices) + 1}.dex'] = work / 'misight.dex'
        for name in ('libmisight_jni.so', 'libmisight.so'):
            additions['lib/arm64-v8a/' + name] = stock / 'system_ext/lib64' / name
        if set(additions) & set(names):
            raise ValueError('SDK payload already exists in original APK')
        candidate = out / 'subscreencenter-misight.apk'
        with zipfile.ZipFile(candidate, 'x') as dst:
            for entry in src.infolist():
                # Soong applies the existing platform signing identity after import.
                if re.fullmatch(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))', entry.filename):
                    continue
                dst.writestr(entry, src.read(entry.filename))
            for name, path in additions.items():
                dst.write(path, name, compress_type=zipfile.ZIP_STORED)
    report = {'original_apk': str(original), 'original_framework': str(framework),
              'candidate_apk': str(candidate),
              'added': {name: str(path) for name, path in additions.items()}}
    (work / 'provenance.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
