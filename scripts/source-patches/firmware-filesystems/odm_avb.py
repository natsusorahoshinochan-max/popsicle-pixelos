# SPDX-License-Identifier: MIT
"""The fixed ODM cohort using the shared strict AVB, expected-key and FEC gates."""
from __future__ import annotations

if __package__:
    from . import vendor_avb as shared
else:
    import vendor_avb as shared

COHORT = {
    "com.android.build.odm.os_version": b"ro.odm.build.version.release",
    "com.android.build.odm.fingerprint": b"ro.odm.build.fingerprint",
}
CONTRACT = {"partition": "odm", "cohort": COHORT}


def parse(path):
    return shared.parse(path, **CONTRACT)


def original_properties(reader, stock):
    return shared.original_properties(reader, stock, **CONTRACT)


def verify(reader, stock, raw, sealed, key, public_key, algorithm, fec):
    return shared.verify(reader, stock, raw, sealed, key, public_key, algorithm, fec, **CONTRACT)


def seal(reader, stock, raw, output, info, avb, key, public_key, algorithm, fec):
    return shared.seal(reader, stock, raw, output, info, avb, key, public_key, algorithm, fec,
                       **CONTRACT)


def verify_info(sealed, data, key, public_key, fec):
    return shared.verify_info(sealed, data, key, public_key, fec, **CONTRACT)


def sync_info(sealed, path, key, public_key, fec):
    return shared.sync_info(sealed, path, key, public_key, fec, **CONTRACT)
