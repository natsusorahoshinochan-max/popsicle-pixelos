#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Prepare only the original rear media and its explicit preset-theme inputs."""
import filecmp
import json
from pathlib import Path, PurePosixPath
import shutil


def product_references(value):
    if isinstance(value, dict):
        for child in value.values():
            yield from product_references(child)
    elif isinstance(value, list):
        for child in value:
            yield from product_references(child)
    elif isinstance(value, str) and value.startswith('/product/'):
        path = PurePosixPath(value)
        prefix = '/product/etc/precust_theme/theme/.data/'
        if not value.startswith(prefix) or '..' in path.parts:
            raise ValueError('Unexpected rear theme reference: ' + value)
        yield str(path).lstrip('/')


def resource_inputs(source):
    media = source / 'product/media/rearscreen'
    if not media.is_dir():
        raise ValueError('Missing original rear media: ' + str(media))
    inputs = {}
    references = set()
    for src in sorted(media.rglob('*')):
        if src.is_symlink():
            raise ValueError('Symlink in rear media: ' + str(src))
        if not src.is_file():
            continue
        # PixelOS has no /system/media alias. Preserve the exact OEM consumer
        # path without changing the meaning of other system media paths.
        inputs['system/media/rearscreen/' + str(src.relative_to(media))] = src
        if src.suffix == '.json':
            references.update(product_references(json.loads(src.read_text())))
    if 'system/media/rearscreen/template/default/rearScreen.json' not in inputs:
        raise ValueError('Missing original default rear template')
    for name in sorted(references):
        inputs[name] = source / name
    for src in inputs.values():
        if not src.is_file() or any(p.is_symlink() for p in [src, *src.parents]):
            raise ValueError('Expected regular original resource: ' + str(src))
    return dict(sorted(inputs.items()))


def prepare_resources(source, dest, check=False):
    inputs = resource_inputs(source)
    dest = dest / 'resources'
    if any(p.is_symlink() for p in [dest, *dest.parents]):
        raise ValueError('Resource destination must not contain symlinks')
    modules = []
    blocks = ['package { default_applicable_licenses: ["popsicle_oem_rear_resources_license"], }',
              'license { name: "popsicle_oem_rear_resources_license", '
              'license_kinds: ["legacy_proprietary"], }']
    for index, (name, src) in enumerate(inputs.items()):
        dst = dest / name
        if any(p.is_symlink() for p in [dst, *dst.parents]):
            raise ValueError('Symlink in resource destination: ' + name)
        if dst.exists() and (not dst.is_file() or not filecmp.cmp(src, dst, shallow=False)):
            raise ValueError('Different prepared resource: ' + name)
        if check and not dst.is_file():
            raise ValueError('Missing prepared resource: ' + name)
        module = f'popsicle-rear-resource-{index:03d}'
        modules.append(module)
        media = name.startswith('system/media/')
        relative = PurePosixPath(name).relative_to('system/media' if media else 'product/etc')
        kind = 'prebuilt_media' if media else 'prebuilt_etc'
        blocks.append(kind + ' {\n'
                      f'    name: {json.dumps(module)},\n'
                      f'    src: {json.dumps(name)},\n'
                      f'    filename: {json.dumps(relative.name)},\n'
                      f'    sub_dir: {json.dumps(str(relative.parent))},\n'
                      + ('' if media else '    product_specific: true,\n') + '}')
    blocks.append('phony { name: "popsicle-rear-resources", required: '
                  + json.dumps(modules) + ', }')
    generated = {'Android.bp': '\n\n'.join(blocks) + '\n',
                 'resource-files.txt': '\n'.join(inputs) + '\n'}
    for name, content in generated.items():
        path = dest / name
        if path.is_symlink():
            raise ValueError('Symlink in generated resource metadata: ' + name)
        if check and (not path.is_file() or path.read_text() != content):
            raise ValueError('Stale prepared resource metadata: ' + name)
    if not check:
        for name, src in inputs.items():
            path = dest / name
            path.parent.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                shutil.copyfile(src, path)
        for name, content in generated.items():
            (dest / name).write_text(content)
    print(f'PASS: {len(inputs)} original rear media and referenced preset files')
