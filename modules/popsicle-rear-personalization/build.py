#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Package only the two modified apps and their matching preoptimization companions."""
import argparse
import hashlib
from pathlib import Path
import shutil
import subprocess
import zipfile

ROOTS = ('system_ext/priv-app/Settings', 'system_ext/app/PopsicleSubscreenCenter')


def digest(stream):
    result = hashlib.sha256()
    for block in iter(lambda: stream.read(1024 * 1024), b''):
        result.update(block)
    return result.hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--android', required=True, type=Path)
    parser.add_argument('--baseline-target-files', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    product = args.android/'out-pixelos-user/target/product/popsicle'
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=False)
    staging = output/'module'; staging.mkdir()
    here = Path(__file__).resolve().parent
    for name in ('module.prop', 'customize.sh', 'previous-apks.sha256'):
        shutil.copyfile(here/name, staging/name)
    (staging/'customize.sh').chmod(0o755)
    files = []
    baseline = []; candidate = []
    with zipfile.ZipFile(args.baseline_target_files) as original:
        for root in ROOTS:
            module = Path(root).name
            required = (module+'.apk', 'oat/arm64/'+module+'.odex', 'oat/arm64/'+module+'.vdex')
            for suffix in required:
                source = product/root/suffix
                if not source.is_file() or source.is_symlink():
                    raise ValueError('Missing regular candidate: '+str(source))
                target = staging/'system'/root/suffix
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(source, target)
                files.append('system/'+root+'/'+suffix)
            apk = root+'/'+module+'.apk'
            archive_path = 'SYSTEM_EXT/'+apk.removeprefix('system_ext/')
            with original.open(archive_path) as stream:
                baseline.append(digest(stream)+'  '+apk)
            with (product/apk).open('rb') as stream:
                candidate.append(digest(stream)+'  '+apk)
    (staging/'baseline-apks.sha256').write_text('\n'.join(baseline)+'\n')
    (staging/'candidate-apks.sha256').write_text('\n'.join(candidate)+'\n')
    (staging/'payload-files.txt').write_text('\n'.join(files)+'\n')
    listing = output/'zip-inputs.txt'
    listing.write_text('\n'.join(str(p) for p in sorted(staging.rglob('*')) if p.is_file())+'\n')
    archive = output/'popsicle-rear-personalization-v0.2.zip'
    subprocess.run([str(args.android/'out-pixelos-user/host/linux-x86/bin/soong_zip'),
                    '-parallel', '16', '-o', str(archive), '-C', str(staging), '-l', str(listing)], check=True)
    with archive.open('rb') as stream:
        archive.with_suffix('.zip.sha256').write_text(digest(stream)+'  '+archive.name+'\n')
    print(archive)


if __name__ == '__main__':
    main()
