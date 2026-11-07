#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Run the platform ELF verifier, including symbol resolution, on the original SDK libraries."""
import argparse
from pathlib import Path
import re
import subprocess

p = argparse.ArgumentParser(description=__doc__)
p.add_argument('android', type=Path)
p.add_argument('stock', type=Path)
a = p.parse_args()
root = a.android.resolve()
product = root / 'out-pixelos-user/target/product/popsicle'
inter = root / 'out-pixelos-user/soong/.intermediates'
locations = [product / 'system/lib64',
             inter / 'art/build/apex/com.android.art/android_common_com.android.art/image.apex/lib64',
             *[inter / f'bionic/{name}/{name}/android_arm64_armv8-a-branchprot_oryon_shared'
               for name in ('libc', 'libm', 'libdl')]]
for name in ['libmisight_jni.so', 'libmisight.so']:
    library = a.stock / 'system_ext/lib64' / name
    needed = re.findall(r'Shared library: \[(.*?)\]', subprocess.check_output(['readelf', '-d', str(library)], text=True))
    cmd = ['python3', str(root / 'build/make/tools/check_elf_file.py'),
           '--llvm-readobj', str(root / 'prebuilts/clang/host/linux-x86/clang-r596125/bin/llvm-readobj'),
           '--soname', name, '--max-page-size', '4096']
    for dep in needed:
        matches = [base / dep for base in locations if (base / dep).is_file()]
        if not matches:
            raise ValueError('Missing runtime dependency: ' + dep)
        cmd += ['--shared-lib', str(matches[0])]
    subprocess.run(cmd + [str(library)], check=True)
    print('PASS strict ELF/symbol/page alignment: ' + name + ': ' + ', '.join(needed), flush=True)
