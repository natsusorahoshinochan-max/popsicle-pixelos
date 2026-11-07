#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package the ROM-built camera and its preoptimization for KernelSU testing."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('output', type=Path)
    args = parser.parse_args()
    tree = args.tree.resolve(strict=True)
    intermediates = (tree / 'out-pixelos-user/soong/.intermediates/vendor/xiaomi/'
                     'popsicle-private/prebuilt/oem-camera/PopsicleMiuiCamera/android_common')
    camera = 'system_ext/priv-app/PopsicleMiuiCamera'
    files = [camera + '/PopsicleMiuiCamera.apk',
             camera + '/oat/arm64/PopsicleMiuiCamera.odex',
             camera + '/oat/arm64/PopsicleMiuiCamera.vdex']
    sources = [intermediates / 'signed/PopsicleMiuiCamera.apk',
               intermediates / 'dexpreopt/PopsicleMiuiCamera/oat/arm64/package.odex',
               intermediates / 'dexpreopt/PopsicleMiuiCamera/oat/arm64/package.vdex']
    args.output.mkdir(parents=True, exist_ok=False)
    output = args.output.resolve()
    staging = output / 'module'
    staging.mkdir()
    here = Path(__file__).resolve().parent
    for name in ('module.prop', 'customize.sh', 'system.prop', 'README.md'):
        shutil.copy2(here / name, staging / name)
    payload = []
    for name, source in zip(files, sources):
        target = staging / 'system' / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
        payload.append('system/' + name)
    (staging / 'payload-files.txt').write_text('\n'.join(payload) + '\n')
    listing = output / 'zip-inputs.txt'
    listing.write_text('\n'.join(str(p) for p in sorted(staging.rglob('*'))
                                 if p.is_file()) + '\n')
    archive = output / 'popsicle-camera-dng-v0.3.zip'
    subprocess.run([str(tree / 'out-pixelos-user/host/linux-x86/bin/soong_zip'),
                    '-parallel', '16', '-o', str(archive), '-C', str(staging),
                    '-l', str(listing)], check=True)
    with archive.open('rb') as stream:
        digest = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(chunk)
    archive.with_suffix('.zip.sha256').write_text(digest.hexdigest() + '  ' + archive.name + '\n')
    print(archive)


if __name__ == '__main__':
    main()
