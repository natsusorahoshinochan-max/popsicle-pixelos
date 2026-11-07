"""Product-owned guarded camera ELF transformation; no module packaging.

Promoted unchanged from the frozen modules/popsicle-camera-id-buffer/build.py.
"""

import struct


FUNCTION = b"_ZN7adapter12convertToHALERKN5micam6StreamEP13camera_stream"

FUNCTION_ADDRESS = 0x404E8

FUNCTION_SIZE = 200

GUARDS = {
    0x40538: 0x52800100,  # mov w0, #8: real new[] allocation size
    0x40540: 0x9401F010,  # bl operator new[] PLT
    0x40544: 0xB9402E83,  # ldr w3, [x20, #0x2c]: int32 physical ID
    0x40548: 0x3100047F,  # cmn w3, #1: absent-ID sentinel
    0x4054C: 0x540000A0,  # b.eq: do not format absent ID
    0x40550: 0x52800101,  # mov w1, #8: FORTIFY destination object size
    0x40558: 0x94000016,  # bl fortified sprintf wrapper
    0x40560: 0xF900127F,  # original NULL physical_camera_id behavior retained
    0x405AC: 0x1401EFFB,  # original delete[] retained
    0x40634: 0x9401EFDF,  # original __vsprintf_chk retained
}

PATCHES = {0x40538: 0x52800200, 0x40550: 0x52800201}

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def patch_elf(data: bytes) -> bytes:
    require(len(data) >= 64, "Truncated ELF")
    require(data[:7] == b"\x7fELF\x02\x01\x01", "Expected ELF64 little endian")
    header = struct.unpack_from("<16sHHIQQQIHHHHHH", data)
    require(header[1:4] == (3, 183, 1), "Expected AArch64 ET_DYN ELF v1")
    phoff, shoff = header[5:7]
    phsize, phnum, shsize, shnum = header[9:13]
    require(phsize == 56 and shsize == 64 and phnum > 0 and shnum > 0,
            "Unexpected ELF table layout")
    require(phoff + phsize * phnum <= len(data) and shoff + shsize * shnum <= len(data),
            "ELF tables exceed file")
    segments = [struct.unpack_from("<IIQQQQQQ", data, phoff + i * phsize)
                for i in range(phnum)]
    sections = [struct.unpack_from("<IIQQQQIIQQ", data, shoff + i * shsize)
                for i in range(shnum)]

    def offset(address: int, size: int, executable: bool = False) -> int:
        matches = [p for p in segments if p[0] == 1 and p[3] <= address
                   and address + size <= p[3] + p[5] and (not executable or p[1] & 1)]
        require(len(matches) == 1, f"Ambiguous or missing ELF segment at {address:#x}")
        result = matches[0][2] + address - matches[0][3]
        require(result + size <= len(data), "Segment exceeds file")
        return result

    symbols = []
    for section in sections:
        if section[1] != 11:  # SHT_DYNSYM
            continue
        require(section[9] == 24 and section[5] % 24 == 0, "Unexpected dynsym layout")
        require(section[6] < len(sections), "Invalid dynsym string table")
        strings = sections[section[6]]
        require(strings[1] == 3, "Expected dynsym SHT_STRTAB")
        require(section[4] + section[5] <= len(data)
                and strings[4] + strings[5] <= len(data), "Symbol data exceeds file")
        table = data[strings[4]:strings[4] + strings[5]]
        for pos in range(section[4], section[4] + section[5], 24):
            name, info, _, index, value, size = struct.unpack_from("<IBBHQQ", data, pos)
            require(name < len(table), "Invalid symbol string offset")
            end = table.find(b"\0", name)
            require(end >= 0, "Unterminated symbol name")
            if table[name:end] == FUNCTION:
                symbols.append((info, index, value, size))
    require(len(symbols) == 1, "Expected exactly one camera_stream converter symbol")
    info, index, value, size = symbols[0]
    require(info == 0x12 and index != 0 and value == FUNCTION_ADDRESS
            and size == FUNCTION_SIZE, "Camera converter identity/layout differs from audited input")
    for address, expected in GUARDS.items():
        actual = struct.unpack_from("<I", data, offset(address, 4, True))[0]
        require(actual == expected, f"Input instruction mismatch at {address:#x}")
    require(data[offset(0x279B0, 3):offset(0x279B0, 3) + 3] == b"%d\0",
            "Unexpected ID format string")

    patched = bytearray(data)
    for address, replacement in PATCHES.items():
        struct.pack_into("<I", patched, offset(address, 4, True), replacement)
    expected_changes = {offset(address, 4, True) + 1 for address in PATCHES}
    actual_changes = {i for i, (before, after) in enumerate(zip(data, patched)) if before != after}
    require(actual_changes == expected_changes, "Unexpected byte changes")
    for address, expected in GUARDS.items():
        require(struct.unpack_from("<I", patched, offset(address, 4, True))[0]
                == PATCHES.get(address, expected), "Post-patch instruction verification failed")
    return bytes(patched)
