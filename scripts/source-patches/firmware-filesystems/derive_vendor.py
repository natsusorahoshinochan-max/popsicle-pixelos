#!/usr/bin/env python3
# SPDX-License-Identifier: MIT
"""Add the built tracing descriptor to an independent official EROFS copy.

All existing metadata and content are read back from the images themselves.
No host extraction tree, mounted xattrs, digest list, or success marker is evidence.
The output is an unsigned filesystem intermediate, never a flashable AVB image.
"""
from __future__ import annotations

import argparse
import base64
from collections import defaultdict
import gzip
import io
import json
import os
from pathlib import Path
import shutil
import stat
import subprocess
import tarfile
import tempfile
from urllib.parse import quote_from_bytes
import uuid
import xml.etree.ElementTree as ET

DESTINATION = b"etc/tracing_descriptors.gz"
FSTAB = b"etc/fstab.qcom"
FSTAB_SUFFIX = b",avb_keys=/avb/popsicle-userdebug.avbpubkey"
LABEL = b"u:object_r:vendor_configs_file:s0"
AMBIENT = b"bin/mi_ambient"
AMBIENT_LABEL = b"u:object_r:mi_ambient_exec:s0"
NOTICE = b"etc/NOTICE.xml.gz"


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def merge_notices(oem: bytes, source: bytes) -> bytes:
    """Retain each source's text and associations, including colliding content IDs."""
    merged = ET.Element("licenses")
    for prefix, compressed in (("oem", oem), ("source", source)):
        try:
            text = gzip.decompress(compressed).decode("utf-8")
            require("<!DOCTYPE" not in text.upper() and "<!ENTITY" not in text.upper(),
                    "NOTICE document declarations are not supported")
            root = ET.fromstring(text)
        except (OSError, EOFError, UnicodeError, ET.ParseError) as error:
            raise ValueError(f"invalid {prefix} gzip/XML NOTICE") from error
        require(root.tag == "licenses" and not root.attrib and not (root.text or "").strip(),
                "unknown NOTICE root structure")
        ids, references = set(), set()
        for child in root:
            require(child.tag in {"file-name", "file-content"} and not len(child)
                    and not (child.tail or "").strip(), "unknown NOTICE entry structure")
            allowed = {"contentId", "lib"} if child.tag == "file-name" else {"contentId"}
            require(set(child.attrib) <= allowed and child.attrib.get("contentId")
                    and child.text and child.text.strip(), "invalid NOTICE entry")
            content_id = child.attrib["contentId"]
            if child.tag == "file-content":
                require(content_id not in ids, "duplicate NOTICE content ID")
                ids.add(content_id)
            else:
                references.add(content_id)
            # XML parsing decodes the XML layer only. Do not HTML-unescape the
            # resulting license body: both input generators retain that layer.
            attributes = dict(child.attrib)
            attributes["contentId"] = prefix + ":" + content_id
            ET.SubElement(merged, child.tag, attributes).text = child.text
        require(references <= ids, "dangling NOTICE content reference")
    xml = ET.tostring(merged, encoding="utf-8", xml_declaration=True)
    return gzip.compress(xml, mtime=0)


def managed_notice(reader: Path, stock: Path, entries: dict,
                   source_notice: Path | None) -> bytes | None:
    if source_notice is None:
        return None
    require(NOTICE in entries and stat.S_ISREG(entries[NOTICE]["mode"])
            and entries[NOTICE]["nlink"] == 1, "NOTICE requires an unaliased original inode")
    require(source_notice.is_file() and not source_notice.is_symlink(),
            "source NOTICE must be a regular generated file")
    original = run([reader, "cat", stock, os.fsdecode(NOTICE)]).stdout
    return merge_notices(original, source_notice.read_bytes())


def environment() -> dict[str, str]:
    # LD_PRELOAD extraction shims and ambient timestamp overrides are not proof.
    return {key: value for key, value in os.environ.items()
            if key not in {"LD_PRELOAD", "LD_LIBRARY_PATH", "SOURCE_DATE_EPOCH",
                           "TAR_OPTIONS", "EROFS_CONFIGURE"}}


def run(command: list[str | Path], **kwargs) -> subprocess.CompletedProcess:
    return subprocess.run([str(arg) for arg in command], check=True, env=environment(),
                          stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs)


def inventory(reader: Path, image: Path) -> dict[bytes, dict]:
    result = {}
    for line in run([reader, "inventory", image]).stdout.splitlines():
        item = json.loads(line)
        path = bytes.fromhex(item.pop("path_hex"))
        require(not path or (not path.startswith(b"/") and b"\0" not in path
                             and all(part not in {b"", b".", b".."}
                                     for part in path.split(b"/"))), "unsafe image path")
        require(path not in result, "duplicate image path")
        pairs = [(bytes.fromhex(key), bytes.fromhex(value)) for key, value in item["xattrs"]]
        require(len(dict(pairs)) == len(pairs), "duplicate xattr name")
        item["xattrs"] = dict(pairs)
        result[path] = item
    require(b"" in result and stat.S_ISDIR(result[b""]["mode"]), "missing root directory")
    return result


def superblock(reader: Path, image: Path) -> dict:
    return json.loads(run([reader, "super", image]).stdout)


def hardlinks(items: dict[bytes, dict]) -> set[tuple[bytes, ...]]:
    groups = defaultdict(list)
    for path, item in items.items():
        if not stat.S_ISDIR(item["mode"]):
            groups[item["nid"]].append(path)
    return {tuple(sorted(paths)) for paths in groups.values()}


def descriptor_bytes(path: Path) -> bytes:
    require(path.is_file(), "descriptor is not a regular file")
    data = path.read_bytes()
    # The real tracing_proto_extensions generator and consumer tests establish the
    # protobuf schema; this gate additionally catches corrupt/truncated gzip input.
    require(data.startswith(b"\x1f\x8b"), "descriptor is not gzip")
    gzip.decompress(data)
    return data


def new_metadata(parent: dict, data: bytes) -> dict:
    return {"mode": stat.S_IFREG | 0o644, "uid": 0, "gid": 0,
            "size": len(data), "mtime": parent["mtime"], "mtime_nsec": parent["mtime_nsec"],
            "nlink": 1, "rdev": 0, "xattrs": {b"security.selinux": LABEL}}


def managed_fstab(reader: Path, stock: Path, entries: dict, path: Path | None) -> bytes | None:
    if path is None:
        return None
    require(FSTAB in entries and stat.S_ISREG(entries[FSTAB]["mode"])
            and entries[FSTAB]["nlink"] == 1, "managed fstab must be an unaliased regular inode")
    original = run([reader, "cat", stock, os.fsdecode(FSTAB)]).stdout
    require(FSTAB_SUFFIX not in original, "stock already contains the managed AVB key")
    changed = path.read_bytes()
    require(changed.count(FSTAB_SUFFIX) == 4
            and changed.replace(FSTAB_SUFFIX, b"") == original,
            "fstab change exceeds the four managed vendor/ODM AVB suffixes")
    kinds = set()
    for line in changed.splitlines():
        if FSTAB_SUFFIX not in line:
            continue
        fields = line.split()
        require(len(fields) == 5 and fields[0] in {b"vendor", b"odm"}
                and fields[1] == b"/" + fields[0]
                and fields[2] in {b"ext4", b"erofs"}
                and fields[4].endswith(FSTAB_SUFFIX)
                and b"avb=vbmeta" in fields[4].split(b","), "invalid managed fstab entry")
        kinds.add((fields[0], fields[2]))
    require(kinds == {(partition, kind) for partition in (b"vendor", b"odm")
                      for kind in (b"ext4", b"erofs")},
            "managed fstab must cover both vendor/ODM filesystems")
    return changed



def managed_ambient_label(reader: Path, stock: Path, entries: dict, enabled: bool) -> dict:
    if not enabled:
        return {}
    contexts = b"etc/selinux/vendor_file_contexts"
    for path in (AMBIENT, contexts):
        require(path in entries and stat.S_ISREG(entries[path]["mode"])
                and entries[path]["nlink"] == 1, "ambient repair requires an unaliased regular inode")
    original = entries[AMBIENT]
    require(original["mode"] == stat.S_IFREG | 0o755 and original["uid"] == 0
            and original["gid"] == 2000, "ambient original entrypoint ownership or mode differs")
    require(original["xattrs"].get(b"security.selinux") == b"u:object_r:vendor_file:s0",
            "ambient original label differs")
    declarations = [line.split() for line in run([reader, "cat", stock, os.fsdecode(contexts)]).stdout.splitlines()
                    if line.split() and line.split()[0] == b"/(vendor|system/vendor)/bin/mi_ambient"]
    require(declarations == [[b"/(vendor|system/vendor)/bin/mi_ambient", AMBIENT_LABEL]],
            "ambient original file_contexts declaration differs")
    # Replace only the mislabeled entrypoint's SELinux EA. Preserve all bytes,
    # ownership, mode, times and every other EA from the original image.
    return {AMBIENT: original | {"xattrs": original["xattrs"] | {b"security.selinux": AMBIENT_LABEL}}}


def managed_audio(reader: Path, stock: Path, entries: dict, enabled: bool) -> dict:
    if not enabled:
        return {}
    if __package__:
        from . import audio_repair
    else:
        import audio_repair
    transforms = {
        b"etc/audio/audio_module_config_primary.xml": audio_repair.transform,
        b"lib64/hw/libaudiocorehal.qti.so": audio_repair.patch_hal,
    }
    output = {}
    for path, transform in transforms.items():
        require(path in entries and stat.S_ISREG(entries[path]["mode"])
                and entries[path]["nlink"] == 1, "audio repair requires an unaliased original file")
        output[path] = transform(run([reader, "cat", stock, os.fsdecode(path)]).stdout)
    return output


def resolve_stage_inputs(inputs, reader: Path, stock: Path, entries: dict,
                         descriptor: bytes, fstab: bytes | None,
                         policy: dict[bytes, bytes], source_notice: Path | None):
    if inputs is None:
        return {}, {}
    managed = {DESTINATION: descriptor, **policy}
    # The product installs the fstab input into root/recovery. Vendor keeps its
    # original inode with the checked suffix change even without a Soong stage copy.
    if fstab is not None and (inputs.stage / os.fsdecode(FSTAB)).exists():
        managed[FSTAB] = fstab
    if source_notice is not None:
        managed[NOTICE] = source_notice.read_bytes()
    resolution = inputs.resolve(entries,
                                lambda path: run([reader, "cat", stock, os.fsdecode(path)]).stdout,
                                managed)
    return resolution.replacements, resolution.additions


def added_parent_metadata(entries: dict, additions: dict) -> dict:
    changes = {}
    for path, (metadata, _) in additions.items():
        parent = path.rpartition(b"/")[0]
        if parent in entries and stat.S_ISDIR(metadata["mode"]):
            if parent not in changes:
                changes[parent] = dict(entries[parent])
            changes[parent]["nlink"] += 1
    return changes


def verify(reader: Path, fsck: Path, stock: Path, derived: Path, descriptor: Path,
           fstab: Path | None = None, policy_inputs=None, repair_ambient_label: bool = False,
           source_notice: Path | None = None, stage_inputs=None, audio_repair: bool = False) -> dict:
    require(not os.path.samefile(stock, derived), "derived image aliases stock")
    # fsck checks all encoded data, even if no file content comparison reaches it.
    run([fsck, "--extract", stock])
    run([fsck, "--extract", derived])
    before = inventory(reader, stock)
    fstab_data = managed_fstab(reader, stock, before, fstab)
    policy, policy_report = managed_policy(reader, stock, before, policy_inputs)
    metadata_changes = managed_ambient_label(reader, stock, before, repair_ambient_label)
    data = descriptor_bytes(descriptor)
    stage_replacements, additions = resolve_stage_inputs(
        stage_inputs, reader, stock, before, data, fstab_data, policy, source_notice)
    require(not set(policy) & set(stage_replacements), "multiple image content providers")
    policy = policy | stage_replacements
    audio = managed_audio(reader, stock, before, audio_repair)
    require(not set(audio) & set(policy), "audio has multiple content providers")
    policy = policy | audio
    has_policy = bool(policy)
    metadata_changes = metadata_changes | added_parent_metadata(before, additions)
    notice = managed_notice(reader, stock, before, source_notice)
    if notice is not None:
        policy = policy | {NOTICE: notice}
    after = inventory(reader, derived)
    require(DESTINATION not in before, "stock already contains the destination")
    require(set(after) == set(before) | {DESTINATION} | set(additions), "image path inventory changed")
    changed_parents = {path.rpartition(b"/")[0] for path in additions} | {b"", b"etc"}
    for path, original in before.items():
        expected = metadata_changes.get(path, original)
        actual = after[path]
        # Directory encoding size can change when the parent/root is rewritten;
        # its entries, ownership, mode, xattrs, nlink and timestamp remain checked.
        fields = set(expected) - {"nid"}
        if path in changed_parents:
            fields.discard("size")
        if (path == FSTAB and fstab_data is not None) or path in policy:
            fields.discard("size")
        for field in fields:
            require(actual[field] == expected[field],
                    f"original metadata changed: {os.fsdecode(path)!r} {field}")
    require(hardlinks(before) == hardlinks({path: after[path] for path in before}),
            "original hardlink equivalence groups changed")
    require(after[DESTINATION]["nid"] not in {item["nid"] for path, item in after.items()
                                               if path != DESTINATION},
            "new descriptor aliases an original inode")
    for field, value in new_metadata(before[b"etc"], data).items():
        require(after[DESTINATION][field] == value, f"descriptor metadata differs: {field}")
    require(run([reader, "cat", derived, os.fsdecode(DESTINATION)]).stdout == data,
            "descriptor content differs from generated input")
    new_nids = {after[DESTINATION]["nid"]}
    old_nids = {after[path]["nid"] for path in before}
    for path, (expected, content) in additions.items():
        actual = after[path]
        require(actual["nid"] not in old_nids | new_nids, "new stage inode aliases another path")
        new_nids.add(actual["nid"])
        for field, value in expected.items():
            if field == "size" and stat.S_ISDIR(expected["mode"]):
                continue
            require(actual[field] == value, f"new stage metadata differs: {path!r} {field}")
        if content is not None:
            require(run([reader, "cat", derived, os.fsdecode(path)]).stdout == content,
                    "new stage content differs from selected build output")
    if fstab_data is not None:
        require(after[FSTAB]["size"] == len(fstab_data)
                and run([reader, "cat", derived, os.fsdecode(FSTAB)]).stdout == fstab_data,
                "derived fstab differs from the validated managed input")
    for path, expected in policy.items():
        require(after[path]["size"] == len(expected)
                and run([reader, "cat", derived, os.fsdecode(path)]).stdout == expected,
                "derived managed content differs from the proven complete contract")
    comparison = ("compare-data-managed-update" if fstab_data is not None else "compare-data-policy-update") \
        if has_policy else ("compare-data-fstab-update" if fstab_data is not None else "compare-data")
    if stage_inputs is None and not audio_repair:
        run([reader, comparison, stock, derived] + (["--notice"] if notice is not None else []))
    else:
        # Every updated path was checked above against its exact expected bytes. Compare all
        # remaining original file/symlink bytes, without a generic difference exemption list.
        for path, metadata in before.items():
            if path in policy or (path == FSTAB and fstab_data is not None):
                continue
            if stat.S_IFMT(metadata["mode"]) in {stat.S_IFREG, stat.S_IFLNK}:
                require(run([reader, "cat", stock, os.fsdecode(path)]).stdout
                        == run([reader, "cat", derived, os.fsdecode(path)]).stdout,
                        f"retained OEM content differs: {path!r}")
    old_super, new_super = superblock(reader, stock), superblock(reader, derived)
    for key in ("block_size", "uuid", "volume_hex", "feature_compat", "feature_incompat"):
        require(new_super[key] == old_super[key], f"filesystem property changed: {key}")
    require(new_super["blocks"] * new_super["block_size"] == derived.stat().st_size,
            "derived file has an unexpected tail (AVB must be a later explicit build step)")
    return {"original_paths": len(before),
            "new_paths": sorted(os.fsdecode(path) for path in {DESTINATION, *additions}),
            "modified_paths": ([os.fsdecode(FSTAB)] if fstab_data is not None else [])
                              + sorted(os.fsdecode(path) for path in policy),
            "modified_metadata_paths": sorted(os.fsdecode(path) for path in metadata_changes),
            "policy": policy_report,
            "original_hardlink_groups": sum(len(group) > 1 for group in hardlinks(before)),
            "derived_filesystem_bytes": derived.stat().st_size,
            "verification": "raw metadata, hardlink equivalence and complete file byte comparison"}


def tar_entry(path: bytes, metadata: dict) -> tarfile.TarInfo:
    entry = tarfile.TarInfo(os.fsdecode(path) if path else ".")
    types = {stat.S_IFDIR: tarfile.DIRTYPE, stat.S_IFREG: tarfile.REGTYPE,
             stat.S_IFLNK: tarfile.SYMTYPE, stat.S_IFCHR: tarfile.CHRTYPE,
             stat.S_IFBLK: tarfile.BLKTYPE, stat.S_IFIFO: tarfile.FIFOTYPE}
    kind = stat.S_IFMT(metadata["mode"])
    require(kind in types, f"unsupported inode type at {os.fsdecode(path)!r}")
    entry.type = types[kind]
    entry.mode = stat.S_IMODE(metadata["mode"])
    entry.uid, entry.gid = metadata["uid"], metadata["gid"]
    entry.mtime = metadata["mtime"]
    entry.pax_headers["mtime"] = f'{metadata["mtime"]}.{metadata["mtime_nsec"]:09d}'
    for key, value in metadata["xattrs"].items():
        require(quote_from_bytes(key, safe="").encode("ascii") == key,
                "xattr name needs URL decoding unsupported by fixed erofs-utils 1.8.3")
        entry.pax_headers["LIBARCHIVE.xattr." + quote_from_bytes(key, safe="")] = (
            base64.b64encode(value).decode("ascii"))
    if kind in {stat.S_IFCHR, stat.S_IFBLK}:
        # EROFS stores Linux new_encode_dev's 12-bit major / 20-bit minor.
        entry.devmajor = (metadata["rdev"] >> 8) & 0xfff
        entry.devminor = (metadata["rdev"] & 0xff) | ((metadata["rdev"] >> 12) & 0xfff00)
    return entry


def add_tar_entry(archive: tarfile.TarFile, path: bytes, metadata: dict,
                  data: bytes | None = None) -> None:
    entry = tar_entry(path, metadata)
    entry.size = len(data) if data is not None else 0
    archive.addfile(entry, io.BytesIO(data) if data is not None else None)


def write_source_tar(reader: Path, stock: Path, entries: dict[bytes, dict],
                     archive_path: Path, descriptor: bytes, fstab: bytes | None = None,
                     policy: dict[bytes, bytes] | None = None,
                     metadata_changes: dict[bytes, dict] | None = None,
                     additions: dict[bytes, tuple[dict, bytes | None]] | None = None) -> None:
    replacements = dict(policy or {})
    if fstab is not None:
        require(FSTAB not in replacements, "fstab has multiple content providers")
        replacements[FSTAB] = fstab
    additions = dict(additions or {})
    require(DESTINATION not in additions, "descriptor has multiple providers")
    additions[DESTINATION] = (new_metadata(entries[b"etc"], descriptor), descriptor)
    write_image_tar(reader, stock, entries, archive_path, replacements, metadata_changes, additions)


def write_image_tar(reader: Path, stock: Path, entries: dict[bytes, dict],
                    archive_path: Path, replacements: dict[bytes, bytes],
                    metadata_changes: dict[bytes, dict] | None = None,
                    additions: dict[bytes, tuple[dict, bytes | None]] | None = None) -> None:
    """Stream original inodes, with changes already established by each partition contract."""
    additions = additions or {}
    metadata_changes = metadata_changes or {}
    require(set(replacements) <= set(entries), "replacement has no original inode")
    require(set(metadata_changes) <= set(entries), "metadata change has no original inode")
    require(not set(additions) & set(entries), "added path already exists")
    for path in replacements:
        require(stat.S_ISREG(entries[path]["mode"]), "content replacement requires a regular inode")
    for group in hardlinks(entries):
        if set(group) & replacements.keys():
            require(set(group) <= replacements.keys()
                    and len({replacements[path] for path in group}) == 1,
                    "replacement must preserve complete original hardlink group")
    for path, (metadata, data) in additions.items():
        require(path and not path.startswith(b"/") and b"\0" not in path
                and all(part not in {b"", b".", b".."} for part in path.split(b"/")),
                "unsafe added image path")
        parent = path.rpartition(b"/")[0]
        parent_metadata = additions[parent][0] if parent in additions else entries.get(parent)
        require(parent_metadata is not None and stat.S_ISDIR(parent_metadata["mode"]),
                "added path parent is not a directory")
        require((stat.S_ISREG(metadata["mode"]) and isinstance(data, bytes)
                 and metadata["size"] == len(data))
                or (stat.S_ISDIR(metadata["mode"]) and data is None),
                "added inode must be a regular file or directory with matching content")
    inodes: dict[int, bytes] = {}
    with tarfile.open(archive_path, "w", format=tarfile.PAX_FORMAT) as archive:
        for path, original in sorted(entries.items()):
            metadata = metadata_changes.get(path, original)
            entry = tar_entry(path, metadata)
            kind = stat.S_IFMT(metadata["mode"])
            if kind != stat.S_IFDIR and metadata["nid"] in inodes:
                entry.type = tarfile.LNKTYPE
                entry.linkname = os.fsdecode(inodes[metadata["nid"]])
                # Hardlinks share the referenced inode metadata. Repeating PAX
                # xattrs here is unnecessary and can duplicate EAs in a tar reader.
                entry.pax_headers = {}
                archive.addfile(entry)
                continue
            if kind != stat.S_IFDIR:
                inodes[metadata["nid"]] = path
            if path in replacements:
                add_tar_entry(archive, path, metadata, replacements[path])
                continue
            if kind == stat.S_IFREG:
                entry.size = metadata["size"]
                command = [str(reader), "cat", str(stock), os.fsdecode(path)]
                with tempfile.TemporaryFile() as errors, subprocess.Popen(
                        command, stdout=subprocess.PIPE, stderr=errors,
                        env=environment()) as process:
                    try:
                        archive.addfile(entry, process.stdout)
                        require(not process.stdout.read(1), "file grew beyond recorded image size")
                    except BaseException:
                        process.kill()
                        raise
                    finally:
                        process.stdout.close()
                    if process.wait():
                        errors.seek(0)
                        raise subprocess.CalledProcessError(process.returncode, command,
                                                            stderr=errors.read())
            elif kind == stat.S_IFLNK:
                target = run([reader, "cat", stock, os.fsdecode(path)]).stdout
                require(len(target) == metadata["size"] and b"\0" not in target,
                        "invalid image symlink target")
                entry.linkname = os.fsdecode(target)
                archive.addfile(entry)
            else:
                archive.addfile(entry)
        for path, (metadata, data) in sorted(additions.items()):
            add_tar_entry(archive, path, metadata, data)


def managed_policy(reader: Path, stock: Path, entries: dict, inputs) -> tuple[dict, dict | None]:
    if inputs is None:
        return {}, None
    if __package__:
        from . import vendor_policy
    else:
        import vendor_policy
    return vendor_policy.generate(reader, stock, entries, inputs)


def derive(reader: Path, mkfs: Path, fsck: Path, stock: Path, descriptor: Path,
           output: Path, fstab: Path | None = None, policy_inputs=None, repair_ambient_label: bool = False,
           source_notice: Path | None = None, stage_inputs=None, audio_repair: bool = False) -> dict:
    require(stock.is_file(), "stock image is missing")
    require(not output.exists() and not output.is_symlink(), "output already exists")
    require(output.resolve() != stock.resolve() and output.resolve() != descriptor.resolve(),
            "output aliases an input")
    data = descriptor_bytes(descriptor)
    run([fsck, "--extract", stock])
    entries = inventory(reader, stock)
    fstab_data = managed_fstab(reader, stock, entries, fstab)
    policy, _ = managed_policy(reader, stock, entries, policy_inputs)
    metadata_changes = managed_ambient_label(reader, stock, entries, repair_ambient_label)
    stage_replacements, additions = resolve_stage_inputs(
        stage_inputs, reader, stock, entries, data, fstab_data, policy, source_notice)
    require(not set(policy) & set(stage_replacements), "multiple image content providers")
    policy = policy | stage_replacements
    audio = managed_audio(reader, stock, entries, audio_repair)
    require(not set(audio) & set(policy), "audio has multiple content providers")
    policy = policy | audio
    metadata_changes = metadata_changes | added_parent_metadata(entries, additions)
    notice = managed_notice(reader, stock, entries, source_notice)
    if notice is not None:
        policy = policy | {NOTICE: notice}
    require(DESTINATION not in entries, "stock already contains the destination")
    require(b"etc" in entries and stat.S_ISDIR(entries[b"etc"]["mode"]), "etc is not a directory")
    meta = superblock(reader, stock)
    filesystem_size = meta["block_size"] * meta["blocks"]
    require(0 < filesystem_size <= stock.stat().st_size, "invalid filesystem extent")
    require(output.parent.is_dir(), "output parent must already exist")
    data_size = sum(item["size"] for item in entries.values() if stat.S_ISREG(item["mode"]))
    require(shutil.disk_usage(output.parent).free > 2 * data_size + 128 * 1024 * 1024,
            "insufficient scratch space for independent image")
    with tempfile.TemporaryDirectory(prefix=".vendor-erofs-", dir=output.parent) as temporary:
        workspace = Path(temporary)
        archive = workspace / "source-with-descriptor.tar"
        write_source_tar(reader, stock, entries, archive, data, fstab_data, policy, metadata_changes,
                         additions)
        candidate = workspace / "vendor.erofs"
        volume = bytes.fromhex(meta["volume_hex"]).rstrip(b"\0")
        require(b"\0" not in volume, "noncanonical filesystem volume label")
        # Build a complete standalone filesystem. This neither imports blob-index
        # references nor carries the old AVB tree/footer into the new artifact.
        run([mkfs, "--clean=data", "--tar=f", "-zlz4hc", "--preserve-mtime", "--mkfs-time",
             f'-b{meta["block_size"]}', f'-T{meta["build_time"]}',
             f'-U{uuid.UUID(hex=meta["uuid"])}',
             "-L", os.fsdecode(volume), "--ovlfs-strip=0", "--workers=4", candidate, archive])
        report = verify(reader, fsck, stock, candidate, descriptor, fstab, policy_inputs,
                        repair_ambient_label, source_notice, stage_inputs, audio_repair)
        # link() is atomic and refuses an existing destination, including a race
        # with another builder. No existing path is replaced, even after failure.
        os.link(candidate, output)
        return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("derive", "verify", "seal", "verify-avb", "sync-avb-info",
                                           "export", "verify-target-files", "audit-stage",
                                           "export-prebuilt", "verify-prebuilt-target-files", "policy"))
    parser.add_argument("--reader", type=Path, required=True)
    parser.add_argument("--mkfs", type=Path)
    for name in ("fsck", "stock", "descriptor", "output", "fstab", "raw", "image-info",
                 "avbtool", "key", "public-key", "image", "target-files", "target-files-zip", "stage", "fec", "source-notice",
                 "stage-file-list", "stage-fs-config", "stage-target-out", "stage-selabel-lookup",
                 "stage-file-contexts"):
        parser.add_argument("--" + name, type=Path)
    parser.add_argument("--algorithm")
    parser.add_argument("--repair-ambient-label", action="store_true")
    parser.add_argument("--audio-repair", action="store_true")
    parser.add_argument("--build-variant", choices=("user", "userdebug"))
    parser.add_argument("--policy-input", action="append", default=[], metavar="NAME=PATH")
    parser.add_argument("--stage-source", action="append", default=[], metavar="IMAGE_PATH=BUILD_OUTPUT")
    parser.add_argument("--partition", choices=("odm", "system_dlkm", "vendor_dlkm"))
    args = parser.parse_args()
    try:
        if __package__:
            from . import vendor_policy
        else:
            import vendor_policy
        policy_inputs = vendor_policy.Inputs.parse(args.policy_input, args.build_variant)
        stage_config = None
        metadata_args = (args.stage_file_list, args.stage_fs_config, args.stage_target_out,
                         args.stage_selabel_lookup, args.stage_file_contexts)
        if any(value is not None for value in metadata_args) or args.stage_source:
            require(args.command in {"derive", "verify", "audit-stage"}
                    and args.stage is not None and all(value is not None for value in metadata_args),
                    "complete stage inputs are required for derive/verify/audit-stage")
            if __package__:
                from . import stage_inputs
            else:
                import stage_inputs
            sources = {}
            for specification in args.stage_source:
                name, separator, source = specification.partition("=")
                path = stage_inputs.image_path(os.fsencode(name))
                require(separator and source and path not in sources, "invalid/duplicate stage source")
                sources[path] = Path(source)
            metadata = stage_inputs.AndroidMetadata(args.stage_fs_config, args.stage_target_out,
                                                    args.stage_selabel_lookup, args.stage_file_contexts)
            stage_config = stage_inputs.Inputs(args.stage, args.stage_file_list, sources, metadata)
        elif args.stage is not None and args.command in {"derive", "verify"}:
            require(False, "stage requires its actual file list and metadata inputs")
        required = {
            "policy": ("stock", "output"),
            "derive": ("mkfs", "fsck", "stock", "descriptor", "output"),
            "verify": ("fsck", "stock", "descriptor", "output"),
            "seal": ("stock", "raw", "output", "image_info", "avbtool", "key", "public_key", "algorithm", "fec"),
            "verify-avb": ("stock", "raw", "image", "key", "public_key", "algorithm", "fec"),
            "sync-avb-info": ("image", "image_info", "key", "public_key", "fec"),
            "export": ("image", "target_files"),
            "verify-target-files": ("image", "key", "public_key", "fec"),
            "audit-stage": ("stock", "descriptor", "stage"),
            "export-prebuilt": ("partition", "fsck", "stock", "image", "stage", "target_files"),
            "verify-prebuilt-target-files": ("partition", "fsck", "stock", "image", "stage"),
        }
        require(all(getattr(args, name) is not None for name in required[args.command]),
                "missing required arguments for " + args.command)
        require(not args.audio_repair or args.command in {"derive", "verify", "audit-stage"},
                "audio repair is only valid for source derivation checks")
        require(args.partition is None or args.command in {"export-prebuilt", "verify-prebuilt-target-files"},
                "partition selection is only valid for unchanged prebuilt commands")
        require(policy_inputs is None or args.command in {
                    "policy", "derive", "verify", "audit-stage", "verify-target-files"},
                "policy inputs are not valid for this command")
        require(policy_inputs is None or args.command != "verify-target-files" or args.stock is not None,
                "policy target-files verification requires the original stock image")
        require(not args.repair_ambient_label or args.command in {"derive", "verify", "audit-stage"},
                "ambient repair selection is not valid for this command")
        require(args.source_notice is None or args.command in {"derive", "verify", "audit-stage"},
                "source NOTICE is not valid for this command")
        report = {"command": args.command, "verification": "passed"}
        if args.command == "policy":
            require(policy_inputs is not None, "policy command requires the complete policy inputs")
            report = vendor_policy.publish(args.reader, args.stock, policy_inputs, args.output)
        elif args.command in {"derive", "verify"}:
            if args.command == "derive":
                report = derive(args.reader, args.mkfs, args.fsck, args.stock, args.descriptor,
                                args.output, args.fstab, policy_inputs, args.repair_ambient_label,
                                args.source_notice, stage_config, args.audio_repair)
            else:
                report = verify(args.reader, args.fsck, args.stock, args.output, args.descriptor,
                                args.fstab, policy_inputs, args.repair_ambient_label,
                                args.source_notice, stage_config, args.audio_repair)
        elif args.command in {"seal", "verify-avb", "sync-avb-info"}:
            if __package__:
                from . import vendor_avb
            else:
                import vendor_avb
            if args.command == "sync-avb-info":
                vendor_avb.sync_info(args.image, args.image_info, args.key, args.public_key, args.fec)
            elif args.command == "seal":
                report = vendor_avb.seal(args.reader, args.stock, args.raw, args.output,
                                         args.image_info, args.avbtool, args.key, args.public_key, args.algorithm, args.fec)
            else:
                report = vendor_avb.verify(args.reader, args.stock, args.raw, args.image, args.key,
                                           args.public_key, args.algorithm, args.fec)
        else:
            if __package__:
                from . import vendor_target_files
            else:
                import vendor_target_files
            if args.command in {"export-prebuilt", "verify-prebuilt-target-files"}:
                vendor_target_files.verify_prebuilt_inputs(args.fsck, args.stock, args.image, args.partition)
                vendor_target_files.audit_prebuilt_stage(args.reader, args.stock, args.stage, args.partition)
                if args.command == "export-prebuilt":
                    require(args.target_files_zip is None, "export requires a directory, not a ZIP")
                    vendor_target_files.export(args.reader, args.stock, args.target_files, args.partition)
                else:
                    require(bool(args.target_files) != bool(args.target_files_zip),
                            "select exactly one target-files directory or ZIP")
                    if args.target_files:
                        vendor_target_files.verify_directory(args.reader, args.stock, args.target_files,
                                                             partition=args.partition)
                    else:
                        vendor_target_files.verify_zip(args.reader, args.stock, args.target_files_zip,
                                                       partition=args.partition)
            elif args.command == "export":
                vendor_target_files.export(args.reader, args.image, args.target_files)
            elif args.command == "audit-stage":
                managed_audio(args.reader, args.stock, inventory(args.reader, args.stock), args.audio_repair)
                managed_ambient_label(args.reader, args.stock, inventory(args.reader, args.stock),
                                      args.repair_ambient_label)
                vendor_target_files.audit_stage(args.reader, args.stock, args.stage,
                                                args.descriptor, args.fstab, policy_inputs,
                                                args.source_notice, stage_config)
            else:
                require(bool(args.target_files) != bool(args.target_files_zip),
                        "select exactly one target-files directory or ZIP")
                if args.target_files:
                    vendor_target_files.verify_directory(args.reader, args.image, args.target_files,
                                                         key=args.key, public_key=args.public_key, fec=args.fec)
                else:
                    vendor_target_files.verify_zip(args.reader, args.image, args.target_files_zip,
                                                    args.key, args.public_key, args.fec)
                if policy_inputs is not None:
                    vendor_policy.verify_target_files(args.reader, args.stock, args.image, policy_inputs,
                                                       args.target_files, args.target_files_zip)
        print(json.dumps(report, sort_keys=True))
    except (ValueError, OSError, EOFError, KeyError, subprocess.CalledProcessError) as error:
        if isinstance(error, subprocess.CalledProcessError):
            message = error.stderr.decode("utf-8", "replace").strip()
            parser.exit(1, f"{error.cmd[0]} failed ({error.returncode}): {message}\n")
        parser.exit(1, f"{error}\n")


if __name__ == "__main__":
    main()
