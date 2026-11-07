#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Exclude destroyed activities from the original camera's cross-display cleanup."""
from pathlib import Path
import subprocess
import tempfile


def adapt_tree(directory):
    path = directory / 'com/android/camera/guide/a.smali'
    text = path.read_text()
    start = text.index('.method public static c(II)V\n')
    end = text.index('.end method', start)
    method = text[start:end]
    old = ('    check-cast v1, Lcom/android/camera/a;\n\n'
           '    invoke-static {v1}, LF1/o4;->a(Lcom/android/camera/a;)Landroid/view/Display;')
    new = ('    check-cast v1, Lcom/android/camera/a;\n\n'
           '    # A relaunched instance shares the old activity token. Never finish it\n'
           '    # through a destroyed object retained by the weak-reference stack.\n'
           '    invoke-virtual {v1}, Landroid/app/Activity;->isDestroyed()Z\n\n'
           '    move-result v2\n\n'
           '    if-nez v2, :cond_52\n\n'
           '    invoke-static {v1}, LF1/o4;->a(Lcom/android/camera/a;)Landroid/view/Display;')
    if method.count(old) != 1 or method.count('    :cond_52\n') != 1:
        raise ValueError('Unexpected original camera cross-display cleanup')
    if '->isDestroyed()Z' in method:
        raise ValueError('Camera cross-display cleanup already adapted')
    path.write_text(text[:start] + method.replace(old, new) + text[end:])


def prepare(android, original, destination):
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'
    tools = android / 'prebuilts/extract-tools/common/smali'
    with tempfile.TemporaryDirectory(prefix='camera-lifecycle-', dir=destination.parent) as tmp:
        directory = Path(tmp) / 'smali'
        subprocess.run([str(java), '-jar', str(tools / 'baksmali.jar'), 'd',
                        str(original), '-o', str(directory)], check=True)
        adapt_tree(directory)
        result = Path(tmp) / 'adapted.dex'
        subprocess.run([str(java), '-jar', str(tools / 'smali.jar'), 'a',
                        str(directory), '-o', str(result)], check=True)
        result.replace(destination)
