#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Restore unattached original rear gesture windows when the launcher is ready."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import zipfile


LAUNCHER = 'com/xiaomi/subscreencenter/SubScreenLauncher'
ENTRY = '''
.method private restorePixelOsRearGestures()V
    .locals 1
    sget-object v0, Lcom/xiaomi/subscreencenter/SubScreenCenterApp;->u:Lcom/xiaomi/subscreencenter/SubScreenCenterApp;
    if-eqz v0, :restore_done
    iget-object v0, v0, Lcom/xiaomi/subscreencenter/SubScreenCenterApp;->e:Ln2/e;
    if-eqz v0, :restore_done
    invoke-virtual {v0, p0}, Ln2/e;->restorePixelOsGestureWindows(Landroid/content/Context;)V
    :restore_done
    return-void
.end method
'''
RESTORE = '''
.method public restorePixelOsGestureWindows(Landroid/content/Context;)V
    .locals 8
    const-class v0, Landroid/hardware/display/DisplayManager;
    invoke-virtual {p1, v0}, Landroid/content/Context;->getSystemService(Ljava/lang/Class;)Ljava/lang/Object;
    move-result-object v0
    check-cast v0, Landroid/hardware/display/DisplayManager;
    if-eqz v0, :restore_done
    const/4 v1, 0x1
    invoke-virtual {v0, v1}, Landroid/hardware/display/DisplayManager;->getDisplay(I)Landroid/view/Display;
    move-result-object v0
    if-eqz v0, :restore_done
    new-instance v1, Landroid/graphics/Point;
    invoke-direct {v1}, Landroid/graphics/Point;-><init>()V
    invoke-virtual {v0, v1}, Landroid/view/Display;->getRealSize(Landroid/graphics/Point;)V
    iget v2, v1, Landroid/graphics/Point;->x:I
    iget v3, v1, Landroid/graphics/Point;->y:I
    if-lez v2, :restore_done
    if-lez v3, :restore_done
    iput v2, p0, Ln2/e;->c:I
    iput v3, p0, Ln2/e;->d:I

    iget-object v7, p0, Ln2/e;->m:Ln2/h;
    invoke-virtual {v7}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    if-nez v0, :restore_home
    invoke-virtual {v7}, Landroid/view/View;->getContext()Landroid/content/Context;
    move-result-object v0
    new-instance v1, Landroid/view/WindowManager$LayoutParams;
    const/16 v2, 0x3e
    const/4 v3, -0x1
    const/16 v4, 0x7eb
    const/16 v5, 0x128
    const/4 v6, 0x1
    invoke-direct/range {v1 .. v6}, Landroid/view/WindowManager$LayoutParams;-><init>(IIIII)V
    const/16 v2, 0x55
    iput v2, v1, Landroid/view/WindowManager$LayoutParams;->gravity:I
    const/16 v2, 0x60
    iput v2, v1, Landroid/view/WindowManager$LayoutParams;->miuiFlags:I
    const-string v2, "SubScreenGestureBack"
    invoke-virtual {v1, v2}, Landroid/view/WindowManager$LayoutParams;->setTitle(Ljava/lang/CharSequence;)V
    const/4 v2, 0x1
    invoke-static {v0, v7, v1, v2}, LC2/c;->a(Landroid/content/Context;Landroid/view/View;Landroid/view/WindowManager$LayoutParams;I)V
    invoke-virtual {v7}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    if-eqz v0, :restore_home
    # View.post waits for first attachment before applying surface input state.
    new-instance v0, Ln2/PixelOsGestureWindowState;
    const/4 v1, 0x1
    invoke-direct {v0, p0, v1}, Ln2/PixelOsGestureWindowState;-><init>(Ln2/e;Z)V
    invoke-virtual {v7, v0}, Landroid/view/View;->post(Ljava/lang/Runnable;)Z

    :restore_home
    iget-object v7, p0, Ln2/e;->p:Landroid/view/View;
    invoke-virtual {v7}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    if-nez v0, :restore_done
    invoke-virtual {v7}, Landroid/view/View;->getContext()Landroid/content/Context;
    move-result-object v0
    new-instance v1, Landroid/view/WindowManager$LayoutParams;
    const/4 v2, -0x1
    iget v3, p0, Ln2/e;->j:I
    const/16 v4, 0x7eb
    const/16 v5, 0x128
    const/4 v6, 0x1
    invoke-direct/range {v1 .. v6}, Landroid/view/WindowManager$LayoutParams;-><init>(IIIII)V
    const/16 v2, 0x50
    iput v2, v1, Landroid/view/WindowManager$LayoutParams;->gravity:I
    const/4 v2, 0x3
    iput v2, v1, Landroid/view/WindowManager$LayoutParams;->layoutInDisplayCutoutMode:I
    const/16 v2, 0x60
    iput v2, v1, Landroid/view/WindowManager$LayoutParams;->miuiFlags:I
    const-string v2, "SubScreenGestureHome"
    invoke-virtual {v1, v2}, Landroid/view/WindowManager$LayoutParams;->setTitle(Ljava/lang/CharSequence;)V
    const/4 v2, 0x1
    invoke-static {v0, v7, v1, v2}, LC2/c;->a(Landroid/content/Context;Landroid/view/View;Landroid/view/WindowManager$LayoutParams;I)V
    invoke-virtual {v7}, Landroid/view/View;->getParent()Landroid/view/ViewParent;
    move-result-object v0
    if-eqz v0, :restore_done
    new-instance v0, Ln2/PixelOsGestureWindowState;
    const/4 v1, 0x0
    invoke-direct {v0, p0, v1}, Ln2/PixelOsGestureWindowState;-><init>(Ln2/e;Z)V
    invoke-virtual {v7, v0}, Landroid/view/View;->post(Ljava/lang/Runnable;)Z
    :restore_done
    return-void
.end method
'''
WINDOW_STATE = '''
.class public final Ln2/PixelOsGestureWindowState;
.super Ljava/lang/Object;
.implements Ljava/lang/Runnable;
.field private final manager:Ln2/e;
.field private final back:Z

.method public constructor <init>(Ln2/e;Z)V
    .locals 0
    invoke-direct {p0}, Ljava/lang/Object;-><init>()V
    iput-object p1, p0, Ln2/PixelOsGestureWindowState;->manager:Ln2/e;
    iput-boolean p2, p0, Ln2/PixelOsGestureWindowState;->back:Z
    return-void
.end method

.method public run()V
    .locals 2
    iget-object v0, p0, Ln2/PixelOsGestureWindowState;->manager:Ln2/e;
    iget-boolean v1, p0, Ln2/PixelOsGestureWindowState;->back:Z
    if-eqz v1, :home_state
    iget-boolean v1, v0, Ln2/e;->n:Z
    xor-int/lit8 v1, v1, 0x1
    iput-boolean v1, v0, Ln2/e;->n:Z
    invoke-virtual {v0}, Ln2/e;->e()V
    return-void
    :home_state
    iget-boolean v1, v0, Ln2/e;->q:Z
    xor-int/lit8 v1, v1, 0x1
    iput-boolean v1, v0, Ln2/e;->q:Z
    invoke-virtual {v0}, Ln2/e;->f()V
    return-void
.end method
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('android', type=Path)
    parser.add_argument('--private-dir', type=Path,
                        help='isolated output directory for the rear preparation chain')
    args = parser.parse_args()
    android = args.android.resolve(strict=True)
    private = args.private_dir or android / 'vendor/xiaomi/popsicle-private/prebuilt/oem-rear'
    if not private.resolve().is_relative_to(android / 'vendor/xiaomi/popsicle-private/prebuilt'):
        raise ValueError('Rear outputs must remain in this Android tree private inputs')
    if any(path.is_symlink() for path in [private, *private.parents]):
        raise ValueError('Private work directory must not use symlinks')
    source = private / 'subscreencenter-aod.apk'
    work = private / 'gestures-work'
    work.mkdir(exist_ok=False)
    java = android / 'prebuilts/jdk/jdk21/linux-x86/bin/java'
    smali = android / 'prebuilts/extract-tools/common/smali'
    with zipfile.ZipFile(source) as src:
        (work / 'input.dex').write_bytes(src.read('classes.dex'))
    subprocess.run([str(java), '-jar', str(smali / 'baksmali.jar'), 'd', '-l',
                    str(work / 'input.dex'), '-o', str(work / 'smali')], check=True)
    launcher = work / 'smali' / (LAUNCHER + '.smali')
    text = launcher.read_text()
    if 'refreshPixelOsRearGeometry' not in text or 'restorePixelOsRearGestures' in text:
        raise ValueError('Requires the v0.3 geometry candidate without gesture recovery')
    for method in ('onResume()V', 'onConfigurationChanged(Landroid/content/res/Configuration;)V'):
        # Run after the original super lifecycle call, retaining v0.3 geometry refresh.
        pattern = (r'(\.method public final ' + re.escape(method)
                   + r'\n.*?invoke-super[^\n]+\n)')
        text, count = re.subn(pattern, lambda match: match[1] + '\n'
                             + '    invoke-direct {p0}, L' + LAUNCHER
                             + ';->restorePixelOsRearGestures()V\n', text, flags=re.S)
        if count != 1:
            raise ValueError('Unexpected OEM lifecycle method: ' + method)
    launcher.write_text(text + ENTRY)
    manager = work / 'smali/n2/e.smali'
    text = manager.read_text()
    for field in ('c', 'd'):
        old = '.field public final ' + field + ':I'
        if text.count(old) != 1:
            raise ValueError('Unexpected cached gesture geometry field: ' + field)
        text = text.replace(old, '.field public ' + field + ':I')
    manager.write_text(text + RESTORE)
    (work / 'smali/n2/PixelOsGestureWindowState.smali').write_text(WINDOW_STATE)
    subprocess.run([str(java), '-jar', str(smali / 'smali.jar'), 'a',
                    str(work / 'smali'), '-o', str(work / 'classes.dex')], check=True)
    output = private / 'subscreencenter-gestures.apk'
    with zipfile.ZipFile(source) as src, zipfile.ZipFile(output, 'x') as dst:
        for entry in src.infolist():
            payload = (work / 'classes.dex').read_bytes() if entry.filename == 'classes.dex' else src.read(entry)
            dst.writestr(entry, payload)
    result = {'input_apk': str(source), 'output_apk': str(output),
              'changed_classes': [LAUNCHER, 'n2/e', 'n2/PixelOsGestureWindowState'],
              'hooks': ['onResume', 'onConfigurationChanged']}
    (work / 'provenance.json').write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result))


if __name__ == '__main__':
    main()
