# SPDX-License-Identifier: Apache-2.0
import struct

def require(ok, message):
    if not ok:
        raise ValueError(message)

def patch_elf(data):
    require(len(data) == 7804064 and data[:7] == b'\x7fELF\x02\x01\x01', 'Wrong ELF')
    require(struct.unpack_from('<HH', data, 16) == (3, 183), 'Wrong ELF target')
    # Audited libchifeature2 VA == file offset in this executable region.
    guards = {0x4e7ec0: 0xf9422a73, 0x4e7ecc: 0xf94016cb,
              0x4e7f1c: 0x912b71ef, 0x4e7f30: 0xd503249f,
              0x4e7f34: 0x940928d9, 0x4e7f38: 0x35fffca0,
              0x4e7f3c: 0x940928e9, 0x4e7f40: 0x35fffc60,
              0x4e7f44: 0xd0ffdf21, 0x4e7f48: 0x913e4021,
              0x4e7f4c: 0x17ffffdd}
    for offset, word in guards.items():
        require(struct.unpack_from('<I', data, offset)[0] == word, f'ELF guard {offset:x}')
    require(data[0x10dadc + 660 - 0x241] == 0, 'SoC selector mismatch')
    name = b'kaanapali_gsi.xml\0'
    require(data[0xcdf90:0xcdf90 + len(name)] == name, 'Configuration mismatch')
    result = bytearray(data)
    struct.pack_into('<I', result, 0x4e7f38, 0x17ffffe5)
    require([i for i, (a, b) in enumerate(zip(data, result)) if a != b]
            == [0x4e7f38, 0x4e7f39, 0x4e7f3b], 'Unexpected ELF changes')
    return bytes(result)

