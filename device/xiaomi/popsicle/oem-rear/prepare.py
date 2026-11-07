#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare the original rear-screen APK and PAG runtime with its NOTICE mappings."""
import argparse
import filecmp
import fcntl
import gzip
import hashlib
import html
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import zipfile

from resources import prepare_resources


STAGES = [
    ('subscreencenter-misight.apk', 'prepare-rear.py', 'misight-work'),
    ('subscreencenter-aod.apk', 'prepare-rear-geometry.py', 'geometry-work'),
    ('subscreencenter-gestures.apk', 'prepare-rear-gestures.py', 'gestures-work'),
    ('subscreencenter-structured.apk', 'prepare-rear-structured.py', 'structured-work'),
    ('subscreencenter-personalization.apk', 'prepare-rear-personalization.py', 'personalization-work'),
]


def digest(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError('Expected regular preparation input: ' + str(path))
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
    return result.hexdigest()


def write_provenance(path, record):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode='w', dir=path.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            stream.write(json.dumps(record, indent=2) + '\n')
            stream.flush()
            os.fsync(stream.fileno())
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)


def same_apk(existing, generated, android, scratch):
    """Compare payloads, allowing the assembler's equivalent DEX item ordering."""
    with zipfile.ZipFile(existing) as old, zipfile.ZipFile(generated) as new:
        names = old.namelist()
        generated_names = new.namelist()
        if (len(names) != len(set(names)) or len(generated_names) != len(set(generated_names))
                or set(names) != set(generated_names)):
            return False
        for name in names:
            before, after = old.read(name), new.read(name)
            if before == after:
                continue
            if not re.fullmatch(r'classes(?:[1-9][0-9]*)?\.dex', name):
                return False
            trees = []
            for label, data in [('existing', before), ('generated', after)]:
                dex = scratch / (label + '-' + name)
                dex.write_bytes(data)
                directory = dex.with_suffix('.smali')
                subprocess.run([str(android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'),
                                '-jar', str(android / 'prebuilts/extract-tools/common/smali/baksmali.jar'),
                                'd', str(dex), '-o', str(directory)], check=True)
                trees.append({str(p.relative_to(directory)): p.read_bytes()
                              for p in directory.rglob('*.smali')})
            if trees[0] != trees[1]:
                return False
    return True


def prepare_adaptations(android, source, dest, dex_tools, check):
    adaptation = Path(__file__).with_name('adaptation')
    sources = [Path(__file__), *sorted(p for p in adaptation.rglob('*')
                                      if p.suffix in {'.py', '.java', '.smali'})]
    original_inputs = ['product/app/subscreencenter/subscreencenter.apk',
                       'system_ext/framework/miui-framework.jar',
                       'system_ext/lib64/libmisight.so', 'system_ext/lib64/libmisight_jni.so',
                       'system_ext/etc/NOTICE.xml.gz']
    tools = ['prebuilts/sdk/current/public/android.jar', 'prebuilts/r8/r8.jar',
             'prebuilts/extract-tools/common/smali/smali.jar',
             'prebuilts/extract-tools/common/smali/baksmali.jar',
             'prebuilts/extract-tools/common/apktool/apktool.jar']
    generation = {
        'inputs': {name: digest(source / name) for name in original_inputs},
        'sources': {str(p.relative_to(Path(__file__).parent)): digest(p) for p in sources},
        'tools': {name: digest(android / name) for name in tools},
    }
    if dex_tools is not None:
        jars = sorted(dex_tools.resolve(strict=True).rglob('*.jar'))
        if not jars:
            raise ValueError('Expected the dex2jar distribution JARs')
        generation['dex_tools'] = {str(p.relative_to(dex_tools.resolve())): digest(p) for p in jars}
    records = {}
    current = True
    for output, script, work in STAGES:
        target = dest / output
        provenance = dest / work / 'provenance.json'
        if any(p.is_symlink() for p in [target, provenance, provenance.parent]):
            raise ValueError('Private preparation paths must not use symlinks')
        record = json.loads(provenance.read_text()) if provenance.is_file() else {}
        actual = digest(target) if target.exists() else None
        owned = record.get('output_sha256')
        if actual and owned and actual not in {owned, record.get('previous_output_sha256')}:
            raise ValueError('Conflicting prepared rear APK: ' + str(target))
        records[output] = (record, actual)
        recorded_generation = dict(record.get('generation', {}))
        if dex_tools is None:
            recorded_generation.pop('dex_tools', None)
        current = current and bool(actual and actual == owned and recorded_generation == generation)
    notice = dest / 'misight-work/NOTICE'
    if notice.is_symlink():
        raise ValueError('MiSight NOTICE must not be a symlink')
    actual_notice = digest(notice) if notice.exists() else None
    notice_record = records[STAGES[0][0]][0]
    owned_notice = notice_record.get('misight_notice_sha256')
    if actual_notice and owned_notice and actual_notice not in {
            owned_notice, notice_record.get('previous_misight_notice_sha256')}:
        raise ValueError('Conflicting prepared MiSight NOTICE')
    current = (current and notice.is_file()
               and actual_notice == owned_notice)
    if current:
        if not check:
            for output, script, work in STAGES:
                record, actual = records[output]
                if 'previous_output_sha256' in record or 'previous_misight_notice_sha256' in record:
                    record.pop('previous_output_sha256', None)
                    record.pop('previous_misight_notice_sha256', None)
                    write_provenance(dest / work / 'provenance.json', record)
        return
    if dex_tools is None:
        raise ValueError('--dex-tools is required to generate or refresh rear APKs')
    with tempfile.TemporaryDirectory(prefix='.rear-adaptation-', dir=dest.parent) as directory:
        staged = Path(directory)
        for output, script, work in STAGES:
            command = [sys.executable, str(adaptation / script), str(android), '--private-dir', str(staged)]
            if script == 'prepare-rear.py':
                command += [str(source), '--dex-tools', str(dex_tools)]
            subprocess.run(command, check=True)
        for output, script, work in STAGES:
            target = dest / output
            record, actual = records[output]
            if not actual:
                if check:
                    raise ValueError('Missing prepared rear APK: ' + str(target))
                continue
            if check or not record.get('output_sha256'):
                comparison = staged / (work + '-comparison')
                comparison.mkdir()
                if not same_apk(target, staged / output, android, comparison):
                    raise ValueError('Unverified or outdated rear APK: ' + str(target)
                                     + '; prepare a new private input directory')
        generated_notice = staged / 'misight-work/NOTICE'
        generated_notice_digest = digest(generated_notice)
        if actual_notice and actual_notice != generated_notice_digest and (check or not owned_notice):
            raise ValueError('Unverified or outdated MiSight NOTICE')
        if check:
            if not notice.is_file():
                raise ValueError('Missing prepared MiSight NOTICE')
            return
        input_apk = source / original_inputs[0]
        published = {}
        for output, script, work in STAGES:
            record, actual = records[output]
            provenance = dest / work / 'provenance.json'
            updated = {'input_apk': str(input_apk), 'output_apk': str(dest / output),
                       'generation': generation, 'output_sha256': digest(staged / output),
                       'misight_notice_sha256': generated_notice_digest,
                       'previous_misight_notice_sha256': actual_notice}
            updated['previous_output_sha256'] = actual
            # Record both owned states before replacement so interrupted publication can resume.
            write_provenance(provenance, updated)
            (staged / output).replace(dest / output)
            del updated['previous_output_sha256']
            write_provenance(provenance, updated)
            published[work] = updated
            input_apk = dest / output
        generated_notice.replace(notice)
        for work, record in published.items():
            del record['previous_misight_notice_sha256']
            write_provenance(dest / work / 'provenance.json', record)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('android', type=Path)
    parser.add_argument('filesystems', type=Path)
    parser.add_argument('--check', action='store_true')
    parser.add_argument('--dex-tools', type=Path,
                        help='dex2jar distribution used to extract the original MiSight SDK')
    args = parser.parse_args()
    android = args.android.resolve(strict=True)
    source = args.filesystems.resolve(strict=True)
    if not (android / 'build/envsetup.sh').is_file():
        parser.error('Expected the PixelOS Android source tree')
    if 'OS4.0.0.23.XPBCNXM' not in (source / 'product/etc/build.prop').read_text():
        parser.error('Expected matching official A17 filesystem input')
    dest = android / 'vendor/xiaomi/popsicle-private/prebuilt/oem-rear'
    if any(p.is_symlink() for p in [dest, *dest.parents]):
        parser.error('Private destination must not contain symlinks')
    if source == dest or source in dest.parents or dest in source.parents:
        parser.error('Official input and private output must be separate')
    inputs = ['system_ext/framework/pag-hyperos-release.jar',
              'system_ext/lib64/libpag.hyperos.so', 'system_ext/lib64/libffavc.hyperos.so',
              'system_ext/etc/permissions/com.android.systemui.libpag.xml',
              'product/app/subscreencenter/subscreencenter.apk']
    outputs = {Path(name).name: source / name for name in inputs}
    outputs.update({name: Path(__file__).parent / name
                    for name in ['public.libraries-hyperos.txt']})
    outputs['Android.bp'] = Path(__file__).parent / 'Android.bp.in'
    # The OEM aggregate contains malformed XML elsewhere. Read only exact file-name mappings
    # and their CDATA bodies, rather than weakening or omitting NOTICE generation.
    with gzip.open(source / 'system_ext/etc/NOTICE.xml.gz', 'rt') as stream:
        notice = stream.read()
    content = dict(re.findall(r'<file-content contentId="([^"]+)"[^>]*><!\[CDATA\[(.*?)\]\]></file-content>',
                              notice, re.S))
    texts = []
    for name in inputs[:3]:
        ids = set()
        for attrs, path in re.findall(r'<file-name([^>]*)>([^<]*)</file-name>', notice):
            if path == '/' + name:
                match = re.search(r'contentId="([^"]+)"', attrs)
                if match:
                    ids.add(match[1])
        if not ids or any(not content.get(key, '').strip() for key in ids):
            parser.error('Missing official NOTICE mapping/text: ' + name)
        for key in sorted(ids):
            texts.append('Official /' + name + '\n' + html.unescape(content[key]))
    for name, src in outputs.items():
        dst = dest / name
        if src.is_symlink() or not src.is_file() or dst.is_symlink():
            parser.error('Expected regular input/output: ' + name)
        if dst.exists() and not filecmp.cmp(src, dst, shallow=False):
            parser.error('Refusing to replace a different prepared input: ' + name)
        if args.check and not dst.is_file():
            parser.error('Missing prepared input: ' + name)
    notice_text = '\n\n'.join(texts) + '\n'
    target_notice = dest / 'NOTICE'
    if target_notice.is_symlink() or (target_notice.exists()
                                      and target_notice.read_text() != notice_text):
        parser.error('Refusing to replace a different prepared NOTICE')
    if args.check:
        if not target_notice.is_file():
            parser.error('Missing prepared NOTICE')
    else:
        dest.mkdir(parents=True, exist_ok=True)
        for name, src in outputs.items():
            if not (dest / name).exists():
                shutil.copyfile(src, dest / name)
        if not target_notice.exists():
            target_notice.write_text(notice_text)
    prepare_resources(source, dest, args.check)
    descriptor = os.open(dest, os.O_RDONLY)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX)
        prepare_adaptations(android, source, dest, args.dex_tools, args.check)
    finally:
        os.close(descriptor)
    print('PASS: adapted original rear APK, PAG runtime, declarations and mapped NOTICE')


if __name__ == '__main__':
    main()
