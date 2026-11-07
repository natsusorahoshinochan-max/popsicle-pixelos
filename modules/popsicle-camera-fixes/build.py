#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package the ROM-built cameraserver and signed camera APK as a KernelSU delta."""
import argparse
from pathlib import Path
import shutil
import subprocess
import zipfile


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--baseline-date', required=True)
    args = parser.parse_args()
    if not args.baseline_date.isdecimal():
        parser.error('baseline-date must be a UTC epoch integer')
    product = args.tree / 'out-pixelos-user/target/product/popsicle'
    camera = 'system_ext/priv-app/PopsicleMiuiCamera'
    files = ['system/bin/cameraserver', camera + '/PopsicleMiuiCamera.apk',
             camera + '/oat/arm64/PopsicleMiuiCamera.odex',
             camera + '/oat/arm64/PopsicleMiuiCamera.vdex']
    for name in files:
        if not (product / name).is_file() or (product / name).is_symlink():
            raise ValueError('Missing regular ROM output: ' + name)
    args.output.mkdir(parents=True, exist_ok=True)
    staging = args.output / 'module'
    staging.mkdir()
    here = Path(__file__).resolve().parent
    for name in ['module.prop', 'customize.sh']:
        shutil.copy2(here / name, staging / name)
    payload = []
    for name in files:
        relative = name if name.startswith('system/') else 'system/' + name
        target = staging / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(product / name, target)
        payload.append(relative)
    (staging / 'system/bin/cameraserver').chmod(0o755)
    (staging / 'baseline-date').write_text(args.baseline_date + '\n')
    (staging / 'payload-files.txt').write_text('\n'.join(payload) + '\n')
    paths = sorted(p for p in staging.rglob('*') if p.is_file())
    listing = args.output / 'zip-inputs.txt'
    listing.write_text('\n'.join(str(p) for p in paths) + '\n')
    archive = args.output / 'popsicle-camera-fixes-v0.1.zip'
    subprocess.run([str(args.tree / 'out-pixelos-user/host/linux-x86/bin/soong_zip'),
                    '-parallel', '16', '-o', str(archive), '-C', str(staging),
                    '-l', str(listing)], check=True)
    with zipfile.ZipFile(archive) as zipped:
        names = zipped.namelist()
        if len(names) != len(paths) or set(names) != {str(p.relative_to(staging)) for p in paths}:
            raise ValueError('Archive payload differs from staging')
        if zipped.testzip() is not None:
            raise ValueError('Archive CRC verification failed')
    print(archive)


if __name__ == '__main__':
    main()
