#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package the ROM-built navigation repair with its normal optimization and integrity data."""
import argparse
import hashlib
import importlib.util
from pathlib import Path
import shutil
import subprocess
import zipfile

BASELINE_GATES = (
    'system/framework/services.jar',
    'system_ext/priv-app/SystemUI/SystemUI.apk',
    'system_ext/priv-app/Settings/Settings.apk',
    'system_ext/app/PopsicleSubscreenCenter/PopsicleSubscreenCenter.apk',
    'system_ext/priv-app/NexusLauncherRelease/NexusLauncherRelease.apk',
)


def digest(stream):
    result = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--android', type=Path, required=True)
    parser.add_argument('--baseline-target-files', type=Path, required=True)
    parser.add_argument('--rear-v02', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    here = Path(__file__).resolve().parent
    android = args.android.resolve(strict=True)
    out = android / 'out-pixelos-user'
    product = out / 'target/product/popsicle'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    payload = output / 'payload'
    staging = output / 'module'
    staging.mkdir()
    files = (here / 'payload-files.txt').read_text().splitlines()
    for name in files:
        source = product / name
        if not source.is_file() or source.is_symlink():
            raise ValueError('Missing regular built payload: ' + str(source))
        target = payload / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    helper_path = here.parent / 'popsicle-repair-parts/manifest_support.py'
    spec = importlib.util.spec_from_file_location('manifest_support', helper_path)
    helper = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(helper)
    baselines = output / 'baseline'
    baselines.mkdir()
    original = []
    candidate = []
    with zipfile.ZipFile(args.baseline_target_files) as archive:
        for partition, filename in [('system', 'BuildManifest.apk'),
                                    ('system_ext', 'BuildManifestSystemExt.apk')]:
            relative = partition + '/etc/security/fsverity/' + filename
            baseline = baselines / filename
            baseline.write_bytes(archive.read(partition.upper() + relative[len(partition):]))
            names = [name for name in files if name.startswith(partition + '/framework/')]
            helper.build_manifest(android, out, baseline, payload, names, payload / relative,
                                  android / 'build/make/target/product/security/testkey', partition)
        for name in BASELINE_GATES:
            partition, suffix = name.split('/', 1)
            with archive.open(partition.upper() + '/' + suffix) as stream:
                original.append(digest(stream) + '  ' + name)
            with (product / name).open('rb') as stream:
                candidate.append(digest(stream) + '  ' + name)

    with zipfile.ZipFile(args.rear_v02) as archive:
        previous = archive.read('candidate-apks.sha256')
    (staging / 'baseline-files.sha256').write_text('\n'.join(original) + '\n')
    (staging / 'candidate-files.sha256').write_text('\n'.join(candidate) + '\n')
    (staging / 'rear-v02-files.sha256').write_bytes(previous)
    for name in ('module.prop', 'customize.sh', 'README.md'):
        shutil.copyfile(here / name, staging / name)
    installed = []
    for source in sorted(payload.rglob('*')):
        if not source.is_file():
            continue
        relative = source.relative_to(payload).as_posix()
        mount = relative if relative.startswith('system/') else 'system/' + relative
        target = staging / mount
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)
        installed.append(mount)
    notice = android / 'vendor/xiaomi/popsicle-private/prebuilt/oem-rear/misight-work/NOTICE'
    shutil.copyfile(notice, staging / 'NOTICE.misight')
    (staging / 'payload-files.txt').write_text('\n'.join(installed) + '\n')
    (staging / 'customize.sh').chmod(0o755)
    listing = output / 'zip-inputs.txt'
    listing.write_text('\n'.join(str(p) for p in sorted(staging.rglob('*')) if p.is_file()) + '\n')
    archive = output / 'popsicle-hidden-navigation-v0.2.zip'
    subprocess.run([str(out / 'host/linux-x86/bin/soong_zip'), '-parallel', '16',
                    '-o', str(archive), '-C', str(staging), '-l', str(listing)], check=True)
    with archive.open('rb') as stream:
        archive.with_suffix('.zip.sha256').write_text(digest(stream) + '  ' + archive.name + '\n')
    print(archive)


if __name__ == '__main__':
    main()
