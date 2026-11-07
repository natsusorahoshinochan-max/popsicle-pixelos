#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Refresh OEM rear geometry in the existing MiSight candidate, preserving its payload."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import zipfile


LAUNCHER = 'com/xiaomi/subscreencenter/SubScreenLauncher'
HELPER = '''
.method private static refreshPixelOsRearGeometry(Landroid/content/Context;)V
    .locals 4

    const-class v0, Landroid/hardware/display/DisplayManager;
    invoke-virtual {p0, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/Class;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/hardware/display/DisplayManager;
    if-eqz v0, :geometry_done
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/hardware/display/DisplayManager;->getDisplay(I)Landroid/view/Display;
    move-result-object v0
    if-eqz v0, :geometry_done
    sget-object v1, LC2/l;->k:Landroid/graphics/Point;
    invoke-virtual {v0, v1}, Landroid/view/Display;->getRealSize(Landroid/graphics/Point;)V
    iget v2, v1, Landroid/graphics/Point;->x:I
    iget v3, v1, Landroid/graphics/Point;->y:I
    if-lez v2, :geometry_done
    if-lez v3, :geometry_done
    int-to-float v2, v2
    int-to-float v3, v3
    div-float/2addr v2, v3
    sput v2, LC2/l;->l:F
    :geometry_done
    return-void
.end method
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('android', type=Path)
    parser.add_argument('--private-dir', type=Path,
                        help='isolated output directory for the rear preparation chain')
    args = parser.parse_args()
    android = args.android.resolve(strict=True)
    private = args.private_dir or android / 'vendor/xiaomi/popsicle-private/prebuilt/oem-rear'
    if not private.resolve().is_relative_to(android / 'vendor/xiaomi/popsicle-private/prebuilt'):
        raise ValueError('Rear outputs must remain in this Android tree private inputs')
    if any(path.is_symlink() for path in [private, *private.parents]):
        raise ValueError('Private work directory must not use symlinks')
    source = private / 'subscreencenter-misight.apk'
    work = private / 'geometry-work'
    work.mkdir(exist_ok=False)
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'
    smali = android / 'prebuilts/extract-tools/common/smali'
    with zipfile.ZipFile(source) as src:
        if len(src.namelist()) != len(set(src.namelist())):
            raise ValueError('Duplicate APK entries')
        (work / 'input.dex').write_bytes(src.read('classes.dex'))
    subprocess.run([str(java), '-jar', str(smali / 'baksmali.jar'), 'd', '-l',
                    str(work / 'input.dex'), '-o', str(work / 'smali')], check=True)
    target = work / 'smali' / (LAUNCHER + '.smali')
    text = target.read_text()
    if 'refreshPixelOsRearGeometry' in text:
        raise ValueError('Geometry change already present')
    for method in ('onCreate(Landroid/os/Bundle;)V',
                   'onConfigurationChanged(Landroid/content/res/Configuration;)V'):
        pattern = r'(\.method public final ' + re.escape(method) + r'\n    \.locals \d+\n)'
        text, count = re.subn(pattern, lambda match: match[1] + '\n'
                             + '    invoke-static {p0}, L' + LAUNCHER
                             + ';->refreshPixelOsRearGeometry(Landroid/content/Context;)V\n',
                             text)
        if count != 1:
            raise ValueError('Unexpected OEM lifecycle method: ' + method)
    target.write_text(text + HELPER)
    subprocess.run([str(java), '-jar', str(smali / 'smali.jar'), 'a',
                    str(work / 'smali'), '-o', str(work / 'classes.dex')], check=True)
    output = private / 'subscreencenter-aod.apk'
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(output, 'x') as dst:
        for entry in src.infolist():
            # Existing candidate has already removed OEM signatures. Soong signs normally.
            if re.fullmatch(r'META-INF/(?:MANIFEST\.MF|[^/]+\.(?:SF|RSA|DSA|EC))', entry.filename):
                raise ValueError('Unexpected signed candidate input')
            payload = (work / 'classes.dex').read_bytes() if entry.filename == 'classes.dex' else src.read(entry)
            dst.writestr(entry, payload)
    provenance = {'input_apk': str(source), 'output_apk': str(output),
                  'changed_class': LAUNCHER,
                  'hooks': ['onCreate', 'onConfigurationChanged']}
    (work / 'provenance.json').write_text(json.dumps(provenance, indent=2) + '\n')
    print(json.dumps(provenance))


if __name__ == '__main__':
    main()
