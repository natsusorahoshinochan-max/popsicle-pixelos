"""Product-owned guarded camera ELF transformation; no module packaging.

Promoted unchanged from the frozen modules/popsicle-camera-device-config/build.py.
"""

import struct


FUNCTION = b"_ZN15ExtensionModule18GetDevicesSettingsEv"

FUNCTION_ADDRESS = 0x4E7D20

FUNCTION_SIZE = 1516

GUARDS = {
    0x4E7EC0: 0xF9422A73,  # load device settings
    0x4E7EC4: 0x91036260,  # configuration string at settings + 0xd8
    0x4E7EC8: 0x940923C6,  # string assign PLT
    0x4E7ECC: 0xF94016CB,  # original common epilogue (stack guard retained)
    0x4E7F0C: 0x5109068C,  # SoC - 0x241
    0x4E7F10: 0x7102599F,  # range 0x96
    0x4E7F14: 0x540002A8,  # out-of-range branch
    0x4E7F18: 0xD0FFE12F,  # jump table page 0x10d000
    0x4E7F1C: 0x912BF1EF,  # table at 0x10dafc
    0x4E7F20: 0x10000082,  # branch base 0x4e7f30
    0x4E7F24: 0x386C69E8,  # load one-byte table entry
    0x4E7F28: 0x8B080842,  # target = base + entry * 4
    0x4E7F2C: 0xD61F0040,  # indirect branch
    0x4E7F30: 0xD503249F,  # BTI landing instruction retained
    0x4E7F34: 0x940928D9,  # shared framework detector call retained
    0x4E7F38: 0x35FFFCA0,  # cbnz w0, 0x4e7ecc
    0x4E7F3C: 0x940928E9,  # original IsGSIVersion call, no longer reached here
    0x4E7F40: 0x35FFFC60,
    0x4E7F44: 0xD0FFDF21,  # kaanapali_gsi.xml page
    0x4E7F48: 0x913EC021,  # kaanapali_gsi.xml offset
    0x4E7F4C: 0x17FFFFDD,  # original fallback string assignment
}

PATCHES = {0x4E7F38: 0x17FFFFE5}  # b 0x4e7ecc: retain configured device XML

def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)

def patch_elf(data: bytes) -> bytes:
    require(len(data) >= 64, "Truncated ELF")
    require(len(data) == 7804064, "Unexpected audited library size")
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
    require(len(symbols) == 1, "Expected exactly one GetDevicesSettings symbol")
    info, index, value, size = symbols[0]
    require(info == 0x12 and index != 0 and value == FUNCTION_ADDRESS
            and size == FUNCTION_SIZE, "GetDevicesSettings identity/layout differs from audited input")
    for address, expected in GUARDS.items():
        actual = struct.unpack_from("<I", data, offset(address, 4, True))[0]
        require(actual == expected, f"Input instruction mismatch at {address:#x}")
    require(data[offset(0x10DAFC + 660 - 0x241, 1)] == 0,
            "SoC 660 jump table entry differs")
    for address, expected in ((0xCDFB0, b"kaanapali_gsi.xml\0"),
                              (0x78096, b"popsicle.xml\0")):
        start = offset(address, len(expected))
        require(data[start:start + len(expected)] == expected,
                f"Unexpected configuration name at {address:#x}")
    branch = PATCHES[0x4E7F38]
    displacement = branch & 0x3FFFFFF
    if displacement & 0x2000000:
        displacement -= 0x4000000
    require(0x4E7F38 + displacement * 4 == 0x4E7ECC,
            "Replacement branch target differs")

    patched = bytearray(data)
    for address, replacement in PATCHES.items():
        struct.pack_into("<I", patched, offset(address, 4, True), replacement)
    expected_changes = {offset(0x4E7F38, 4, True) + i for i in (0, 1, 3)}
    actual_changes = {i for i, (before, after) in enumerate(zip(data, patched)) if before != after}
    require(actual_changes == expected_changes, "Unexpected byte changes")
    for address, expected in GUARDS.items():
        require(struct.unpack_from("<I", patched, offset(address, 4, True))[0]
                == PATCHES.get(address, expected), "Post-patch instruction verification failed")
    return bytes(patched)
