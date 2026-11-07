#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract the official A17 payload and filesystems required by ROM input preparation."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import tempfile


PARTITIONS = ('product', 'system_ext', 'vendor', 'odm', 'vendor_dlkm', 'system_dlkm')


def executable(path):
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ValueError('Expected executable tool: ' + str(path))
    return resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--payload', type=Path, required=True)
    parser.add_argument('--payload-dumper', type=Path, required=True,
                        help='payload-dumper-go executable')
    parser.add_argument('--fsck-erofs', type=Path, required=True,
                        help='Linux fsck.erofs supporting content extraction and explicit ownership options')
    parser.add_argument('--output', type=Path, required=True,
                        help='new directory receiving images/ and filesystems/')
    args = parser.parse_args()
    payload = args.payload.resolve(strict=True)
    if args.payload.is_symlink() or not payload.is_file():
        parser.error('Expected an original regular payload.bin')
    dumper = executable(args.payload_dumper)
    fsck = executable(args.fsck_erofs)
    output = args.output.absolute()
    if output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        parser.error('Output must be a new directory without symlink parents')
    if payload.is_relative_to(output):
        parser.error('Original payload and extracted output must be separate')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.official-a17-', dir=output.parent))
    try:
        images = stage / 'images'
        images.mkdir()
        subprocess.run([str(dumper), '-c', '4', '-o', str(images), str(payload)], check=True)
        filesystems = stage / 'filesystems'
        for partition in PARTITIONS:
            image = images / (partition + '.img')
            if image.is_symlink() or not image.is_file():
                raise ValueError('Missing original payload partition: ' + partition)
            directory = filesystems / partition
            directory.mkdir(parents=True)
            subprocess.run([str(fsck), '--extract=' + str(directory), '--no-xattrs',
                            '--no-preserve-owner', '--preserve-perms', str(image)], check=True)
        if 'OS4.0.0.23.XPBCNXM' not in (filesystems / 'product/etc/build.prop').read_text():
            raise ValueError('Expected the matching OS4.0.0.23.XPBCNXM original payload')
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(output)


if __name__ == '__main__':
    main()
