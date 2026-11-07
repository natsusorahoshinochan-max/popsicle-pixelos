# SPDX-License-Identifier: MIT
"""Complete ODM directory and ZIP views tied to the same verified sealed image."""
from __future__ import annotations

from pathlib import Path
import zipfile

if __package__:
    from . import derive_vendor as image, odm_avb, odm_image, vendor_target_files as tf
else:
    import derive_vendor as image
    import odm_avb
    import odm_image
    import vendor_target_files as tf


def verify_source(reader, fsck, stock, raw, sealed, transforms, key, public_key, algorithm, fec,
                  source_notice=None, stage_inputs=None):
    report = odm_image.verify(reader, fsck, stock, raw, transforms, source_notice, stage_inputs)
    report["avb"] = odm_avb.verify(reader, stock, raw, sealed, key, public_key, algorithm, fec)
    return report


def export(reader, fsck, stock, raw, sealed, transforms, key, public_key, algorithm, fec,
           target_files: Path, stage: Path, source_notice=None, stage_inputs=None):
    report = verify_source(reader, fsck, stock, raw, sealed, transforms, key, public_key,
                           algorithm, fec, source_notice, stage_inputs)
    odm_image.audit_stage(reader, stock, stage, transforms, source_notice, stage_inputs)
    # This creates only the complete ODM view and its metadata. The existing Make
    # image provider must supply IMAGES/odm.img before the final publication gate.
    tf.export(reader, sealed, target_files, partition="odm")
    return report


def verify(reader, fsck, stock, raw, sealed, transforms, key, public_key, algorithm, fec,
           stage: Path, target_files: Path | None = None, target_files_zip: Path | None = None,
           source_notice=None, stage_inputs=None):
    image.require(bool(target_files) != bool(target_files_zip),
                  "select exactly one ODM target-files directory or ZIP")
    report = verify_source(reader, fsck, stock, raw, sealed, transforms, key, public_key,
                           algorithm, fec, source_notice, stage_inputs)
    odm_image.audit_stage(reader, stock, stage, transforms, source_notice, stage_inputs)
    if target_files is not None:
        tf.verify_directory(reader, sealed, target_files, partition="odm")
        info = (target_files / "META/misc_info.txt").read_bytes()
    else:
        tf.verify_zip(reader, sealed, target_files_zip, partition="odm")
        with zipfile.ZipFile(target_files_zip) as archive:
            info = archive.read("META/misc_info.txt")
    odm_avb.verify_info(sealed, info, key, public_key, fec)
    return report
