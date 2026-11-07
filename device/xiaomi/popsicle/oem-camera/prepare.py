#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare original camera APK, algorithm JNI and CameraOpt inputs."""
import argparse
import filecmp
import gzip
import html
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
import zipfile

from process_policy import aapt2_path, prepare as prepare_process_policy
from brightness_reset import prepare as prepare_brightness_reset
from default_gallery import prepare as prepare_default_gallery
from dual_screen_lifecycle import prepare as prepare_dual_screen_lifecycle
from raw_save import prepare as prepare_raw_save


def prepare_camera_apk(android, original, destination, check):
    """Derive discovery, lifecycle, gallery and RAW save-boundary fixes."""
    if destination.is_symlink():
        raise ValueError('Symlink camera output')
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'
    dexlib = android / 'prebuilts/extract-tools/common/smali/baksmali.jar'
    tool = Path(__file__).parent / 'CameraVendorDiscovery.java'
    with tempfile.TemporaryDirectory(prefix='camera-discovery-', dir=destination.parent) as tmp:
        tmp = Path(tmp)
        with zipfile.ZipFile(original) as source:
            names = source.namelist()
            if len(names) != len(set(names)):
                raise ValueError('Duplicate original APK entries')
            (tmp / 'original.dex').write_bytes(source.read('classes.dex'))
            subprocess.run([str(java), '--class-path', str(dexlib), str(tool),
                            str(tmp / 'original.dex'), str(tmp / 'adapted.dex')], check=True)
            discovery = (tmp / 'adapted.dex').read_bytes()
            prepare_brightness_reset(android, tmp / 'adapted.dex', tmp / 'brightness.dex')
            brightness = (tmp / 'brightness.dex').read_bytes()
            prepare_default_gallery(android, tmp / 'brightness.dex', tmp / 'gallery.dex')
            gallery = (tmp / 'gallery.dex').read_bytes()
            prepare_dual_screen_lifecycle(android, tmp / 'gallery.dex', tmp / 'lifecycle.dex')
            lifecycle = (tmp / 'lifecycle.dex').read_bytes()
            prepare_raw_save(android, tmp / 'lifecycle.dex', tmp / 'raw-save.dex')
            adapted = (tmp / 'raw-save.dex').read_bytes()
            if destination.exists():
                with zipfile.ZipFile(destination) as existing:
                    if existing.namelist() != names:
                        raise ValueError('Conflicting adapted APK entries')
                    for name in names:
                        if name != 'classes.dex' and existing.read(name) != source.read(name):
                            raise ValueError('Conflicting adapted APK entry: ' + name)
                    actual = existing.read('classes.dex')
                    if actual == adapted:
                        return
                    # Smali can reorder equivalent DEX data items between invocations.
                    # Require identical disassembly, never accept arbitrary bytecode changes.
                    def disassembly(data, label):
                        dex = tmp / (label + '.dex')
                        dex.write_bytes(data)
                        directory = tmp / label
                        subprocess.run([str(java), '-jar', str(dexlib), 'd', str(dex),
                                        '-o', str(directory)], check=True)
                        return {str(p.relative_to(directory)): p.read_bytes()
                                for p in directory.rglob('*.smali')}
                    actual_tree = disassembly(actual, 'existing-check')
                    if actual_tree == disassembly(adapted, 'current-check'):
                        return
                    if check or not (actual == lifecycle or actual == gallery or actual == brightness or actual == discovery or
                            actual_tree == disassembly(lifecycle, 'lifecycle-check') or
                            actual_tree == disassembly(gallery, 'gallery-check') or
                            actual_tree == disassembly(brightness, 'brightness-check') or
                            actual_tree == disassembly(discovery, 'discovery-check')):
                        raise ValueError('Conflicting or outdated adapted camera APK')
            elif check:
                raise ValueError('Missing adapted camera APK')
            with zipfile.ZipFile(tmp / 'adapted.apk', 'w') as output:
                for entry in source.infolist():
                    output.writestr(entry, adapted if entry.filename == 'classes.dex'
                                    else source.read(entry.filename))
            (tmp / 'adapted.apk').replace(destination)



def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('android', type=Path)
    parser.add_argument('filesystems', type=Path)
    parser.add_argument('--host-bin', type=Path, required=True,
                        help='explicit directory containing the Android host aapt2')
    parser.add_argument('--check', action='store_true')
    args = parser.parse_args()
    aapt2_path(args.host_bin)
    android = args.android.resolve(strict=True)
    source = args.filesystems.resolve(strict=True)
    if not (android / 'build/envsetup.sh').is_file():
        parser.error('Expected the PixelOS Android source tree')
    if 'OS4.0.0.23.XPBCNXM' not in (source / 'product/etc/build.prop').read_text():
        parser.error('Expected matching official A17 filesystem input')
    dest = android / 'vendor/xiaomi/popsicle-private/prebuilt/oem-camera'
    if any(p.is_symlink() for p in [dest, *dest.parents]):
        parser.error('Private destination must not contain symlinks')
    if source == dest or source in dest.parents or dest in source.parents:
        parser.error('Official input and private output must be separate')
    inputs = ['system_ext/framework/miui-cameraopt.jar',
              'system_ext/lib64/libcamera_algoup_jni.xiaomi.so',
              'system_ext/lib64/libcamera_mianode_jni.xiaomi.so',
              'system_ext/lib64/libcameraopt.so',
              'system_ext/lib64/libcameraopt_jni.so',
              'system_ext/etc/cameraopt.json',
              'system_ext/etc/cameraopt_perf.json',
              'system_ext/etc/cameraopt_reclaim.json',
              'system_ext/etc/cameraopt_thirdParty.json',
              'system_ext/etc/camerascene.json',
              'system_ext/etc/permissions/miui-cameraopt.xml',
              'product/priv-app/MiuiCamera/MiuiCamera.apk']
    outputs = {Path(name).name: source / name for name in inputs}
    outputs['Android.bp'] = Path(__file__).parent / 'Android.bp.in'
    outputs['privapp-permissions-popsicle-camera.xml'] = (
        Path(__file__).parent / 'privapp-permissions-popsicle-camera.xml')
    # The OEM aggregate contains malformed XML elsewhere. Read only exact file-name mappings
    # and their CDATA bodies, rather than weakening or omitting NOTICE generation.
    with gzip.open(source / 'system_ext/etc/NOTICE.xml.gz', 'rt') as stream:
        notice = stream.read()
    content = dict(re.findall(r'<file-content contentId="([^"]+)"[^>]*><!\[CDATA\[(.*?)\]\]></file-content>',
                              notice, re.S))
    texts = []
    for name in inputs[:1]:
        ids = set()
        for attrs, path in re.findall(r'<file-name([^>]*)>([^<]*)</file-name>', notice):
            if path == '/' + name:
                match = re.search(r'contentId="([^"]+)"', attrs)
                if match:
                    ids.add(match[1])
        if not ids or any(not content.get(key, '').strip() for key in ids):
            parser.error('Missing official NOTICE mapping/text: ' + name)
        for key in sorted(ids):
            texts.append('Official /' + name + '\n' + html.unescape(content[key]))
    for name, src in outputs.items():
        dst = dest / name
        if src.is_symlink() or not src.is_file() or dst.is_symlink():
            parser.error('Expected regular input/output: ' + name)
        if dst.exists() and not filecmp.cmp(src, dst, shallow=False):
            # Permit only the exact earlier maintained templates, not arbitrary changes.
            templates = []
            if name == 'Android.bp':
                current = src.read_text()
                previous = current.replace(
                    '        "popsicle-cameraopt-process-policy",\n', '').removesuffix(
                    '\nprebuilt_etc {\n'
                    '    name: "popsicle-cameraopt-process-policy",\n'
                    '    src: "process-policy.json",\n'
                    '    filename: "popsicle-process-policy.json",\n'
                    '    system_ext_specific: true,\n'
                    '}\n')
                templates = [previous,
                             previous.replace('MiuiCamera-pixelos.apk', 'MiuiCamera.apk')]
            if not templates or dst.read_text() not in templates or args.check:
                parser.error('Refusing to replace a different prepared input: ' + name)
        if args.check and not dst.is_file():
            parser.error('Missing prepared input: ' + name)
    notice_text = '\n\n'.join(texts) + '\n'
    target_notice = dest / 'NOTICE'
    if target_notice.is_symlink() or (target_notice.exists()
                                      and target_notice.read_text() != notice_text):
        parser.error('Refusing to replace a different prepared NOTICE')
    if args.check:
        if not target_notice.is_file():
            parser.error('Missing prepared NOTICE')
    else:
        dest.mkdir(parents=True, exist_ok=True)
        for name, src in outputs.items():
            if not (dest / name).exists() or (name == 'Android.bp'
                    and not filecmp.cmp(src, dest / name, shallow=False)):
                shutil.copyfile(src, dest / name)
        if not target_notice.exists():
            target_notice.write_text(notice_text)
    prepare_process_policy(android, source, args.check, host_bin=args.host_bin)
    prepare_camera_apk(android, outputs['MiuiCamera.apk'],
                       dest / 'MiuiCamera-pixelos.apk', args.check)
    print('PASS: original inputs, ordinary process policy and camera adaptations')


if __name__ == '__main__':
    main()
