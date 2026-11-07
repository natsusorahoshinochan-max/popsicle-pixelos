#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay the PixelOS image/policy foundation and install maintained host sources."""
import runpy
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from replay import Replay, arguments, destination


def main():
    args = arguments(__doc__, with_series=False)
    source = Path(__file__).resolve().parent
    plan = Replay(args.tree, source / 'pixelos-foundation.series')
    for name in ('boot', 'dtbo', 'vendor_boot', 'vbmeta', 'vbmeta-witness',
                 'vendor', 'odm', 'mi_product', 'vendor_dlkm', 'system_dlkm'):
        image = destination(plan.tree,
                            'vendor/xiaomi/popsicle-private/prebuilt/firmware-a17/'
                            + name + '.img')
        if not image.is_file():
            raise ValueError('Prepare matching official inputs first: ' + str(image))
    # Reuse the single maintained source inventory; camera inputs have their own stage.
    copies = runpy.run_path(str(source / 'prepare-public-source.py'))['copies']
    pending = []
    for src, relative in copies(source):
        if not relative.startswith('external/erofs-utils/popsicle/'):
            continue
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
                destination(plan.tree, str(dst.relative_to(plan.tree)))
                dst.write_bytes(data)
        except OSError:
            print('Patches applied; host source installation incomplete. Inspect before retrying.',
                  file=sys.stderr)
            raise
    print(f'PASS PixelOS foundation host inputs: {len(pending)} new files ({args.mode})')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
