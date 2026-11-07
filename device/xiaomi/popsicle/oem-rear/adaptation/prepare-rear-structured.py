#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Consolidate the accepted OEM rear geometry and gesture-window adaptation."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import zipfile

LAUNCHER = 'com/xiaomi/subscreencenter/SubScreenLauncher'


def method(text, signature):
    pattern = r'\.method [^\n]* ' + re.escape(signature) + r'\n.*?\.end method'
    matches = list(re.finditer(pattern, text, re.S))
    if len(matches) != 1:
        raise ValueError('Unexpected method: ' + signature)
    return matches[0].group()


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected OEM source near ' + old[:100])
    return text.replace(old, new)


def transform_manager(text):
    # Preserve the accepted attach path, including all original window parameters.
    restore = method(text, 'restorePixelOsGestureWindows(Landroid/content/Context;)V')
    attach_start = restore.index('    iget-object v7, p0, Ln2/e;->m:Ln2/h;')
    shared = '''.method public restorePixelOsGestureWindows(Landroid/content/Context;)V
    .locals 8
    invoke-static {p1, p0}, Ln2/PixelOsRearDisplay;->refreshGeometry(Landroid/content/Context;Ln2/e;)Z
    move-result v0
    if-eqz v0, :restore_done
''' + restore[attach_start:]
    # Labels are assigned by baksmali; replace its final return label with ours.
    last_label = re.search(r'(:[\w]+)\s+return-void\s+\.end method$', shared)[1]
    shared = shared.replace(last_label, ':restore_done')
    shared = shared.replace('invoke-direct {v0, p0, v1}, Ln2/PixelOsGestureWindowState;-><init>(Ln2/e;Z)V',
                            'invoke-direct {v0, p0, v7, v1}, Ln2/PixelOsGestureWindowState;-><init>(Ln2/e;Landroid/view/View;Z)V')
    text = replace_once(text, restore, shared)

    constructor = method(text, '<init>()V')
    # Remove only the two old inline LayoutParams/attach blocks. Views and their
    # listeners remain initialized by the original constructor.
    for view, next_instruction in (
            ('m:Ln2/h;', 'new-instance v3, Landroid/view/View;'),
            ('p:Landroid/view/View;', 'new-instance v2, LC2/o;')):
        pattern = (r'    iget-object v3, p0, Ln2/e;->' + re.escape(view)
                   + r'\s+new-instance [^\n]+Landroid/view/WindowManager\$LayoutParams;'
                   + r'.*?(?=    ' + re.escape(next_instruction) + ')')
        replacement = '' if view.startswith('m:') else (
            '    invoke-virtual {p0, v2}, Ln2/e;->restorePixelOsGestureWindows(Landroid/content/Context;)V\n\n')
        constructor, count = re.subn(pattern, replacement, constructor, flags=re.S)
        if count != 1:
            raise ValueError('Unexpected constructor attach block: ' + view)
    text = replace_once(text, method(text, '<init>()V'), constructor)

    # Keep the OEM policy calculation, cache and surface application together.
    # Normal callers use false; a newly attached window explicitly forces replay.
    for original, implementation in (('e', 'applyPixelOsBackState'), ('f', 'applyPixelOsHomeState')):
        old = method(text, original + '()V')
        updated = old.replace(' ' + original + '()V', ' ' + implementation + '(Z)V', 1)
        branch = re.search(r'    if-ne v0, v1, (:[\w]+)', updated)
        if not branch:
            raise ValueError('Missing OEM policy cache branch: ' + original)
        updated = updated[:branch.start()] + '    if-nez p1, ' + branch[1] + '\n\n' + updated[branch.start():]
        wrapper = f'''.method public final {original}()V
    .locals 1
    const/4 v0, 0x0
    invoke-virtual {{p0, v0}}, Ln2/e;->{implementation}(Z)V
    return-void
.end method'''
        text = replace_once(text, old, wrapper + '\n\n' + updated)
    return text


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
    source = private / 'subscreencenter-gestures.apk'
    work = private / 'structured-work'
    work.mkdir(exist_ok=False)
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'
    smali = android / 'prebuilts/extract-tools/common/smali'
    with zipfile.ZipFile(source) as src:
        (work / 'input.dex').write_bytes(src.read('classes.dex'))
    subprocess.run([str(java), '-jar', str(smali / 'baksmali.jar'), 'd', '-l',
                    str(work / 'input.dex'), '-o', str(work / 'smali')], check=True)
    launcher = work / 'smali' / (LAUNCHER + '.smali')
    text = launcher.read_text()
    old = method(text, 'refreshPixelOsRearGeometry(Landroid/content/Context;)V')
    wrapper = '''.method private static refreshPixelOsRearGeometry(Landroid/content/Context;)V
    .locals 1
    sget-object v0, Lcom/xiaomi/subscreencenter/SubScreenCenterApp;->u:Lcom/xiaomi/subscreencenter/SubScreenCenterApp;
    if-nez v0, :manager
    const/4 v0, 0x0
    goto :refresh
    :manager
    iget-object v0, v0, Lcom/xiaomi/subscreencenter/SubScreenCenterApp;->e:Ln2/e;
    :refresh
    invoke-static {p0, v0}, Ln2/PixelOsRearDisplay;->refreshGeometry(Landroid/content/Context;Ln2/e;)Z
    return-void
.end method'''
    launcher.write_text(replace_once(text, old, wrapper))
    manager = work / 'smali/n2/e.smali'
    manager.write_text(transform_manager(manager.read_text()))
    runtime = Path(__file__).with_name('structured-runtime')
    for filename in ('PixelOsRearDisplay.smali', 'PixelOsGestureWindowState.smali'):
        (work / 'smali/n2' / filename).write_text((runtime / filename).read_text())
    subprocess.run([str(java), '-jar', str(smali / 'smali.jar'), 'a',
                    str(work / 'smali'), '-o', str(work / 'classes.dex')], check=True)
    output = private / 'subscreencenter-structured.apk'
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(output, 'x') as dst:
        dex = (work / 'classes.dex').read_bytes()
        for entry in src.infolist():
            dst.writestr(entry, dex if entry.filename == 'classes.dex' else src.read(entry))
    result = {'input_apk': str(source), 'output_apk': str(output),
              'changed_classes': [LAUNCHER, 'n2/e', 'n2/PixelOsRearDisplay',
                                  'n2/PixelOsGestureWindowState']}
    (work / 'provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
