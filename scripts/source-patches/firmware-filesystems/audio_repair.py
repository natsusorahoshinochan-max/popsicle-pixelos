# SPDX-License-Identifier: Apache-2.0
"""Exact popsicle audio changes validated with KernelSU v0.3."""
import hashlib
import re
import struct
import xml.etree.ElementTree as ET

STOCK_SHA256 = '4b4de74b7ea20ee1bd407f9c1c90c6304c33c46288a05e1f8d3b916960881f13'
HAL_SHA256 = '388afd93534a81747a874f70fac2577e737db998c42dec6c02d109073335d298'


def patch_hal(data):
    """Correct this device's HAL-local GSI flag; keep framework-facing properties."""
    if hashlib.sha256(data).hexdigest() != HAL_SHA256:
        raise ValueError('Unsupported original audio HAL')
    if data[:6] != b'\x7fELF\x02\x01' or struct.unpack_from('<H', data, 18)[0] != 183:
        raise ValueError('Expected little-endian AArch64 ELF64')
    address = 0x227170
    phoff = struct.unpack_from('<Q', data, 32)[0]
    phsize, count = struct.unpack_from('<HH', data, 54)
    offsets = []
    for index in range(count):
        kind, flags, offset, vaddr, _, size, _, _ = struct.unpack_from(
            '<IIQQQQQQ', data, phoff + index * phsize)
        if kind == 1 and flags & 1 and vaddr <= address and address + 4 <= vaddr + size:
            offsets.append(offset + address - vaddr)
    if len(offsets) != 1:
        raise ValueError('Instruction is not in one executable segment')
    offset = offsets[0]
    if struct.unpack_from('<I', data, offset)[0] != 0x390002a9:
        raise ValueError('Unexpected GSI initialization instruction')
    result = bytearray(data)
    # strb w9, [x21] -> strb wzr, [x21]. No branches or CTS stream flags change.
    struct.pack_into('<I', result, offset, 0x390002bf)
    if [i for i, (a, b) in enumerate(zip(data, result)) if a != b] != [offset]:
        raise ValueError('Unexpected HAL delta')
    return bytes(result)


def transform(data):
    if hashlib.sha256(data).hexdigest() != STOCK_SHA256:
        raise ValueError('Requires unmodified OS4.0.0.23.XPBCNXM primary audio XML')
    pattern = rb'        <devicePort tagName="fm_tuner_mic"[^>]*>.*?</devicePort>\n'
    result, count = re.subn(pattern, b'', data, flags=re.DOTALL)
    if count != 1 or result.count(b',fm_tuner_mic,') != 1:
        raise ValueError('Unexpected FM port or route references')
    result = result.replace(b',fm_tuner_mic,', b',')
    root = ET.fromstring(result)
    if b'fm_tuner_mic' in result:
        raise ValueError('Dangling FM input reference')
    for module in root.findall('module'):
        names = {p.get('tagName') for p in module.findall('./devicePorts/devicePort')}
        names.update(p.get('name') for p in module.findall('./mixPorts/mixPort'))
        for route in module.findall('./routes/route'):
            if route.get('sink') not in names or not set(route.get('sources').split(',')) <= names:
                raise ValueError('Dangling audio route')
    return result

