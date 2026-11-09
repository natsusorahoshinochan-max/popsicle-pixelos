#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare private PixelOS inputs with explicit or checked-in SDK host tools."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile

sys.dont_write_bytecode = True
VERSION = 'OS4.0.0.23.XPBCNXM'
PAYLOAD_SHA256 = 'b614dabafabff794177e24f5ae3f3ef251043527122f2b6e4da535d6473155c4'


def digest(path):
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def download(url, path, expected):
    if path.is_symlink():
        raise ValueError('Download path must not be a symlink: ' + str(path))
    if path.exists():
        if digest(path) != expected:
            raise ValueError('Existing download has the wrong SHA256: ' + str(path))
        return
    with tempfile.NamedTemporaryFile(dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            with urllib.request.urlopen(url, timeout=120) as response:
                shutil.copyfileobj(response, stream)
            stream.flush()
            if digest(temporary) != expected:
                raise ValueError('Download SHA256 mismatch: ' + url)
            temporary.replace(path)
        except OSError as error:
            raise ValueError('Could not download ' + url + ': ' + str(error)) from error
        finally:
            temporary.unlink(missing_ok=True)


def prepare_all(args, project, android):
    workspace = args.workspace.absolute()
    if any(p.is_symlink() for p in [workspace, *workspace.parents]):
        raise ValueError('Workspace must not use symlink paths')
    workspace.mkdir(parents=True, exist_ok=True)
    workspace = workspace.resolve()
    if workspace == project or workspace.is_relative_to(project) or workspace == android or workspace.is_relative_to(android):
        raise ValueError('Use a workspace outside the maintenance checkout and Android tree')
    host = android / 'prebuilts/sdk/tools/linux/bin'
    firmware = workspace / 'work/firmware' / VERSION
    cache = workspace / 'tools/downloads'
    for path in (firmware, cache):
        if any(p.is_symlink() for p in [path, *path.parents]):
            raise ValueError('Generated paths must not use symlinks: ' + str(path))
    cache.mkdir(parents=True, exist_ok=True)
    original = args.rom or args.payload
    if original.is_symlink() or not original.is_file():
        raise ValueError('Provide an original regular OTA ZIP or payload.bin')
    for name in ('base.apk', 'split_config.arm64_v8a.apk', 'split_config.en.apk',
                 'split_config.es.apk', 'split_config.zh.apk', 'split_config.xxhdpi.apk'):
        if (args.aicore / name).is_symlink() or not (args.aicore / name).is_file():
            raise ValueError('Missing original AICore APK: ' + name)
    for tool in (host / 'aapt2', android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'):
        if not tool.is_file():
            raise ValueError('Missing fixed Android host tool: ' + str(tool))
    protoc = shutil.which('protoc')
    if not protoc:
        raise ValueError('Install protobuf-compiler (protoc) first')
    def run(script, *arguments):
        subprocess.run([sys.executable, str(project / script), *map(str, arguments)], check=True)
    lock = json.loads((project / 'scripts/source-patches/turbo-r8/dependencies.json').read_text())
    for source, _, sha in lock['r8_files'].values():
        download('https://storage.googleapis.com/r8-releases/raw/' + lock['r8_version'] + '/' + source,
                 cache / source, sha)
    archive = cache / 'dex-tools-v2.4.zip'
    download('https://github.com/pxb1988/dex2jar/releases/download/v2.4/dex-tools-v2.4.zip?download=1',
             archive, lock['dex2jar_zip_sha256'])
    turbo = android / 'vendor/pixel/gms/common/proprietary/system_ext/priv-app/TurboAdapter/TurboAdapter.apk'
    if turbo.is_symlink() or digest(turbo) != lock['apk_sha256']:
        raise ValueError('Fixed upstream TurboAdapter APK is missing or changed; sync Git/LFS inputs first')
    run('scripts/source-patches/turbo-r8/install-r8.py', '--apply', android, cache)
    run('scripts/source-patches/turbo-r8/prepare-inputs.py', android, '--apk', turbo, '--dex-tools', archive)
    if firmware.exists():
        record = json.loads((firmware / 'source.json').read_text())
        if record.get('payload_sha256') != PAYLOAD_SHA256 or digest(firmware / 'payload.bin') != PAYLOAD_SHA256:
            raise ValueError('Existing extraction does not match the fixed official payload')
        # Also check the newly supplied original, including when resuming preparation.
        if args.rom:
            with zipfile.ZipFile(args.rom) as ota:
                matches = [m for m in ota.infolist() if m.filename == 'payload.bin']
                if len(matches) != 1 or matches[0].file_size != 9121308331:
                    raise ValueError('Expected one payload.bin in the OTA ZIP')
                with ota.open(matches[0]) as stream:
                    h = hashlib.sha256()
                    for block in iter(lambda: stream.read(4 * 1024 * 1024), b''):
                        h.update(block)
                if h.hexdigest() != PAYLOAD_SHA256:
                    raise ValueError('OTA does not match the fixed firmware')
        elif digest(args.payload) != PAYLOAD_SHA256:
            raise ValueError('Original payload does not match the fixed firmware')
    else:
        run('scripts/firmware-analysis/extract-firmware-inputs.py',
            '--rom' if args.rom else '--payload', args.rom or args.payload,
            '--payload-dumper', args.payload_dumper, '--fsck-erofs', args.fsck_erofs,
            '--output', firmware)
    if not (firmware / 'filesystems/mi_ext/product/etc/vendor_miui.xml').is_file():
        raise ValueError('Incomplete firmware extraction: mi_ext carrier input is missing; '
                         'extract the official payload into a new directory')
    # The rear APK converter consumes a directory of JARs; Turbo consumes the original ZIP.
    with tempfile.TemporaryDirectory(prefix='dex-tools-', dir=cache) as temporary:
        dex_tools = Path(temporary)
        (dex_tools / 'lib').mkdir()
        with zipfile.ZipFile(archive) as zipped:
            for member in zipped.infolist():
                relative = Path(member.filename)
                if relative.parts[:2] == ('dex-tools-v2.4', 'lib') and relative.suffix == '.jar':
                    if len(relative.parts) != 3 or member.filename != relative.as_posix():
                        raise ValueError('Invalid dex2jar library path')
                    (dex_tools / 'lib' / relative.name).write_bytes(zipped.read(member))
        run('scripts/build-support/prepare-source-inputs.py', '--android', android,
            '--images', firmware / 'images', '--filesystems', firmware / 'filesystems',
            '--host-bin', host, '--dex-tools', dex_tools)
    run('device/xiaomi/popsicle/aicore/prepare.py', android, args.aicore,
        '--host-bin', host, '--protoc', protoc)
    print('Prepared inputs for ' + str(android))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    complete = commands.add_parser('all', help='prepare fixed inputs from an official OTA and AICore APKs')
    complete.add_argument('--android', type=Path, required=True)
    complete.add_argument('--workspace', type=Path, required=True)
    original = complete.add_mutually_exclusive_group(required=True)
    original.add_argument('--rom', type=Path)
    original.add_argument('--payload', type=Path)
    complete.add_argument('--aicore', type=Path, required=True)
    complete.add_argument('--payload-dumper', type=Path, required=True)
    complete.add_argument('--fsck-erofs', type=Path, required=True)
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
    if args.command == 'all':
        prepare_all(args, project, android)
        return
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
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError, zipfile.BadZipFile) as error:
        sys.exit(str(error))
