#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay PixelOS camera, biometrics and display repairs with maintained cache sources."""
import runpy
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from replay import Replay, arguments, destination


def main():
    args = arguments(__doc__, with_series=False)
    source = Path(__file__).resolve().parent
    plan = Replay(args.tree, source / 'pixelos-hardware.series')
    # Reuse the sole maintained inventory for the complete camera cache stage.
    copies = runpy.run_path(str(source / 'prepare-public-source.py'))['copies']
    pending = []
    for src, relative in copies(source):
        if not relative.startswith('packages/apps/Aperture/app/libs/popsicle-cache/'):
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
            print('Patches applied; camera source installation incomplete. Inspect before retrying.',
                  file=sys.stderr)
            raise
    print(f'PASS PixelOS hardware cache inputs: {len(pending)} new files ({args.mode})')


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
