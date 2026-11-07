#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Stage the fixed APK and converter inputs used by the Android generation rule."""
import argparse
import hashlib
import json
from pathlib import Path, PurePosixPath
import tempfile
import zipfile

HERE = Path(__file__).resolve().parent
PRIVATE = Path('vendor/xiaomi/popsicle-private/prebuilt/turbo-r8/inputs')


def digest(data):
    return hashlib.sha256(data).hexdigest()


def staged_files(root):
    if any(path.is_symlink() for path in [root, *root.parents]):
        raise ValueError('Private input destination contains a symlink')
    result = {}
    for path in root.rglob('*'):
        if path.is_symlink():
            raise ValueError('Symlink in private inputs: ' + str(path))
        if path.is_file():
            result[str(path.relative_to(root))] = path
    return result


def validate(tree):
    lock = json.loads((HERE / 'dependencies.json').read_text())
    inputs = tree / PRIVATE
    actual = staged_files(inputs)
    expected = json.loads((inputs / 'manifest.json').read_text())
    if expected['apk_sha256'] != lock['apk_sha256'] or expected['dex2jar_zip_sha256'] != lock['dex2jar_zip_sha256']:
        raise ValueError('Private converter inputs differ from the fixed source inputs')
    if set(actual) != set(expected['files']) | {'manifest.json'}:
        raise ValueError('Unexpected or missing private input files')
    for name, sha in expected['files'].items():
        relative = PurePosixPath(name)
        if relative.is_absolute() or '..' in relative.parts:
            raise ValueError('Invalid staged input path')
        path = inputs / name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != sha:
            raise ValueError('Missing or changed private input: ' + str(path))
    if expected['files'].get('TurboAdapter.apk') != lock['apk_sha256']:
        raise ValueError('Missing fixed TurboAdapter APK')
    for name, (_, _, sha) in lock['r8_files'].items():
        path = tree / 'prebuilts/r8' / name
        if path.is_symlink() or not path.is_file() or digest(path.read_bytes()) != sha:
            raise ValueError('Prepare R8 9.3.19 first: ' + name)


def prepare(tree, apk, archive):
    lock = json.loads((HERE / 'dependencies.json').read_text())
    if digest(apk.read_bytes()) != lock['apk_sha256'] or digest(archive.read_bytes()) != lock['dex2jar_zip_sha256']:
        raise ValueError('Unrecognized APK or converter archive')
    files = {'TurboAdapter.apk': apk.read_bytes()}
    with zipfile.ZipFile(archive) as zipped:
        for name in zipped.namelist():
            relative = PurePosixPath(name)
            if relative.parts[:2] == ('dex-tools-v2.4', 'lib') and relative.suffix == '.jar':
                if len(relative.parts) != 3 or name != str(relative):
                    raise ValueError('Invalid converter library path')
                files['dex-tools/lib/' + relative.name] = zipped.read(name)
    if len(files) == 1:
        raise ValueError('Converter archive contains no libraries')
    manifest = {'apk_sha256': lock['apk_sha256'], 'dex2jar_zip_sha256': lock['dex2jar_zip_sha256'],
                'files': {name: digest(data) for name, data in sorted(files.items())}}
    files['manifest.json'] = (json.dumps(manifest, indent=2) + '\n').encode()
    destination = tree / PRIVATE
    if any(path.is_symlink() for path in [destination, *destination.parents]):
        raise ValueError('Private input destination contains a symlink')
    if destination.exists():
        if set(staged_files(destination)) != set(files):
            raise ValueError('Unexpected or missing private input files')
        for name, data in files.items():
            path = destination / name
            if path.is_symlink() or not path.is_file() or path.read_bytes() != data:
                raise ValueError('Conflicting private input: ' + str(path))
        return
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(dir=destination.parent) as temporary:
        staged = Path(temporary) / 'inputs'
        for name, data in files.items():
            path = staged / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        staged.rename(destination)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('tree', type=Path)
    parser.add_argument('--apk', type=Path)
    parser.add_argument('--dex-tools', type=Path)
    args = parser.parse_args()
    tree = args.tree.resolve(strict=True)
    if args.check:
        if args.apk or args.dex_tools:
            parser.error('--check uses the already staged inputs')
        validate(tree)
    else:
        if args.apk is None or args.dex_tools is None:
            parser.error('Provide --apk and --dex-tools')
        prepare(tree, args.apk, args.dex_tools)
    print('PASS fixed TurboAdapter source inputs')


if __name__ == '__main__':
    main()
