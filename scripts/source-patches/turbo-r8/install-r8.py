#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Install only fixed, verified R8 inputs; preflight every destination first."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys


def plan(tree, cache):
    lock = json.loads(Path(__file__).with_name('dependencies.json').read_text())
    repo = tree / 'prebuilts/r8'
    if subprocess.check_output(['git', '-C', str(repo), 'rev-parse', 'HEAD'], text=True).strip() != lock['r8_repository_head']:
        raise ValueError('Unexpected R8 base HEAD')
    result = []
    for name, (source, old, new) in lock['r8_files'].items():
        dst, src = repo / name, cache / source
        for path in (src, dst):
            if path.is_symlink() or not path.is_file():
                raise ValueError('Expected regular file: ' + str(path))
        data = src.read_bytes()
        if hashlib.sha256(data).hexdigest() != new:
            raise ValueError('Dependency hash mismatch: ' + source)
        actual = hashlib.sha256(dst.read_bytes()).hexdigest()
        if actual not in (old, new):
            raise ValueError('Conflicting destination: ' + str(dst))
        if actual == old:
            result.append((dst, data))
    return result


def main():
    if len(sys.argv) != 4 or sys.argv[1] not in ('--check', '--apply'):
        raise ValueError('Usage: install-r8.py --check|--apply TREE VERIFIED_DOWNLOAD_DIRECTORY')
    pending = plan(Path(sys.argv[2]).resolve(), Path(sys.argv[3]).resolve())
    if sys.argv[1] == '--apply':
        for dst, data in pending:
            temporary = dst.with_name(dst.name + '.popsicle-new')
            with temporary.open('xb') as stream:
                stream.write(data)
            os.replace(temporary, dst)
    print('PASS R8 dependency inputs:', len(pending), sys.argv[1])


if __name__ == '__main__':
    main()
