#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare the tested IMS repair from read-only official inputs, inside private storage."""
import argparse
import gzip
from pathlib import Path
import shutil
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

parser = argparse.ArgumentParser()
parser.add_argument('android', type=Path)
# Retain the positional argument for existing preparation commands.
parser.add_argument('project', type=Path, help='legacy project argument; repair source is adjacent')
parser.add_argument('stock', type=Path)
args = parser.parse_args()
android = args.android.resolve(strict=True)
stock = args.stock.resolve(strict=True)
if not (android / 'build/envsetup.sh').is_file():
    parser.error('Expected an Android source tree with build/envsetup.sh')
if ('repositories-readonly' in android.parts
        or android.is_relative_to(Path('/root/autodl-tmp/lineage-24.0'))
        or android.is_relative_to(Path('/root/autodl-tmp/popsicle-archive'))):
    parser.error('Refusing read-only or retired sources')
destination = android / 'vendor/xiaomi/popsicle-private/prebuilt/ims'
if destination.is_relative_to(stock) or stock.is_relative_to(destination):
    parser.error('Official inputs and private output must be separate')
if any(path.is_symlink() for path in [destination, *destination.parents]):
    parser.error('Private output path must not contain symlinks')
destination.parent.mkdir(parents=True, exist_ok=True)
# Assemble all inputs before inspecting/publishing; never overwrite an existing bundle.
workspace = tempfile.TemporaryDirectory(prefix='.ims-', dir=destination.parent)
output = Path(workspace.name) / 'ims'
output.mkdir()
files = {'qti-telephony-utils.jar': 'system_ext/framework/qti-telephony-utils.jar',
         'ims-ext-common.jar': 'product/framework/ims-ext-common.jar',
         'QtiTelephony.apk': 'system_ext/priv-app/QtiTelephony/QtiTelephony.apk',
         'libimsmedia_jni.so': 'system_ext/lib64/libimsmedia_jni.so',
         'libSurfaceUtil_jni.so': 'system_ext/lib64/libSurfaceUtil_jni.so',
         'qti_telephony_utils.xml': 'system_ext/etc/permissions/qti_telephony_utils.xml',
         'ims_ext_common.xml': 'product/etc/permissions/ims_ext_common.xml',
         'TelephonyResCommon_Sys.apk': 'product/overlay/TelephonyResCommon_Sys.apk'}
for name, source in files.items():
    shutil.copyfile(args.stock / source, output / name)
with zipfile.ZipFile(output / 'TelephonyResCommon_Sys.apk') as overlay:
    names = overlay.namelist()
    if any(name.endswith('.dex') for name in names) or 'resources.arsc' not in names:
        raise ValueError('Expected the official resource-only MMTEL overlay')
with tempfile.TemporaryDirectory(dir=output) as tmp:
    unsigned = Path(tmp) / 'unsigned.apk'
    subprocess.run(['python3', str(Path(__file__).with_name('patch-apk.py')),
                    str(args.stock / 'system_ext/priv-app/ims/ims.apk'), str(unsigned)], check=True)
    with zipfile.ZipFile(unsigned) as src, zipfile.ZipFile(output / 'ims.apk', 'w') as dst:
        for entry in src.infolist():
            dst.writestr(entry, src.read(entry))
root = ET.Element('permissions')
entry = ET.parse(args.stock / 'system_ext/etc/permissions/telephony_system-ext_privapp-permissions-qti.xml').find("privapp-permissions[@package='org.codeaurora.ims']")
if entry is None:
    raise ValueError('Missing official IMS permissions')
root.append(entry)
ET.ElementTree(root).write(output / 'privapp-permissions-popsicle-ims.xml', encoding='utf-8', xml_declaration=True)
with (output / 'NOTICE').open('wb') as notice:
    for partition in ['system_ext', 'product']:
        path = args.stock / partition / 'etc/NOTICE.xml.gz'
        notice.write(gzip.decompress(path.read_bytes()))
        notice.write(b'\n')
for name in ['Android.bp', 'Android.mk']:
    shutil.copyfile(Path(__file__).with_name('private-' + name), output / name)
if destination.exists():
    expected = {p.name for p in output.iterdir()}
    if {p.name for p in destination.iterdir()} != expected:
        raise ValueError('Existing IMS bundle has different files')
    for source in output.iterdir():
        target = destination / source.name
        if target.is_symlink() or not target.is_file() or target.read_bytes() != source.read_bytes():
            raise ValueError('Refusing to replace different private input: ' + str(target))
else:
    output.rename(destination)
workspace.cleanup()
print('Prepared/verified private IMS inputs; APK is signed by the normal product build.')
