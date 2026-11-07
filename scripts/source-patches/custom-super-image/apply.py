#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay super-image packaging and install its private input declaration."""
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
    private = 'vendor/xiaomi/popsicle-private'
    image = destination(plan.tree, private + '/prebuilt/firmware-a17/mi_product.img')
    if not image.is_file():
        raise ValueError('Missing verified official mi_product image: ' + str(image))
    declaration = source / 'private-inputs.bp'
    if declaration.is_symlink() or not declaration.is_file():
        raise ValueError('Missing regular private input declaration')
    target = destination(plan.tree, private + '/Android.bp')
    if target.exists() and (not target.is_file() or target.read_bytes() != declaration.read_bytes()):
        raise ValueError('Conflicting private input declaration: ' + str(target))
    plan.run(args.mode)
    if args.mode == '--apply':
        try:
            shutil.copyfile(declaration, target)
        except OSError:
            print('Patches applied; private declaration installation failed. Inspect before retrying.', file=sys.stderr)
            raise


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
