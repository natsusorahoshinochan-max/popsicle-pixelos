#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Adapt the three reset calls in the matching official camera's primary DEX."""
from pathlib import Path
import subprocess
import tempfile

CALL = 'LFp/a;->a(Landroid/hardware/display/DisplayManager;F)V'
RESETS = {
    'F1/U2.smali': (
        '    iput v0, p0, LF1/U2;->g:F\n\n'
        f'    invoke-static {{v1, v0}}, {CALL}',
        '    iput v0, p0, LF1/U2;->g:F\n\n'
        '    const/high16 v0, 0x7fc00000    # Float.NaN: cancel temporary adjustment\n\n'
        f'    invoke-static {{v1, v0}}, {CALL}'),
    'F1/e3.smali': (
        '    const/4 v5, 0x0\n\n'
        f'    invoke-static {{v0, v5}}, {CALL}',
        '    const/high16 v5, 0x7fc00000    # Float.NaN: cancel temporary adjustment\n\n'
        f'    invoke-static {{v0, v5}}, {CALL}'),
    'r6/u.smali': (
        '    iput p0, v1, LF1/U2;->g:F\n\n'
        f'    invoke-static {{v3, p0}}, {CALL}',
        '    iput p0, v1, LF1/U2;->g:F\n\n'
        '    const/high16 p0, 0x7fc00000    # Float.NaN: cancel temporary adjustment\n\n'
        f'    invoke-static {{v3, p0}}, {CALL}'),
}


def adapt_tree(directory):
    files = {p: p.read_text() for p in directory.rglob('*.smali')}
    calls = sum(text.count(CALL) for text in files.values())
    if calls != 5:
        raise ValueError(f'Expected three resets and two boosts, found {calls} calls')
    replacements = {}
    for name, (old, new) in RESETS.items():
        path = directory / name
        text = files.get(path, '')
        if text.count(old) != 1:
            raise ValueError('Unexpected camera brightness reset: ' + name)
        replacements[path] = text.replace(old, new)
    # Validate all fixed call sites before changing any disassembly.
    for path, text in replacements.items():
        path.write_text(text)


def prepare(android, original, destination):
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'
    tools = android / 'prebuilts/extract-tools/common/smali'
    with tempfile.TemporaryDirectory(prefix='camera-brightness-', dir=destination.parent) as tmp:
        directory = Path(tmp) / 'smali'
        subprocess.run([str(java), '-jar', str(tools / 'baksmali.jar'), 'd',
                        str(original), '-o', str(directory)], check=True)
        adapt_tree(directory)
        result = Path(tmp) / 'adapted.dex'
        subprocess.run([str(java), '-jar', str(tools / 'smali.jar'), 'a',
                        str(directory), '-o', str(result)], check=True)
        result.replace(destination)
