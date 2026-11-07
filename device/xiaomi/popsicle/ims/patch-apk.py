#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Select the OEM's existing non-MIUI branches on the tested LineageOS build."""
import hashlib
import struct
import sys
import zipfile
import zlib

with zipfile.ZipFile(sys.argv[1]) as source:
    dex = bytearray(source.read('classes.dex'))
    # Four isMiuiRom() calls. The OEM interface default is false; specialize only
    # this platform predicate, preserving both call handling and IMS validation.
    for offset, register in [(0x51180, 0), (0x5595c, 13), (0x580d8, 1), (0x5845c, 1)]:
        expected = bytes.fromhex('710022010000') + bytes([0x0a, register])
        if dex[offset:offset + 8] != expected:
            raise SystemExit(f'Unexpected IMS instruction at {offset:#x}')
        dex[offset:offset + 8] = bytes([0x12, register, 0, 0, 0, 0, 0, 0])
    dex[12:32] = hashlib.sha1(dex[32:]).digest()
    struct.pack_into('<I', dex, 8, zlib.adler32(dex[12:]) & 0xffffffff)
    with zipfile.ZipFile(sys.argv[2], 'w') as target:
        for entry in source.infolist():
            if entry.filename.startswith('META-INF/'):
                continue
            target.writestr(entry, dex if entry.filename == 'classes.dex' else source.read(entry))
