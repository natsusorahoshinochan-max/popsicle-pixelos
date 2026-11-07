#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Extract class definitions from the pinned APK, not the converter's output."""
import hashlib
from pathlib import Path
import struct
import sys
import zipfile

apk = Path(sys.argv[1])
if hashlib.sha256(apk.read_bytes()).hexdigest() != '1c2c35361830a8fa755a923ee941085d38f3165f5226556ba4432352fd107031':
    raise ValueError('Unexpected TurboAdapter APK')
names = set()
with zipfile.ZipFile(apk) as z:
    for name in z.namelist():
        if not name.endswith('.dex'):
            continue
        data = z.read(name)
        def u32(offset):
            return struct.unpack_from('<I', data, offset)[0]
        def text(index):
            pos = u32(u32(60) + index * 4)
            while data[pos] & 128:
                pos += 1
            pos += 1
            return data[pos:data.index(0, pos)].decode('ascii')
        for i in range(u32(96)):
            class_idx = u32(u32(100) + i * 32)
            descriptor = text(u32(u32(68) + class_idx * 4))
            if not descriptor.startswith('L') or not descriptor.endswith(';'):
                raise ValueError(descriptor)
            if descriptor in names:
                raise ValueError('Duplicate DEX definition')
            names.add(descriptor)
Path(sys.argv[2]).write_text(''.join(n[1:-1] + '\n' for n in sorted(names)))
print('DEX class definitions:', len(names))
