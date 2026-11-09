#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract the official A17 payload and filesystems required by ROM input preparation."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import zipfile


PARTITIONS = ('product', 'system_ext', 'vendor', 'odm', 'vendor_dlkm', 'system_dlkm', 'mi_ext')
VERSION = 'OS4.0.0.23.XPBCNXM'
PAYLOAD_SHA256 = 'b614dabafabff794177e24f5ae3f3ef251043527122f2b6e4da535d6473155c4'
PAYLOAD_BYTES = 9121308331


def copy_payload(source, target):
    """Copy just the payload member, never extract arbitrary archive paths."""
    digest = hashlib.sha256()
    size = 0
    with target.open('xb') as output:
        for block in iter(lambda: source.read(4 * 1024 * 1024), b''):
            size += len(block)
            if size > PAYLOAD_BYTES:
                raise ValueError('Payload exceeds the fixed firmware size')
            digest.update(block)
            output.write(block)
    if size != PAYLOAD_BYTES or digest.hexdigest() != PAYLOAD_SHA256:
        raise ValueError('Expected the original full ' + VERSION + ' payload')


def executable(path):
    resolved = path.resolve(strict=True)
    if not resolved.is_file() or not os.access(resolved, os.X_OK):
        raise ValueError('Expected executable tool: ' + str(path))
    return resolved


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    original = parser.add_mutually_exclusive_group(required=True)
    original.add_argument('--rom', type=Path, help='official full OTA ZIP containing payload.bin')
    original.add_argument('--payload', type=Path, help='original payload.bin extracted from that OTA')
    parser.add_argument('--payload-dumper', type=Path, required=True,
                        help='payload-dumper-go executable')
    parser.add_argument('--fsck-erofs', type=Path, required=True,
                        help='Linux fsck.erofs supporting content extraction and explicit ownership options')
    parser.add_argument('--output', type=Path, required=True,
                        help='new directory receiving images/ and filesystems/')
    args = parser.parse_args()
    original = args.rom or args.payload
    if original.is_symlink() or not original.is_file():
        parser.error('Expected an original regular OTA ZIP or payload.bin')
    original = original.resolve(strict=True)
    dumper = executable(args.payload_dumper)
    fsck = executable(args.fsck_erofs)
    output = args.output.absolute()
    if output.exists() or any(p.is_symlink() for p in [output, *output.parents]):
        parser.error('Output must be a new directory without symlink parents')
    if original.is_relative_to(output):
        parser.error('Original payload and extracted output must be separate')
    output.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.official-a17-', dir=output.parent))
    try:
        payload = stage / 'payload.bin'
        if args.rom:
            with zipfile.ZipFile(original) as archive:
                members = [m for m in archive.infolist() if m.filename == 'payload.bin']
                if len(members) != 1 or members[0].file_size != PAYLOAD_BYTES:
                    raise ValueError('Expected exactly one full-size payload.bin in the OTA ZIP')
                with archive.open(members[0]) as stream:
                    copy_payload(stream, payload)
        else:
            with original.open('rb') as stream:
                copy_payload(stream, payload)
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
        if VERSION not in (filesystems / 'product/etc/build.prop').read_text():
            raise ValueError('Expected the matching OS4.0.0.23.XPBCNXM original payload')
        (stage / 'source.json').write_text(json.dumps({
            'firmware': VERSION, 'payload_sha256': PAYLOAD_SHA256,
            'payload_bytes': PAYLOAD_BYTES,
        }, indent=2) + '\n')
        stage.rename(output)
    finally:
        if stage.exists():
            shutil.rmtree(stage)
    print(output)


if __name__ == '__main__':
    main()
