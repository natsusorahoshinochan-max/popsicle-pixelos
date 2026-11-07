#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare installer tools from three local Android SDK Platform-Tools ZIPs."""

import argparse
from pathlib import Path
import shutil
import tempfile
import zipfile


TOOLS = {
    'Linux': ('fastboot', 'make_f2fs', 'make_f2fs_casefold', 'lib64/libc++.so'),
    'macOS': ('fastboot', 'make_f2fs', 'make_f2fs_casefold', 'lib64/libc++.dylib'),
    'Windows': ('fastboot.exe', 'make_f2fs.exe', 'make_f2fs_casefold.exe', 'AdbWinApi.dll', 'AdbWinUsbApi.dll'),
}


def prepare(archives, output):
    output.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.platform-tools-', dir=output.parent) as name:
        staging = Path(name) / 'tools'
        for platform, source in archives.items():
            with zipfile.ZipFile(source) as archive:
                for relative in (*TOOLS[platform], 'NOTICE.txt', 'source.properties'):
                    target = staging / platform / relative
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(archive.read('platform-tools/' + relative))
                    target.chmod(0o755 if relative in TOOLS[platform] else 0o644)
        output.mkdir()
        try:
            for path in staging.iterdir():
                shutil.move(str(path), str(output / path.name))
        except BaseException:
            shutil.rmtree(output)
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--linux', type=Path, required=True)
    parser.add_argument('--macos', type=Path, required=True)
    parser.add_argument('--windows', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    prepare({'Linux': args.linux, 'macOS': args.macos, 'Windows': args.windows}, args.output)
    print(args.output)


if __name__ == '__main__':
    main()
