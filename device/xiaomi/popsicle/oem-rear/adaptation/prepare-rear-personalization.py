#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Add the bounded Settings provider and gesture gate to the accepted SSC input."""
import argparse
import json
from pathlib import Path
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
import zipfile


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected SSC implementation near ' + old[:100])
    return text.replace(old, new)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('android', type=Path)
    parser.add_argument('--work', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--private-dir', type=Path,
                        help='isolated output directory for the rear preparation chain')
    args = parser.parse_args()
    android = args.android.resolve(strict=True)
    private = args.private_dir or android / 'vendor/xiaomi/popsicle-private/prebuilt/oem-rear'
    if not private.resolve().is_relative_to(android / 'vendor/xiaomi/popsicle-private/prebuilt'):
        raise ValueError('Rear outputs must remain in this Android tree private inputs')
    if any(path.is_symlink() for path in [private, *private.parents]):
        raise ValueError('Private output directory must not use symlinks')
    args.output = args.output or private / 'subscreencenter-personalization.apk'
    work = (args.work or private / 'personalization-work').resolve()
    work.mkdir(parents=True, exist_ok=False)
    source = private / 'subscreencenter-structured.apk'
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin'
    smali = android / 'prebuilts/extract-tools/common/smali'
    apktool = android / 'prebuilts/extract-tools/common/apktool/apktool.jar'
    sdk = android / 'prebuilts/sdk/current/public/android.jar'
    run = lambda command: subprocess.run(list(map(str, command)), check=True)
    decoded = work / 'decoded'
    framework = work / 'apktool-framework'
    run([java/'java', '-Xmx4g', '-jar', apktool, 'd', '-p', framework, '-s', source, '-o', decoded])
    manifest = decoded/'AndroidManifest.xml'
    namespace = 'http://schemas.android.com/apk/res/android'
    ET.register_namespace('android', namespace)
    tree = ET.parse(manifest)
    application = tree.getroot().find('application')
    ET.SubElement(application, 'provider', {
        '{'+namespace+'}name': 'com.xiaomi.subscreencenter.personalization.RearPersonalizationProvider',
        '{'+namespace+'}authorities': 'com.xiaomi.subscreencenter.personalization',
        '{'+namespace+'}exported': 'true',
        '{'+namespace+'}directBootAware': 'true',
        '{'+namespace+'}permission': 'android.permission.WRITE_SECURE_SETTINGS',
    })
    tree.write(manifest, encoding='utf-8', xml_declaration=True)
    with zipfile.ZipFile(source) as archive:
        (work/'input.dex').write_bytes(archive.read('classes.dex'))
    root = work/'smali'
    run([java/'java', '-jar', smali/'baksmali.jar', 'd', '-l', work/'input.dex', '-o', root])
    descriptor = 'Lcom/xiaomi/subscreencenter/personalization/RearPersonalization;'
    app = root/'com/xiaomi/subscreencenter/SubScreenCenterApp.smali'
    text = app.read_text()
    anchor = '    sput-object v1, Lcom/xiaomi/subscreencenter/SubScreenCenterApp;->u:Lcom/xiaomi/subscreencenter/SubScreenCenterApp;'
    app.write_text(replace_once(text, anchor, anchor + '\n\n    invoke-static {v1}, '+descriptor+'->start(Landroid/content/Context;)V'))
    gesture = root/'k2/s.smali'
    text = gesture.read_text()
    anchor = '.method public final run()V\n    .locals 4\n'
    text = replace_once(text, anchor, anchor + '\n    invoke-static {}, '+descriptor+'->allowLongPress()Z\n    move-result v0\n    if-nez v0, :pixelos_run_allowed\n    return-void\n    :pixelos_run_allowed\n')
    anchor = '.method public final f(Landroid/view/MotionEvent;)V\n    .locals 5\n'
    text = replace_once(text, anchor, anchor + '\n    invoke-static {}, '+descriptor+'->allowLongPress()Z\n    move-result v0\n    if-nez v0, :pixelos_touch_allowed\n    iget-object v0, p0, Lk2/s;->e:Landroid/os/Handler;\n    invoke-virtual {v0, p0}, Landroid/os/Handler;->removeCallbacks(Ljava/lang/Runnable;)V\n    return-void\n    :pixelos_touch_allowed\n')
    anchor = '.method public final g(Landroid/view/MotionEvent;)Z\n    .locals 0\n'
    text = replace_once(text, anchor, anchor + '\n    invoke-static {}, '+descriptor+'->allowLongPress()Z\n    move-result p1\n    if-nez p1, :pixelos_eligible\n    return p1\n    :pixelos_eligible\n')
    gesture.write_text(text)
    accessibility = root/'E2/g.smali'
    text = accessibility.read_text()
    anchor = '    iget-boolean p0, p0, LE2/w;->u:Z\n\n    if-eqz p0, :cond_38'
    text = replace_once(text, anchor, anchor + '\n\n    invoke-static {}, '+descriptor+'->allowLongPress()Z\n    move-result p0\n    if-eqz p0, :cond_38')
    accessibility.write_text(text)
    classes = work/'classes'; classes.mkdir()
    sources = sorted(Path(__file__).with_name('personalization-runtime').rglob('*.java'))
    run([java/'javac', '--release', '17', '-classpath', sdk, '-d', classes, *sources])
    dex = work/'helper-dex'; dex.mkdir()
    run([java/'java', '-Xmx4g', '-cp', android/'prebuilts/r8/r8.jar', 'com.android.tools.r8.D8',
         '--min-api', '37', '--lib', sdk, '--output', dex, *sorted(classes.rglob('*.class'))])
    helpers = work/'helper-smali'
    run([java/'java', '-jar', smali/'baksmali.jar', 'd', dex/'classes.dex', '-o', helpers])
    for helper in helpers.rglob('*.smali'):
        target = root/helper.relative_to(helpers)
        if target.exists(): raise ValueError('Refusing to replace original class: '+str(target))
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(helper, target)
    run([java/'java', '-Xmx4g', '-jar', smali/'smali.jar', 'a', '--api', '28', '-j', '4', root, '-o', decoded/'classes.dex'])
    run([java/'java', '-Xmx4g', '-jar', apktool, 'b', '-p', framework, decoded, '-o', args.output])
    (work/'provenance.json').write_text(json.dumps({'input_apk': str(source),
        'output_apk': str(args.output), 'sources': list(map(str, sources))}, indent=2)+'\n')

if __name__ == '__main__':
    main()
