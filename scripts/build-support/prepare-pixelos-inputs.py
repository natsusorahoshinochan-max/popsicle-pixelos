#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare private PixelOS inputs with explicit or checked-in SDK host tools."""
import argparse
from pathlib import Path
import subprocess
import sys


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    source = commands.add_parser('source', help='prepare the official firmware/provider inputs')
    source.add_argument('--android', type=Path, required=True)
    source.add_argument('--images', type=Path, required=True)
    source.add_argument('--filesystems', type=Path, required=True)
    source.add_argument('--dex-tools', type=Path, help='dex2jar distribution for rear APK preparation')
    source.add_argument('--check', action='store_true')
    source.add_argument('--host-bin', type=Path,
                        help='directory containing aapt2, defaulting to the checked-in SDK tools')
    aicore = commands.add_parser('aicore', help='wrap the verified Play-delivered split set')
    aicore.add_argument('--android', type=Path, required=True)
    aicore.add_argument('--inputs', type=Path, required=True)
    aicore.add_argument('--host-bin', type=Path,
                        help='directory containing apksigner and aapt2, defaulting to the SDK tools')
    aicore.add_argument('--protoc', type=Path,
                        help='protobuf compiler, defaulting to HOST_BIN/aprotoc')
    carrier = commands.add_parser('carrier', help='convert stock global carrier and APN data')
    carrier.add_argument('--android', type=Path, required=True)
    carrier.add_argument('--filesystems', type=Path, required=True)
    args = parser.parse_args()
    project = Path(__file__).resolve().parents[2]
    android = args.android.resolve(strict=True)
    if args.command == 'carrier':
        subprocess.run([sys.executable,
                        str(project / 'device/xiaomi/popsicle/carrier-config/prepare.py'),
                        str(android), str(project), str(args.filesystems)], check=True)
        subprocess.run([sys.executable,
                        str(project / 'device/xiaomi/popsicle/carrier-apns/prepare.py'),
                        '--android', str(android), '--stock', str(args.filesystems)], check=True)
        return
    host = args.host_bin or android / 'prebuilts/sdk/tools/linux/bin'
    if args.command == 'source':
        command = [project / 'scripts/build-support/prepare-source-inputs.py',
                   '--android', android, '--images', args.images, '--filesystems', args.filesystems]
        if args.dex_tools:
            command += ['--dex-tools', args.dex_tools]
        if args.check:
            command.append('--check')
    else:
        command = [project / 'device/xiaomi/popsicle/aicore/prepare.py', android, args.inputs]
        if args.protoc:
            command += ['--protoc', args.protoc]
    subprocess.run([sys.executable, *map(str, command), '--host-bin', str(host)], check=True)


if __name__ == '__main__':
    main()
