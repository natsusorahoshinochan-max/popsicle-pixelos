#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare source-release firmware and provider inputs from unpacked official A17 files."""
import argparse
import filecmp
import os
from pathlib import Path
import shutil
import subprocess
import sys

sys.dont_write_bytecode = True


def regular(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected a regular input: ' + str(path))
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--android', type=Path, required=True)
    parser.add_argument('--images', type=Path, required=True)
    parser.add_argument('--filesystems', type=Path, required=True)
    parser.add_argument('--host-bin', type=Path, required=True,
                        help='explicit directory containing the Android host aapt2')
    parser.add_argument('--dex-tools', type=Path, help='dex2jar distribution for rear APK preparation')
    parser.add_argument('--check', action='store_true', help='verify all prepared files without writing')
    args = parser.parse_args()
    host = args.host_bin.resolve(strict=True)
    tool = host / 'aapt2'
    if not tool.is_file() or not os.access(tool, os.X_OK):
        parser.error('Expected executable host tool: ' + str(tool))
    project = Path(__file__).resolve().parents[2]
    android = args.android.resolve(strict=True)
    images = args.images.resolve(strict=True)
    fs = args.filesystems.resolve(strict=True)
    if not (android / 'build/envsetup.sh').is_file():
        parser.error('Expected an Android source tree')
    if ('repositories-readonly' in android.parts
            or android.is_relative_to(Path('/root/autodl-tmp/lineage-24.0'))
            or android.is_relative_to(Path('/root/autodl-tmp/popsicle-archive'))):
        parser.error('Refusing read-only or retired sources')
    private = android / 'vendor/xiaomi/popsicle-private/prebuilt'
    if any(p.is_symlink() for p in [private, *private.parents]):
        parser.error('Private output path must not contain symlinks')
    if any(private.is_relative_to(p) or p.is_relative_to(private) for p in [images, fs]):
        parser.error('Official input roots and private output must be separate')
    # This release specializes the fixed OEM cohort; strict image checks still run in the build.
    prop = regular(fs / 'product/etc/build.prop').read_text()
    if 'OS4.0.0.23.XPBCNXM' not in prop:
        parser.error('Expected the OS4.0.0.23.XPBCNXM official filesystem cohort')
    outputs = []
    for name in ['boot', 'dtbo', 'vendor_boot', 'vbmeta', 'vendor', 'odm', 'mi_product', 'vendor_dlkm', 'system_dlkm']:
        outputs.append((regular(images / (name + '.img')), private / 'firmware-a17' / (name + '.img')))
    outputs.append((regular(images / 'vbmeta.img'), private / 'firmware-a17/vbmeta-witness.img'))
    for name, source in [('vendor', 'vendor/build.prop'), ('odm', 'odm/etc/build.prop'),
                         ('odm-dlkm', 'vendor/odm_dlkm/etc/build.prop'),
                         ('vendor-dlkm', 'vendor_dlkm/etc/build.prop'),
                         ('system-dlkm', 'system_dlkm/etc/build.prop')]:
        outputs.append((regular(fs / source), private / 'firmware-a17' / (name + '-build.prop')))
    pilots = project / 'scripts/source-patches/oem-vendor-providers'
    for name in ['libbase', 'libcrypto', 'libaudioutils']:
        relative = 'oem-abi/Android.bp' if name == 'libbase' else 'oem-abi/' + name + '/Android.bp'
        outputs.append((regular(pilots / (name + '-pilot/Android.bp')), private / relative))
    for src, dst in outputs:
        if any(p.is_symlink() for p in [dst, *dst.parents]):
            parser.error('Symlink private destination: ' + str(dst))
        if dst.exists() and (not dst.is_file() or not filecmp.cmp(src, dst, shallow=False)):
            parser.error('Refusing to replace a different private input: ' + str(dst))
        if args.check and not dst.is_file():
            parser.error('Missing prepared input: ' + str(dst))
    if not args.check:
        for src, dst in outputs:
            if not dst.exists():
                dst.parent.mkdir(parents=True, exist_ok=True)
                with src.open('rb') as inp, dst.open('xb') as out:
                    shutil.copyfileobj(inp, out)
                if not filecmp.cmp(src, dst, shallow=False):
                    raise ValueError('Private copy differs: ' + str(dst))
        for name in ['libbase', 'libcrypto', 'libaudioutils']:
            subprocess.run([sys.executable, str(pilots / (name + '-pilot/prepare-private-input.py')),
                            '--official-filesystems', str(fs), '--private-root', str(private / 'oem-abi')], check=True)
        subprocess.run([sys.executable, str(project / 'scripts/firmware-analysis/prepare_qcc_hal.py'),
                        '--firmware-root', str(fs), '--template-dir', str(project / 'device/xiaomi/popsicle/qcc'),
                        '--output', str(private / 'qcc-hal')], check=True)
        subprocess.run([sys.executable, str(project / 'device/xiaomi/popsicle/ims/prepare.py'),
                        str(android), str(project), str(fs)], check=True)
        subprocess.run([sys.executable, str(project / 'device/xiaomi/popsicle/carrier-config/prepare.py'),
                        str(android), str(project), str(fs)], check=True)
        subprocess.run([sys.executable, str(project / 'device/xiaomi/popsicle/carrier-apns/prepare.py'),
                        '--android', str(android), '--stock', str(fs)], check=True)
    else:
        # Check-only also covers all byte-preserved provider inputs and their declarations.
        for name in ['libbase', 'libcrypto', 'libaudioutils']:
            dst = regular(private / f'oem-abi/{name}/arm64/{name}.so')
            if not filecmp.cmp(regular(fs / f'vendor/lib64/{name}.so'), dst, shallow=False):
                raise ValueError('Provider differs from official input: ' + name)
        for name in ['qcc-hal/Android.bp', 'ims/Android.bp', 'ims/Android.mk', 'ims/ims.apk']:
            regular(private / name)
    subprocess.run([sys.executable, str(project / 'device/xiaomi/popsicle/oem-rear/prepare.py'),
                    str(android), str(fs)] + (['--dex-tools', str(args.dex_tools)] if args.dex_tools else [])
                    + (['--check'] if args.check else []), check=True)
    subprocess.run([sys.executable, str(project / 'device/xiaomi/popsicle/oem-camera/prepare.py'),
                    str(android), str(fs), '--host-bin', str(host)] + (['--check'] if args.check else []), check=True)
    print('PASS firmware/provider input preparation' if not args.check else
          'PASS firmware/provider byte checks; transformed IMS/QCC require their preparation and build checks')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
