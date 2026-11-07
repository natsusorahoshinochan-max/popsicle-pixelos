#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a device-test-only KernelSU audio candidate from matching stock XML."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import zipfile

# The module and formal image producer use the same guarded transforms.
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2] /
                       'scripts/source-patches/firmware-filesystems'))
from audio_repair import STOCK_SHA256, HAL_SHA256, transform, patch_hal


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('stock', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--soong-zip', type=Path, required=True)
    parser.add_argument('--platform-property', action='store_true')
    parser.add_argument('--hal', type=Path)
    args = parser.parse_args()
    if args.platform_property:
        parser.error('v0.2 withdrawn: global property breaks PixelOS audio policy conversion')
    data = transform(args.stock.read_bytes())
    args.output.mkdir(parents=True, exist_ok=True)
    stage = args.output / 'module'
    stage.mkdir()
    here = Path(__file__).resolve().parent
    shutil.copy2(here / 'customize.sh', stage / 'customize.sh')
    version = '0.3' if args.hal else '0.1'
    (stage / 'module.prop').write_text(
        'id=popsicle-audio-fixes\nname=Popsicle Audio Fixes\n'
        f'version={version}\nversionCode={3 if args.hal else 1}\n'
        'author=PixelOS popsicle bring-up\n'
        'description=Device validation candidate: remove phantom FM input'
        + (' and correct HAL-local GSI detection' if args.hal else '')
        + '; disable and reboot to restore.\n')
    target = stage / 'system/vendor/etc/audio/audio_module_config_primary.xml'
    target.parent.mkdir(parents=True)
    target.write_bytes(data)
    manifest = [(str(target.relative_to(stage)), STOCK_SHA256,
                 hashlib.sha256(data).hexdigest(), 'vendor_configs_file')]
    if args.hal:
        hal_data = patch_hal(args.hal.read_bytes())
        hal_target = stage / 'system/vendor/lib64/hw/libaudiocorehal.qti.so'
        hal_target.parent.mkdir(parents=True)
        hal_target.write_bytes(hal_data)
        manifest.append((str(hal_target.relative_to(stage)), HAL_SHA256,
                         hashlib.sha256(hal_data).hexdigest(), 'vendor_file'))
    (stage / 'payload-manifest.txt').write_text(
        ''.join(' '.join(row) + '\n' for row in manifest))
    (stage / 'baseline-date').write_text('1789465178\n')
    (stage / 'stock-sha256').write_text(STOCK_SHA256 + '\n')
    (stage / 'payload-sha256').write_text(hashlib.sha256(data).hexdigest() + '\n')
    files = sorted(p for p in stage.rglob('*') if p.is_file())
    for path in files:
        path.chmod(0o755 if path.suffix == '.sh' else 0o644)
    listing = args.output / 'zip-inputs.txt'
    listing.write_text('\n'.join(str(p.resolve()) for p in files) + '\n')
    archive = args.output / f'popsicle-audio-fixes-v{version}.zip'
    subprocess.run([str(args.soong_zip), '-parallel', '16', '-o', str(archive),
                    '-C', str(stage), '-l', str(listing)], check=True)
    with zipfile.ZipFile(archive) as zipped:
        if set(zipped.namelist()) != {str(p.relative_to(stage)) for p in files}:
            raise ValueError('ZIP member mismatch')
        for path in files:
            if zipped.read(str(path.relative_to(stage))) != path.read_bytes():
                raise ValueError('ZIP payload mismatch')
    print(archive)


if __name__ == '__main__':
    main()
