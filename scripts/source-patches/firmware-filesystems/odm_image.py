# SPDX-License-Identifier: MIT
"""Derive ODM by replaying the three guarded camera transformations on raw inodes.

The transform sources are explicit build prerequisites. Only their pure patch_elf
functions run; module packaging and previous patched output are never inputs.
"""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile
import uuid

if __package__:
    from . import derive_vendor as image, vendor_target_files as tf
else:
    import derive_vendor as image
    import vendor_target_files as tf

CAMERA_PATHS = (b"lib64/libmicamera_adapter.so", b"lib64/hw/com.qti.chi.override.so",
                b"lib64/libchifeature2.so")
# Audited instruction byte offsets, not digests or copies of proprietary data.
CHANGES = ({0x40539, 0x40551}, {0x4E7F38, 0x4E7F39, 0x4E7F3B},
           {0x4E7F38, 0x4E7F39, 0x4E7F3B})


def patch_bytes(original: bytes, source: Path, index: int) -> bytes:
    image.require(source.is_file(), "camera transformation source is missing")
    spec = importlib.util.spec_from_file_location("_popsicle_odm_transform", source)
    image.require(spec is not None and spec.loader is not None, "invalid transformation source")
    module = importlib.util.module_from_spec(spec)
    # SourceFileLoader can create __pycache__ in its source tree. Reading and
    # compiling the explicit source instead keeps both reference trees read-only.
    exec(compile(source.read_bytes(), str(source), "exec"), module.__dict__)
    result = module.patch_elf(original)
    image.require(isinstance(result, bytes) and len(result) == len(original),
                  "camera transformation changed the ELF extent")
    changed = {i for i, (a, b) in enumerate(zip(original, result)) if a != b}
    image.require(changed == CHANGES[index], "camera transformation changed unexpected bytes")
    return result


def replacements(reader: Path, stock: Path, entries: dict, transforms: tuple[Path, Path, Path],
                 source_notice: Path | None = None) -> dict:
    image.require(len(transforms) == 3, "all three camera transformation sources are required")
    result = {}
    for index, path in enumerate(CAMERA_PATHS):
        image.require(path in entries, "official camera input is missing")
        metadata = entries[path]
        image.require(metadata["mode"] == stat.S_IFREG | 0o644
                      and metadata["uid"] == metadata["gid"] == 0
                      and metadata["nlink"] == 1
                      and metadata["xattrs"].get(b"security.selinux") == b"u:object_r:vendor_file:s0",
                      "official camera inode identity differs")
        image.require(sum(item["nid"] == metadata["nid"] for item in entries.values()) == 1,
                      "camera input has an aliased inode")
        original = image.run([reader, "cat", stock, os.fsdecode(path)]).stdout
        image.require(len(original) == metadata["size"], "official camera extent differs")
        result[path] = patch_bytes(original, transforms[index], index)
    notice = image.managed_notice(reader, stock, entries, source_notice)
    if notice is not None:
        result[image.NOTICE] = notice
    return result


def check_product_stage(reader: Path, stock: Path, entries: dict, changed: dict,
                        inputs, source_notice: Path | None) -> None:
    if inputs is None:
        return  # Image-only validation has no product stage to compare.
    image.require(not inputs.sources and inputs.metadata.partition == "odm",
                  "ODM stage accepts only its guarded providers and ODM metadata")
    # Camera repairs are image transformations, so a source-stage camera install
    # is optional. If selected, it must contain the same guarded result.
    managed = {path: changed[path] for path in CAMERA_PATHS
               if (inputs.stage / os.fsdecode(path)).exists()}
    if source_notice is not None:
        managed[image.NOTICE] = source_notice.read_bytes()
    resolved = inputs.resolve(entries,
        lambda path: image.run([reader, "cat", stock, os.fsdecode(path)]).stdout, managed)
    image.require(not resolved.replacements and not resolved.additions,
                  "ODM stage exceeds the guarded camera and NOTICE change set")


def compare_unchanged(reader: Path, stock: Path, derived: Path, entries: dict, changed: dict) -> None:
    """Stream every unmodified inode from both raw images, using the existing reader."""
    visited = set()
    for path, metadata in entries.items():
        if path in changed or not (stat.S_ISREG(metadata["mode"])
                                       or stat.S_ISLNK(metadata["mode"])):
            continue
        if metadata["nid"] in visited:
            continue
        visited.add(metadata["nid"])
        command = [str(reader), "cat", str(derived), os.fsdecode(path)]
        with tempfile.TemporaryFile() as errors, subprocess.Popen(
                command, stdout=subprocess.PIPE, stderr=errors, env=image.environment()) as process:
            try:
                tf.compare_stream_to_image(reader, stock, path, process.stdout, metadata["size"])
            except BaseException:
                process.kill()
                raise
            finally:
                process.stdout.close()
            if process.wait():
                errors.seek(0)
                raise subprocess.CalledProcessError(process.returncode, command,
                                                    stderr=errors.read())


def verify(reader: Path, fsck: Path, stock: Path, raw: Path,
           transforms: tuple[Path, Path, Path], source_notice: Path | None = None,
           stage_inputs=None) -> dict:
    image.require(not os.path.samefile(stock, raw), "derived ODM aliases stock")
    image.run([fsck, "--extract", stock])
    image.run([fsck, "--extract", raw])
    before = image.inventory(reader, stock)
    changed = replacements(reader, stock, before, transforms, source_notice)
    check_product_stage(reader, stock, before, changed, stage_inputs, source_notice)
    after = image.inventory(reader, raw)
    image.require(set(before) == set(after), "ODM path inventory changed")
    for path, expected in before.items():
        if path in changed:
            expected = expected | {"size": len(changed[path])}
        for field in set(expected) - {"nid"}:
            image.require(after[path][field] == expected[field],
                          f"ODM metadata changed: {os.fsdecode(path)!r} {field}")
    image.require(image.hardlinks(before) == image.hardlinks(after),
                  "ODM hardlink equivalence groups changed")
    for path, expected in changed.items():
        image.require(image.run([reader, "cat", raw, os.fsdecode(path)]).stdout == expected,
                      "derived ODM bytes differ from the guarded transformation or NOTICE input")
    compare_unchanged(reader, stock, raw, before, changed)
    old, new = image.superblock(reader, stock), image.superblock(reader, raw)
    for key in ("block_size", "uuid", "volume_hex", "feature_compat", "feature_incompat"):
        image.require(new[key] == old[key], f"ODM filesystem property changed: {key}")
    image.require(new["blocks"] * new["block_size"] == raw.stat().st_size,
                  "ODM raw intermediate contains a non-filesystem tail")
    return {"original_paths": len(before), "modified_paths": [os.fsdecode(p) for p in changed],
            "new_paths": [], "modified_metadata_paths": [os.fsdecode(p) for p in changed
                if len(changed[p]) != before[p]["size"]],
            "filesystem_bytes": raw.stat().st_size,
            "verification": "complete inode metadata, hardlink groups and all file bytes"}


def derive(reader: Path, mkfs: Path, fsck: Path, stock: Path, output: Path,
           transforms: tuple[Path, Path, Path], source_notice: Path | None = None,
           stage_inputs=None) -> dict:
    image.require(stock.is_file(), "official ODM is missing")
    image.require(not output.exists() and not output.is_symlink(), "ODM output already exists")
    image.require(output.parent.is_dir(), "ODM output parent must already exist")
    image.run([fsck, "--extract", stock])
    entries = image.inventory(reader, stock)
    changed = replacements(reader, stock, entries, transforms, source_notice)
    check_product_stage(reader, stock, entries, changed, stage_inputs, source_notice)
    meta = image.superblock(reader, stock)
    image.require(0 < meta["block_size"] * meta["blocks"] <= stock.stat().st_size,
                  "invalid original ODM filesystem extent")
    data_size = sum(item["size"] for item in entries.values() if stat.S_ISREG(item["mode"]))
    image.require(shutil.disk_usage(output.parent).free > 2 * data_size + 128 * 1024**2,
                  "insufficient scratch space for complete ODM derivation")
    with tempfile.TemporaryDirectory(prefix=".odm-erofs-", dir=output.parent) as temporary:
        workspace = Path(temporary)
        archive, candidate = workspace / "source.tar", workspace / "odm.erofs"
        image.write_image_tar(reader, stock, entries, archive, changed)
        volume = bytes.fromhex(meta["volume_hex"]).rstrip(b"\0")
        image.require(b"\0" not in volume, "noncanonical ODM volume label")
        image.run([mkfs, "--clean=data", "--tar=f", "-zlz4hc", "--preserve-mtime", "--mkfs-time",
                   f'-b{meta["block_size"]}', f'-T{meta["build_time"]}',
                   f'-U{uuid.UUID(hex=meta["uuid"])}', "-L", os.fsdecode(volume),
                   "--ovlfs-strip=0", "--workers=4", candidate, archive])
        report = verify(reader, fsck, stock, candidate, transforms, source_notice, stage_inputs)
        os.link(candidate, output)
        return report


def audit_stage(reader: Path, stock: Path, stage: Path, transforms: tuple[Path, Path, Path],
                source_notice: Path | None = None, stage_inputs=None) -> None:
    """Check guarded camera bytes and, when selected, the exact source NOTICE input."""
    entries = image.inventory(reader, stock)
    changed = replacements(reader, stock, entries, transforms, source_notice)
    if stage_inputs is not None:
        image.require(stage.resolve() == stage_inputs.stage.resolve(), "different ODM stage inputs")
        check_product_stage(reader, stock, entries, changed, stage_inputs, source_notice)
        return
    # Direct image callers can omit product metadata. The CLI supplies the
    # complete product group whenever a stage is selected.
    if not stage.exists() and not stage.is_symlink():
        return
    image.require(stage.is_dir() and not stage.is_symlink(), "ODM staging is not a real directory")
    for path, staged in tf.logical_paths(stage).items():
        image.require(path in entries, f"unapproved ODM staged path: {os.fsdecode(path)}")
        expected = entries[path]
        kind = stat.S_IFMT(staged.lstat().st_mode)
        image.require(kind == stat.S_IFMT(expected["mode"]), "ODM staged inode type differs")
        if path == image.NOTICE and source_notice is not None:
            image.require(staged.read_bytes() == source_notice.read_bytes(),
                          "ODM staged source NOTICE differs")
        elif path in changed:
            image.require(staged.read_bytes() == changed[path], "ODM staged camera provider differs")
        elif kind == stat.S_IFLNK:
            target = image.run([reader, "cat", stock, os.fsdecode(path)]).stdout
            image.require(os.fsencode(os.readlink(staged)) == target, "ODM staged symlink differs")
        elif kind == stat.S_IFREG:
            with staged.open("rb") as stream:
                tf.compare_stream_to_image(reader, stock, path, stream, expected["size"])
