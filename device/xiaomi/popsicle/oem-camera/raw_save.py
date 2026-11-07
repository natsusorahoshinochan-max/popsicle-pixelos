#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Adapt save failure handling and standard DNG metadata/preview at the OEM boundary."""
from pathlib import Path
import shutil
import subprocess
import tempfile


def replace_once(text, old, new):
    if text.count(old) != 1:
        raise ValueError('Unexpected original camera save sequence: ' + old[:90])
    return text.replace(old, new, 1)


def adapt_tree(directory):
    path = directory / 'k7/y.smali'
    text = path.read_text()
    text = replace_once(text, '    move-result-object v12\n', '''    move-result-object v12

    invoke-static {v12}, Lcom/android/camera/PixelosRawSave;->begin(Ljava/lang/String;)V
''')
    text = replace_once(text, '''    :try_start_ae
    invoke-virtual {v8, v3}, Ljava/io/OutputStream;->write([B)V''', '''    :try_start_ae
    array-length v0, v3
    if-gtz v0, :pixelos_encoded_nonempty
    new-instance v0, Ljava/io/IOException;
    const-string v9, "Empty encoded DNG"
    invoke-direct {v0, v9}, Ljava/io/IOException;-><init>(Ljava/lang/String;)V
    throw v0
    :pixelos_encoded_nonempty
    invoke-virtual {v8, v3}, Ljava/io/OutputStream;->write([B)V''')
    start = text.index('    new-instance v0, Ljava/io/File;\n', text.index('    :goto_e4\n'))
    end = text.index('    :cond_fa\n', start)
    text = text[:start] + '''    new-instance v0, Ljava/io/IOException;
    const-string v3, "Encoded DNG write failed after retries"
    invoke-direct {v0, v3}, Ljava/io/IOException;-><init>(Ljava/lang/String;)V
    invoke-static {v1, v12, v7, v0}, Lcom/android/camera/PixelosRawSave;->failed(Ljava/lang/Object;Ljava/lang/String;Landroid/net/Uri;Ljava/lang/Throwable;)V
    goto/16 :goto_2bb

''' + text[end:]
    text = replace_once(text, '    new-instance v10, Landroid/hardware/camera2/DngCreator;\n', '')
    text = replace_once(text,
        '    invoke-direct {v10, v0, v13}, Landroid/hardware/camera2/DngCreator;-><init>(Landroid/hardware/camera2/CameraCharacteristics;Landroid/hardware/camera2/CaptureResult;)V',
        '    invoke-static {v1}, Lcom/android/camera/PixelosRawSave;->create(Ljava/lang/Object;)Landroid/hardware/camera2/DngCreator;\n\n    move-result-object v10')
    start = text.index('    array-length v0, v3\n', text.index('    if-eqz v1, :cond_1db'))
    end = text.index('    :try_end_1be', start)
    text = text[:start] + '    move-object/from16 v1, p0\n' + text[end:]
    start = text.index('    const-class v0, Ljava/io/OutputStream;', text.index('    :try_start_1be'))
    end = text.index('    :try_end_1cf', start)
    text = text[:start] + '    invoke-static {v1, v10, v2}, Lcom/android/camera/PixelosRawSave;->writeCompressed(Ljava/lang/Object;Landroid/hardware/camera2/DngCreator;Ljava/io/OutputStream;)V\n' + text[end:]
    text = replace_once(text, '''    invoke-static {v14, v1, v0}, Lcom/android/camera/log/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)V
    :try_end_168''', '''    invoke-static {v14, v1, v0}, Lcom/android/camera/log/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)V
    move-object/from16 v1, p0
    iget-object v0, v1, Lk7/y;->q:Ljava/nio/ByteBuffer;
    invoke-static {v10, v0}, Lcom/android/camera/PixelosRawSave;->thumbnail(Landroid/hardware/camera2/DngCreator;Ljava/nio/ByteBuffer;)V
    :try_end_168''')
    text = replace_once(text, '''    invoke-static {v14, v1, v0}, Lcom/android/camera/log/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)V

    :goto_1d6''', '''    invoke-static {v14, v1, v0}, Lcom/android/camera/log/Log;->e(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)V
    throw v0

    :goto_1d6''')
    text = replace_once(text, '''    invoke-static {v14, v2, v0}, Lcom/android/camera/log/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)V

    :goto_2bb''', '''    invoke-static {v14, v2, v0}, Lcom/android/camera/log/Log;->w(Ljava/lang/String;Ljava/lang/String;Ljava/lang/Throwable;)V
    invoke-static {v1, v12, v7, v0}, Lcom/android/camera/PixelosRawSave;->failed(Ljava/lang/Object;Ljava/lang/String;Landroid/net/Uri;Ljava/lang/Throwable;)V

    :goto_2bb
    invoke-static {}, Lcom/android/camera/PixelosRawSave;->complete()V''')
    path.write_text(text)

    path = directory / 'k7/K.smali'
    text = path.read_text()
    start = text.index('.method public static y(Landroid/content/Context;')
    end = text.index('.end method', start)
    method = text[start:end]
    first = method.index('    new-instance p0, Ljava/io/File;')
    last = method.index('    :cond_82\n', first)
    method = method[:first] + '    return v0\n\n' + method[last:]
    method = replace_once(method, '    move v1, v0\n', '''    if-nez p1, :pixelos_buffer_present
    return v0
    :pixelos_buffer_present
    invoke-virtual {p1}, Ljava/nio/Buffer;->limit()I
    move-result v1
    if-gtz v1, :pixelos_image_nonempty
    return v0
    :pixelos_image_nonempty
    move v1, v0
''')
    path.write_text(text[:start] + method + text[end:])


def prepare(android, original, destination):
    java_dir = android / 'prebuilts/jdk/jdk21/linux-x86/bin'
    tools = android / 'prebuilts/extract-tools/common/smali'
    sdk = android / 'prebuilts/sdk/current/public/android.jar'
    here = Path(__file__).parent
    with tempfile.TemporaryDirectory(prefix='camera-raw-save-', dir=destination.parent) as tmp:
        tmp = Path(tmp)
        directory = tmp / 'smali'
        subprocess.run([str(java_dir / 'java'), '-jar', str(tools / 'baksmali.jar'),
                        'd', str(original), '-o', str(directory)], check=True)
        adapt_tree(directory)
        classes = tmp / 'classes'
        classes.mkdir()
        subprocess.run([str(java_dir / 'javac'), '--release', '17', '-classpath', str(sdk),
                        '-d', str(classes), str(here / 'PixelosRawSave.java'), str(here / 'DngTiles.java')], check=True)
        dex = tmp / 'dex'
        dex.mkdir()
        # The checked-in compiler also works before the first ROM build.
        subprocess.run([str(java_dir / 'java'), '-cp', str(android / 'prebuilts/r8/r8.jar'),
                        'com.android.tools.r8.D8',
                        '--min-api', '37', '--lib', str(sdk), '--output', str(dex),
                        *map(str, sorted(classes.rglob('*.class')))], check=True)
        helpers = tmp / 'helpers'
        subprocess.run([str(java_dir / 'java'), '-jar', str(tools / 'baksmali.jar'),
                        'd', str(dex / 'classes.dex'), '-o', str(helpers)], check=True)
        for source in helpers.rglob('*.smali'):
            target = directory / source.relative_to(helpers)
            if target.exists():
                raise ValueError('DNG helper already exists: ' + str(target))
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
        subprocess.run([str(java_dir / 'java'), '-jar', str(tools / 'smali.jar'),
                        'a', str(directory), '-o', str(destination)], check=True)
