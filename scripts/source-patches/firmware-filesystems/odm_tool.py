#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Device-specific camera ODM derivation; no unchanged-prebuilt or module bypass."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

if __package__:
    from . import derive_vendor as image, odm_avb, odm_image, odm_target_files, stage_inputs
else:
    import derive_vendor as image
    import odm_avb
    import odm_image
    import odm_target_files
    import stage_inputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("derive", "verify", "seal", "verify-avb",
                                            "sync-avb-info", "audit-stage", "export",
                                            "verify-target-files"))
    for name in ("reader", "fsck", "mkfs", "stock", "raw", "image", "output", "id-buffer-patch",
                 "device-config-patch", "extension-config-patch", "key", "public-key", "fec", "avbtool", "image-info",
                 "target-files", "target-files-zip", "stage", "source-notice",
                 "stage-file-list", "stage-fs-config", "stage-target-out",
                 "stage-selabel-lookup", "stage-file-contexts"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--algorithm")
    args = parser.parse_args()
    source = ("reader", "fsck", "stock", "id_buffer_patch", "device_config_patch", "extension_config_patch")
    signed = (*source, "raw", "image", "key", "public_key", "algorithm", "fec")
    required = {
        "derive": (*source, "mkfs", "output"), "verify": (*source, "raw"),
        "audit-stage": ("reader", "stock", "stage", "id_buffer_patch", "device_config_patch", "extension_config_patch"),
        "seal": (*source, "raw", "output", "key", "public_key", "algorithm", "fec",
                 "avbtool", "image_info"),
        "verify-avb": signed,
        "sync-avb-info": ("image", "image_info", "key", "public_key", "fec"),
        "export": (*signed, "target_files", "stage"),
        "verify-target-files": (*signed, "stage"),
    }
    try:
        stage_values = (args.stage, args.stage_file_list, args.stage_fs_config,
                        args.stage_target_out, args.stage_selabel_lookup, args.stage_file_contexts)
        stage_config = None
        if any(value is not None for value in stage_values):
            image.require(args.command != "sync-avb-info"
                          and all(value is not None for value in stage_values),
                          "complete ODM stage inputs are required for this command")
            metadata = stage_inputs.AndroidMetadata(args.stage_fs_config, args.stage_target_out,
                args.stage_selabel_lookup, args.stage_file_contexts, partition="odm")
            stage_config = stage_inputs.Inputs(args.stage, args.stage_file_list, {}, metadata)
        image.require(args.command not in {"audit-stage", "export", "verify-target-files"}
                      or stage_config is not None,
                      "complete ODM stage inputs are required for this command")
        image.require(all(getattr(args, name) is not None for name in required[args.command]),
                      "missing required ODM command inputs")
        transforms = (args.id_buffer_patch, args.device_config_patch, args.extension_config_patch)
        report = {"command": args.command, "verification": "passed"}
        if args.command == "derive":
            report = odm_image.derive(args.reader, args.mkfs, args.fsck, args.stock,
                                      args.output, transforms, args.source_notice, stage_config)
        elif args.command == "verify":
            report = odm_image.verify(args.reader, args.fsck, args.stock, args.raw,
                                      transforms, args.source_notice, stage_config)
        elif args.command == "audit-stage":
            odm_image.audit_stage(args.reader, args.stock, args.stage, transforms,
                                  args.source_notice, stage_config)
        elif args.command == "seal":
            odm_image.verify(args.reader, args.fsck, args.stock, args.raw,
                             transforms, args.source_notice, stage_config)
            report = odm_avb.seal(args.reader, args.stock, args.raw, args.output, args.image_info,
                                  args.avbtool, args.key, args.public_key, args.algorithm, args.fec)
        elif args.command == "sync-avb-info":
            odm_avb.sync_info(args.image, args.image_info, args.key, args.public_key, args.fec)
        else:
            arguments = (args.reader, args.fsck, args.stock, args.raw, args.image, transforms,
                         args.key, args.public_key, args.algorithm, args.fec)
            if args.command == "verify-avb":
                report = odm_target_files.verify_source(*arguments, source_notice=args.source_notice,
                                                        stage_inputs=stage_config)
            elif args.command == "export":
                image.require(args.target_files_zip is None, "ODM export requires a directory")
                report = odm_target_files.export(*arguments, args.target_files, args.stage,
                                                 args.source_notice, stage_config)
            else:
                report = odm_target_files.verify(*arguments, args.stage,
                    args.target_files, args.target_files_zip, args.source_notice, stage_config)
        print(json.dumps(report, sort_keys=True))
    except (ValueError, OSError, EOFError, KeyError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = (error.stderr or b"").decode("utf-8", "replace").strip()
            parser.exit(1, f"{error.cmd[0]} failed ({error.returncode}): {message}\n")
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
