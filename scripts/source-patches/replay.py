#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replay one ordered, revision-pinned series without changing the real Git index."""

import argparse
import os
from pathlib import Path, PurePosixPath
import subprocess
import sys
import tempfile

RETIRED = Path('/root/autodl-tmp/lineage-24.0')
ARCHIVE = Path('/root/autodl-tmp/popsicle-archive')


def allowed_root(path):
    path = Path(path).resolve(strict=True)
    if path == RETIRED or RETIRED in path.parents:
        raise ValueError('Refusing the retired source tree: ' + str(path))
    if path == ARCHIVE or ARCHIVE in path.parents or 'repositories-readonly' in path.parts:
        raise ValueError('Refusing archived or read-only sources: ' + str(path))
    if not path.is_dir():
        raise ValueError('Expected a directory: ' + str(path))
    return path


def destination(root, name):
    """Resolve a tree-relative destination, rejecting links and non-directory parents."""
    relative = PurePosixPath(name)
    if relative.is_absolute() or '..' in relative.parts or not relative.parts:
        raise ValueError('Invalid tree-relative path: ' + name)
    path = root
    for part in relative.parts:
        path = path / part
        if path.is_symlink():
            raise ValueError('Symlink destination: ' + str(path))
        if path != root / relative and path.exists() and not path.is_dir():
            raise ValueError('Non-directory parent: ' + str(path))
    return path


def git(directory, *arguments):
    # Caller Git environment must not redirect writes to another worktree/index.
    env = {key: value for key, value in os.environ.items() if not key.startswith('GIT_')}
    return subprocess.check_output(
        ['git', '-C', str(directory), *arguments], env=env)


class Replay:
    """Validate and execute the same immutable series; product adapters own extra files."""

    def __init__(self, tree, series):
        self.tree = allowed_root(tree)
        self.entries = []
        self.repositories = {}
        series = Path(series).resolve(strict=True)
        for number, line in enumerate(series.read_text().splitlines(), 1):
            if not line.strip() or line.lstrip().startswith('#'):
                continue
            fields = line.split()
            if len(fields) != 3:
                raise ValueError(f'{series}:{number}: expected repository revision patch')
            repo, revision, name = fields
            directory = allowed_root(destination(self.tree, repo))
            if Path(git(directory, 'rev-parse', '--show-toplevel').decode().strip()).resolve() != directory:
                raise ValueError('Series path is not a repository root: ' + repo)
            previous = self.repositories.get(directory)
            if previous is not None and previous != revision:
                raise ValueError('Conflicting revisions in ' + repo)
            self.repositories[directory] = revision
            # Sibling patch references are intentional (firmware-filesystems -> camera).
            patch = (series.parent / name).resolve(strict=True)
            if not patch.is_file():
                raise ValueError('Expected a patch file: ' + str(patch))
            self.entries.append((directory, name, patch.read_bytes()))
        if not self.entries:
            raise ValueError('Empty patch series')

    def run(self, mode):
        if mode not in ('--check', '--apply'):
            raise ValueError('Expected --check or --apply')
        with tempfile.TemporaryDirectory(prefix='popsicle-replay-') as temporary:
            scratch = Path(temporary)
            groups = {}
            patches = []
            for index, (directory, name, data) in enumerate(self.entries):
                patch = scratch / f'{index}.patch'
                patch.write_bytes(data)
                patches.append((directory, name, patch))
                groups.setdefault(directory, []).append(data)
                records = git(directory, 'apply', '--numstat', '-z', str(patch))
                if not records:
                    raise ValueError('Empty patch: ' + name)
                for record in records.split(b'\0'):
                    if not record:
                        continue
                    fields = record.split(b'\t', 2)
                    if len(fields) != 3 or not fields[2]:
                        raise ValueError('Unsupported rename entry: ' + name)
                    target = destination(directory, os.fsdecode(fields[2]))
                    if target.exists() and not target.is_file():
                        raise ValueError('Patch target must be a regular file: ' + str(target))
            for index, (directory, data) in enumerate(groups.items()):
                revision = self.repositories[directory]
                actual = git(directory, 'rev-parse', 'HEAD').decode().strip()
                if actual != revision:
                    raise ValueError(f'Unexpected revision in {directory}: {actual} (expected {revision})')
                bundle = scratch / f'bundle-{index}.patch'
                bundle.write_bytes(b''.join(part + (b'' if part.endswith(b'\n') else b'\n') for part in data))
                git(directory, 'apply', '--check', '--whitespace=warn', str(bundle))
            print(f'PASS ordered patch preflight: {len(patches)} patches, {len(groups)} repositories', flush=True)
            if mode == '--check':
                return
            completed = []
            try:
                for directory, name, patch in patches:
                    git(directory, 'apply', '--whitespace=warn', str(patch))
                    completed.append(f'{directory.relative_to(self.tree)}: {name}')
            except (OSError, subprocess.CalledProcessError):
                print('Replay stopped; completed patches: ' + (', '.join(completed) or 'none'), file=sys.stderr)
                print('Inspect the working tree before retrying; no automatic rollback.', file=sys.stderr)
                raise
            print(f'PASS applied {len(completed)} patches', flush=True)


def arguments(description, with_series=True):
    parser = argparse.ArgumentParser(description=description)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument('--check', dest='mode', action='store_const', const='--check')
    mode.add_argument('--apply', dest='mode', action='store_const', const='--apply')
    parser.add_argument('tree', type=Path)
    if with_series:
        parser.add_argument('series', type=Path)
    return parser.parse_args()


def main():
    args = arguments(__doc__)
    Replay(args.tree, args.series).run(args.mode)


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
