#!/usr/bin/env python3
"""Repackage an already validated three-platform ROM with the current installer."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess

CHUNK = 8 * 1024 * 1024


def digest(stream):
    value = hashlib.sha256()
    for block in iter(lambda: stream.read(CHUNK), b''):
        value.update(block)
    return value.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    package = args.output.absolute()
    archive = package.with_name(package.name + '.tar.gz')
    if package.exists() or archive.exists():
        parser.error('output package/archive already exists; choose a new output')
    sums = {}
    for line in (source / 'metadata/SHA256SUMS').read_text().splitlines():
        checksum, name = line.split('  ', 1)
        if name in sums or Path(name).is_absolute() or '..' in Path(name).parts:
            parser.error('invalid source checksum inventory')
        sums[name] = checksum
    image_names = {n for n in sums if n.startswith('images/') and n.endswith('.img')}
    if len(image_names) != 50:
        parser.error('expected validated 50-image source package')
    package.mkdir(parents=True)
    for folder in ('images', 'tools'):
        # Existing validated payloads are read-only inputs. Hardlinks avoid duplicate data.
        shutil.copytree(source / folder, package / folder, copy_function=os.link)
    (package / 'metadata').mkdir()
    (package / 'logs').mkdir()
    shutil.copy2(source / 'metadata/flash-manifest.tsv', package / 'metadata/flash-manifest.tsv')
    installer = Path(__file__).resolve().parent / 'installer'
    shutil.copytree(installer, package, dirs_exist_ok=True)
    readme = source / 'README.md'
    if readme.is_file():
        shutil.copy2(readme, package / 'README.md')
    checksums = {}
    for path in sorted(package.rglob('*')):
        if path.is_symlink():
            raise ValueError(f'symlink in package: {path}')
        if not path.is_file():
            continue
        name = path.relative_to(package).as_posix()
        if name.startswith(('images/', 'tools/')):
            checksums[name] = sums[name]
        else:
            with path.open('rb') as stream:
                checksums[name] = digest(stream)
    (package / 'metadata/SHA256SUMS').write_text(''.join(
        f'{checksums[name]}  {name}\n' for name in sorted(checksums)))
    subprocess.run(['tar', '--use-compress-program=pigz -p 16',
                    '-cf', str(archive), '-C', str(package.parent),
                    '--', package.name], check=True)
    with archive.open('rb') as stream:
        checksum = digest(stream)
    archive.with_name(archive.name + '.sha256').write_text(f'{checksum}  {archive.name}\n')
    report = dict(complete=True, archive=str(archive), sha256=checksum,
                  bytes=archive.stat().st_size,
                  image_count=len(image_names), images_unchanged=True,
                  rom_rebuilt=False, device_flashed=False)
    archive.with_name(archive.name + '.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
