#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Adapt only the matching OEM gallery entry; retain its success/return lifecycle."""
import hashlib
from pathlib import Path
import shutil
import subprocess
import tempfile

METHOD = '.method public final b5(ZZ)V'
METHOD_SHA256 = '726abab08c3007a441494942c407726cc995785b55ef568b4042b432a393dfac'


def adapt_tree(directory):
    camera = directory / 'com/android/camera/Camera.smali'
    source = camera.read_text()
    start = source.index(METHOD)
    end = source.index('.end method', start) + len('.end method')
    method = source[start:end]
    if hashlib.sha256(method.encode()).hexdigest() != METHOD_SHA256:
        raise ValueError('Unexpected official gallery method; refusing adaptation')
    replacements = [
        ('    :cond_10d\n', '    :goto_2cb\n', '''    :cond_10d
    :try_start_pixelos_view
    iget-boolean v0, v9, LF1/w4;->h:Z
    invoke-static {v7, v5, v0}, Lcom/android/camera/PixelosGallery;->view(Landroid/content/Context;Landroid/net/Uri;Z)Landroid/content/Intent;
    move-result-object v1
    move/from16 v2, p2
    invoke-direct {v7, v1, v2}, Lcom/android/camera/Camera;->pixelosLaunchGallery(Landroid/content/Intent;Z)Z
    move-result v0
    :try_end_pixelos_view
    .catch Ljava/lang/RuntimeException; {:try_start_pixelos_view .. :try_end_pixelos_view} :catch_pixelos_view
    goto :goto_2cb
    :catch_pixelos_view
    move-exception v0
    const-string v1, "Cannot open thumbnail URI"
    invoke-static {v8, v1, v0}, Landroid/util/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)I
    const/4 v0, 0x0

'''),
        ('    :goto_2cb\n', '    :cond_2f3\n', '''    :goto_2cb
    invoke-static {v14, v15}, Landroid/os/Process;->setThreadPriority(II)V
    goto/16 :goto_37c

'''),
        ('    :cond_2f3\n', '    :cond_365\n', '''    :cond_2f3
    if-nez p1, :cond_365
    sget-boolean v0, LQa/b;->e:Z
    if-nez v0, :cond_365
    invoke-static {}, Lcom/android/camera/PixelosGallery;->album()Landroid/content/Intent;
    move-result-object v1
    move/from16 v2, p2
    invoke-direct {v7, v1, v2}, Lcom/android/camera/Camera;->pixelosLaunchGallery(Landroid/content/Intent;Z)Z
    move-result v0
    goto :goto_37c

'''),
    ]
    for first, last, replacement in replacements:
        left = method.index(first)
        right = method.index(last, left)
        method = method[:left] + replacement + method[right:]
    method = method.replace(METHOD, '.method public final pixelosGotoGallery(ZZ)V', 1)
    additions = Path(__file__).parent / 'gallery-smali'
    helpers = ['PixelosGallery.smali', 'PixelosGalleryUnlock.smali']
    for name in helpers:
        if (camera.parent / name).exists():
            raise ValueError('Gallery helper already exists: ' + name)
    guide = directory / 'com/android/camera/guide/a.smali'
    guide_source = guide.read_text()
    guide_start = guide_source.index('.method public static g(Landroid/content/Intent;)V')
    guide_end = guide_source.index('.end method', guide_start) + len('.end method')
    guide_method = guide_source[guide_start:guide_end]
    if hashlib.sha256(guide_method.encode()).hexdigest() != (
            '46ae5088f41a8d0fd7c2b668f6d3b0ddc734ceeb831b9befcf00f248efe27850'):
        raise ValueError('Unexpected official rear gallery launch; refusing adaptation')
    # The original returns void even when no eligible rear-display activity exists.
    # Preserve its guards, but commit both display and camera jump flags only on launch.
    guide_method = guide_method.replace(' g(Landroid/content/Intent;)V',
                                        ' pixelosStartGallery(Landroid/content/Intent;)Z', 1)
    flag = '    iput-boolean v2, v1, Lcom/android/camera/fragment/presentation/MainScreenSelfieActivity;->d0:Z'
    launch = '    invoke-virtual {v0, p0}, Landroid/app/Activity;->startActivity(Landroid/content/Intent;)V'
    guide_method = guide_method.replace(flag + '\n\n', '', 1)
    guide_method = guide_method.replace(launch, launch + '\n\n' + flag +
                                        '\n\n    return v2', 1)
    guide_method = guide_method.replace('    return-void', '    const/4 v0, 0x0\n\n    return v0', 1)
    guide.write_text(guide_source + '\n' + guide_method + '\n')
    camera.write_text(source[:start] + method + '\n\n' +
                      (additions / 'Camera-methods.smali').read_text() + source[end:])
    for name in helpers:
        shutil.copyfile(additions / name, camera.parent / name)


def prepare(android, original, destination):
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'
    tools = android / 'prebuilts/extract-tools/common/smali'
    with tempfile.TemporaryDirectory(prefix='camera-gallery-', dir=destination.parent) as tmp:
        directory = Path(tmp) / 'smali'
        subprocess.run([str(java), '-jar', str(tools / 'baksmali.jar'), 'd',
                        str(original), '-o', str(directory)], check=True)
        adapt_tree(directory)
        result = Path(tmp) / 'adapted.dex'
        subprocess.run([str(java), '-jar', str(tools / 'smali.jar'), 'a',
                        str(directory), '-o', str(result)], check=True)
        if not result.is_file():
            raise RuntimeError('Gallery DEX assembly failed')
        result.replace(destination)
