#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay Aperture patches and install the accompanying cache sources."""
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.dont_write_bytecode = True
from replay import Replay, arguments, destination


def main():
    args = arguments(__doc__, with_series=False)
    source = Path(__file__).resolve().parent
    plan = Replay(args.tree, source / 'series')
    relative = 'packages/apps/Aperture/app/libs/popsicle-cache'
    target = destination(plan.tree, relative)
    if target.exists():
        raise ValueError('Cache source destination already exists: ' + str(target))
    files = [source / 'Android.bp', source / 'CameraExtensionCache.java']
    for path in files:
        if path.is_symlink() or not (path.is_file() or path.is_dir()):
            raise ValueError('Invalid cache source: ' + str(path))
    plan.run(args.mode)
    if args.mode == '--apply':
        try:
            target.mkdir(parents=True)
            for name in ('Android.bp', 'CameraExtensionCache.java'):
                shutil.copyfile(source / name, target / name)
        except OSError:
            print('Patches applied; cache source installation failed. Inspect before retrying.', file=sys.stderr)
            raise


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
