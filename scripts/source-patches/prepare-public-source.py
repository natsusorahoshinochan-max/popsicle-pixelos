#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the complete PixelOS user series and install its maintained source inputs."""
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from replay import Replay, arguments, destination


def copies(source):
    firmware = source / 'firmware-filesystems'
    for directory in [firmware / 'policy']:
        if directory.is_symlink() or not directory.is_dir():
            raise ValueError('Expected source directory: ' + str(directory))
        if any(p.is_symlink() for p in directory.rglob('*')):
            raise ValueError('Symlink in source directory: ' + str(directory))
    names = ['LICENSE', 'erofs_readback.c', 'audio_repair.py']
    names += ('derive_vendor.py stage_inputs.py vendor_avb.py vendor_target_files.py '
              'vendor_policy.py odm_tool.py odm_image.py odm_avb.py odm_target_files.py').split()
    names += [str(p.relative_to(firmware)) for p in (firmware / 'policy').glob('*.py')
              if not p.name.startswith('.')]
    names += ['policy-producers/NOTICE', 'policy-producers/mediacodec.te']
    result = [(firmware / n, 'external/erofs-utils/popsicle/' + n) for n in names]
    cache = source / 'camera-extensions'
    result += [(cache / n, 'packages/apps/Aperture/app/libs/popsicle-cache/' + n)
               for n in ['Android.bp', 'CameraExtensionCache.java']]
    result.append((source / 'custom-super-image/private-inputs.bp',
                   'vendor/xiaomi/popsicle-private/Android.bp'))
    result.append((source / 'turbo-r8/private-jar.bp',
                   'vendor/xiaomi/popsicle-private/prebuilt/turbo-r8/Android.bp'))
    result += [(source / 'turbo-r8' / name,
                'frameworks/base/tools/popsicle-turbo/' + name)
               for name in ('Android.bp', 'NormalizeTurbo.java', 'Ir2JRegAssignTransformer.java',
                            'generate.py', 'dex-types.py', 'filter-turbo.py', 'dependencies.json')]
    return result


def main(series_name="pixelos-public-user.series",
         firmware_images=("boot", "dtbo", "vendor_boot", "vbmeta", "vbmeta-witness",
                          "vendor", "odm", "mi_product", "vendor_dlkm", "system_dlkm")):
    args = arguments(__doc__, with_series=False)
    source = Path(__file__).resolve().parent
    if series_name == 'pixelos-public-user.series':
        subprocess.run([sys.executable, str(source / 'turbo-r8/prepare-inputs.py'),
                        '--check', str(args.tree)], check=True)
    plan = Replay(args.tree, source / series_name)
    for name in firmware_images:
        image = destination(plan.tree,
                            'vendor/xiaomi/popsicle-private/prebuilt/firmware-a17/' + name + '.img')
        if not image.is_file():
            raise ValueError('Prepare the matching private firmware inputs first: ' + str(image))
    pending = []
    for src, relative in copies(source):
        dst = destination(plan.tree, relative)
        if src.is_symlink() or not src.is_file():
            raise ValueError('Expected a regular maintained source: ' + str(src))
        data = src.read_bytes()
        if dst.exists():
            if not dst.is_file() or dst.read_bytes() != data:
                raise ValueError('Conflicting source destination: ' + str(dst))
        else:
            pending.append((dst, data))
    plan.run(args.mode)
    if args.mode == '--apply':
        try:
            for dst, data in pending:
                dst.parent.mkdir(parents=True, exist_ok=True)
                # A patch may create an older helper at a previously absent target.
                # Install its maintained final source after the ordered series.
                destination(plan.tree, str(dst.relative_to(plan.tree)))
                dst.write_bytes(data)
        except OSError:
            print('Patches applied; source installation incomplete. Inspect before retrying.', file=sys.stderr)
            raise
    print(f'PASS source inputs: {len(pending)} new files ({args.mode})')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
