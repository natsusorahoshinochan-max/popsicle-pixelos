# SPDX-License-Identifier: MIT
"""Export/verify exact target-files views of managed vendor and raw OEM images.

ZIP has no owner/xattr/hardlink representation. Its fs_config and raw metadata
record are checked alongside the bytes, instead of treating host xattrs as proof.
"""
from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import tempfile
import zipfile

if __package__:
    from . import derive_vendor as image
else:
    import derive_vendor as image

CONFIG = "META/vendor_filesystem_config.txt"
METADATA = "META/vendor_erofs_metadata.json"
PREBUILT_PARTITIONS = ("odm", "system_dlkm", "vendor_dlkm")


def partition_paths(partition: str) -> tuple[str, str, str]:
    image.require(partition in ("vendor", *PREBUILT_PARTITIONS), "unsupported EROFS partition")
    return (partition.upper(), f"META/{partition}_filesystem_config.txt",
            f"META/{partition}_erofs_metadata.json")


def metadata_bytes(entries: dict[bytes, dict], partition: str = "vendor") -> bytes:
    partition_paths(partition)
    records = []
    for path, values in sorted(entries.items()):
        record = dict(values)
        record["path_hex"] = path.hex()
        record["xattrs"] = [[key.hex(), value.hex()] for key, value in sorted(values["xattrs"].items())]
        records.append(record)
    return (json.dumps({"format": 1, "partition": partition, "entries": records},
                       sort_keys=True, separators=(",", ":")) + "\n").encode()


def config_bytes(entries: dict[bytes, dict], partition: str = "vendor") -> bytes:
    partition_paths(partition)
    lines = []
    for path, item in sorted(entries.items()):
        image.require(not any(byte <= 32 or byte >= 127 for byte in path),
                      "image path cannot be represented by Android fs_config")
        capability = item["xattrs"].get(b"security.capability")
        mask = 0
        if capability is not None:
            image.require(len(capability) == 20, "unsupported VFS capability revision")
            magic, low, inherit_low, high, inherit_high = struct.unpack("<5I", capability)
            mask = low | (high << 32)
            image.require(magic == 0x02000001 and not inherit_low and not inherit_high and mask,
                          "capability cannot be represented exactly by Android fs_config")
        name = partition.encode("ascii") + (b"/" + path if path else b"")
        lines.append(name + f' {item["uid"]} {item["gid"]} {stat.S_IMODE(item["mode"]):o}'
                     f' capabilities=0x{mask:x}\n'.encode())
    return b"".join(lines)


def logical_paths(root: Path) -> dict[bytes, Path]:
    found = {b"": root}
    for directory, directories, files in os.walk(root, followlinks=False):
        for name in directories + files:
            path = Path(directory) / name
            found[os.fsencode(path.relative_to(root))] = path
    return found


def supported_view(entries: dict[bytes, dict]) -> None:
    for path, item in entries.items():
        image.require(stat.S_IFMT(item["mode"]) in {stat.S_IFREG, stat.S_IFDIR, stat.S_IFLNK},
                      f"target-files ZIP cannot encode special inode {os.fsdecode(path)!r}")


def write_file(reader: Path, source_image: Path, source_path: bytes, output: Path, size: int) -> None:
    command = [str(reader), "cat", str(source_image), os.fsdecode(source_path)]
    with output.open("xb") as destination, tempfile.TemporaryFile() as errors:
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=errors,
                              env=image.environment()) as process:
            try:
                shutil.copyfileobj(process.stdout, destination, 1024 * 1024)
            except BaseException:
                process.kill()
                raise
            finally:
                process.stdout.close()
            if process.wait():
                errors.seek(0)
                raise subprocess.CalledProcessError(process.returncode, command, stderr=errors.read())
        image.require(destination.tell() == size, "image file size changed while exporting")


def export(reader: Path, source_image: Path, target_files: Path, partition: str = "vendor") -> None:
    directory, config_path, metadata_path = partition_paths(partition)
    entries = image.inventory(reader, source_image)
    supported_view(entries)
    config, metadata = config_bytes(entries, partition), metadata_bytes(entries, partition)
    root = target_files / directory
    image.require(target_files.is_dir() and (target_files / "META").is_dir(),
                  "target_files and META must already exist")
    for path in (root, target_files / config_path, target_files / metadata_path):
        image.require(not path.exists() and not path.is_symlink(), "partition export output already exists")
    inodes: dict[int, Path] = {}
    directories = []
    for name, item in sorted(entries.items()):
        path = root / os.fsdecode(name)
        kind = stat.S_IFMT(item["mode"])
        if kind == stat.S_IFDIR:
            path.mkdir(mode=0o700)
            directories.append((path, item))
            continue
        if item["nid"] in inodes:
            os.link(inodes[item["nid"]], path, follow_symlinks=False)
            continue
        inodes[item["nid"]] = path
        if kind == stat.S_IFREG:
            write_file(reader, source_image, name, path, item["size"])
            path.chmod(stat.S_IMODE(item["mode"]))
        else:
            target = image.run([reader, "cat", source_image, os.fsdecode(name)]).stdout
            os.symlink(os.fsdecode(target), path)
        mtime = item["mtime"] * 1_000_000_000 + item["mtime_nsec"]
        os.utime(path, ns=(mtime, mtime), follow_symlinks=False)
    for path, item in reversed(directories):
        path.chmod(stat.S_IMODE(item["mode"]))
        mtime = item["mtime"] * 1_000_000_000 + item["mtime_nsec"]
        os.utime(path, ns=(mtime, mtime))
    with (target_files / config_path).open("xb") as output:
        output.write(config)
    with (target_files / metadata_path).open("xb") as output:
        output.write(metadata)
    verify_directory(reader, source_image, target_files, require_image=False, partition=partition)


def compare_stream_to_image(reader: Path, source_image: Path, name: bytes, stream, size: int) -> None:
    command = [str(reader), "cat", str(source_image), os.fsdecode(name)]
    with tempfile.TemporaryFile() as errors, subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=errors, env=image.environment()) as process:
        try:
            remaining = size
            while remaining:
                count = min(remaining, 1024 * 1024)
                expected = process.stdout.read(count)
                actual = stream.read(count)
                image.require(len(expected) == count and expected == actual,
                              f"target-files content differs: {os.fsdecode(name)!r}")
                remaining -= count
            image.require(not process.stdout.read(1) and not stream.read(1), "unexpected file tail")
        except BaseException:
            process.kill()
            raise
        finally:
            process.stdout.close()
        if process.wait():
            errors.seek(0)
            raise subprocess.CalledProcessError(process.returncode, command, stderr=errors.read())


def compare_files(first: Path, second: Path) -> None:
    image.require(first.stat().st_size == second.stat().st_size, "target-files image size differs")
    with first.open("rb") as a, second.open("rb") as b:
        while block := a.read(1024 * 1024):
            image.require(block == b.read(len(block)), "target-files image bytes differ")


def verify_prebuilt_inputs(fsck: Path, stock: Path, installed: Path, partition: str) -> None:
    image.require(partition in PREBUILT_PARTITIONS, "unsupported unchanged prebuilt partition")
    image.require(stock.name == installed.name == partition + ".img",
                  "prebuilt image filename does not match partition")
    image.require(stock.is_file() and installed.is_file(), "prebuilt image is missing")
    compare_files(stock, installed)
    # fsck validates the filesystem without extracting to a host tree. The
    # complete byte comparison above includes all original AVB/footer/padding.
    image.run([fsck, "--extract", stock])


def audit_prebuilt_stage(reader: Path, stock: Path, stage: Path, partition: str) -> None:
    image.require(partition in PREBUILT_PARTITIONS, "unsupported unchanged prebuilt partition")
    if not stage.exists() and not stage.is_symlink():
        return
    image.require(stage.is_dir() and not stage.is_symlink(), "prebuilt stage must be a real directory")
    entries = image.inventory(reader, stock)
    problems = []
    for name, path in logical_paths(stage).items():
        if name not in entries:
            problems.append(f"{os.fsdecode(name)}: unapproved new path")
            continue
        expected = entries[name]
        kind = stat.S_IFMT(path.lstat().st_mode)
        if kind != stat.S_IFMT(expected["mode"]):
            problems.append(f"{os.fsdecode(name)}: inode type differs")
        elif kind == stat.S_IFLNK:
            target = image.run([reader, "cat", stock, os.fsdecode(name)]).stdout
            if os.fsencode(os.readlink(path)) != target:
                problems.append(f"{os.fsdecode(name)}: symlink target differs")
        elif kind == stat.S_IFREG:
            try:
                with path.open("rb") as stream:
                    compare_stream_to_image(reader, stock, name, stream, expected["size"])
            except ValueError:
                problems.append(f"{os.fsdecode(name)}: content differs")
    image.require(not problems, f"unapproved {partition} stage differences:\n" + "\n".join(problems))


def verify_directory(reader: Path, source_image: Path, target_files: Path,
                     require_image: bool = True, key: Path | None = None,
                     public_key: Path | None = None, fec: Path | None = None,
                     partition: str = "vendor") -> None:
    directory, config_path, metadata_path = partition_paths(partition)
    entries = image.inventory(reader, source_image)
    supported_view(entries)
    if require_image:
        compare_files(source_image, target_files / f"IMAGES/{partition}.img")
    if require_image and partition == "vendor":
        image.require(key is not None and public_key is not None and fec is not None,
                      "expected vendor key inputs and FEC tool are required")
        if __package__:
            from . import vendor_avb
        else:
            import vendor_avb
        vendor_avb.verify_info(source_image, (target_files / "META/misc_info.txt").read_bytes(), key, public_key, fec)
    image.require((target_files / config_path).read_bytes() == config_bytes(entries, partition), "partition fs_config differs")
    image.require((target_files / metadata_path).read_bytes() == metadata_bytes(entries, partition), "partition raw metadata differs")
    found = logical_paths(target_files / directory)
    image.require(set(found) == set(entries), "partition directory path inventory differs")
    groups = {}
    for name, item in entries.items():
        path = found[name]
        actual = path.lstat()
        kind = stat.S_IFMT(item["mode"])
        image.require(stat.S_IFMT(actual.st_mode) == kind, "partition inode type differs")
        if kind != stat.S_IFLNK:
            image.require(stat.S_IMODE(actual.st_mode) == stat.S_IMODE(item["mode"]), "partition mode differs")
        image.require(actual.st_mtime_ns == item["mtime"] * 1_000_000_000 + item["mtime_nsec"],
                      "partition timestamp differs")
        if kind == stat.S_IFDIR:
            continue
        groups[name] = {"nid": (actual.st_dev, actual.st_ino), "mode": actual.st_mode}
        if kind == stat.S_IFLNK:
            expected = image.run([reader, "cat", source_image, os.fsdecode(name)]).stdout
            image.require(os.fsencode(os.readlink(path)) == expected, "partition symlink target differs")
        else:
            with path.open("rb") as stream:
                compare_stream_to_image(reader, source_image, name, stream, item["size"])
    image.require(image.hardlinks(groups) == image.hardlinks(entries), "partition hardlink groups differ")


def verify_zip(reader: Path, source_image: Path, archive_path: Path,
               key: Path | None = None, public_key: Path | None = None, fec: Path | None = None,
               partition: str = "vendor") -> None:
    directory, config_path, metadata_path = partition_paths(partition)
    prefix = directory + "/"
    image_path = f"IMAGES/{partition}.img"
    entries = image.inventory(reader, source_image)
    supported_view(entries)
    with zipfile.ZipFile(archive_path) as archive:
        if partition == "vendor":
            image.require(key is not None and public_key is not None and fec is not None,
                          "expected vendor key inputs and FEC tool are required")
            if __package__:
                from . import vendor_avb
            else:
                import vendor_avb
            vendor_avb.verify_info(source_image, archive.read("META/misc_info.txt"), key, public_key, fec)
        names = archive.namelist()
        image.require(len(names) == len(set(names)), "duplicate ZIP entry")
        image.require(archive.read(config_path) == config_bytes(entries, partition), "ZIP partition fs_config differs")
        image.require(archive.read(metadata_path) == metadata_bytes(entries, partition), "ZIP partition raw metadata differs")
        with archive.open(image_path) as packed, source_image.open("rb") as source:
            image.require(archive.getinfo(image_path).file_size == source_image.stat().st_size,
                          "ZIP partition image size differs")
            while block := source.read(1024 * 1024):
                image.require(packed.read(len(block)) == block, "ZIP partition image bytes differ")
        expected_files = {prefix.encode("ascii") + path for path, item in entries.items()
                          if not stat.S_ISDIR(item["mode"])}
        actual_files = {os.fsencode(name) for name in names
                        if name.startswith(prefix) and not name.endswith("/")}
        image.require(actual_files == expected_files, "ZIP partition file inventory differs")
        expected_directories = {prefix.encode("ascii") + (path + b"/" if path else b"")
                                for path, item in entries.items() if stat.S_ISDIR(item["mode"])}
        actual_directories = {os.fsencode(name) for name in names
                              if name.startswith(prefix) and name.endswith("/")}
        image.require(actual_directories == expected_directories, "ZIP partition directory inventory differs")
        for name in actual_directories:
            mode = archive.getinfo(os.fsdecode(name)).external_attr >> 16
            image.require(stat.S_ISDIR(mode) and stat.S_IMODE(mode) == 0o755,
                          "ZIP partition directory transport mode differs")
        for path, item in entries.items():
            kind = stat.S_IFMT(item["mode"])
            if kind == stat.S_IFDIR:
                continue
            name = prefix + os.fsdecode(path)
            entry = archive.getinfo(name)
            mode = entry.external_attr >> 16
            # Fixed soong_zip deliberately normalizes regular modes to 0644/0755;
            # actual Android modes remain exact in fs_config and raw metadata.
            transport_mode = 0o777 if kind == stat.S_IFLNK else (
                0o755 if item["mode"] & 0o100 else 0o644)
            image.require(stat.S_IFMT(mode) == kind and stat.S_IMODE(mode) == transport_mode,
                          "ZIP partition mode/type differs")
            with archive.open(entry) as stream:
                compare_stream_to_image(reader, source_image, path, stream, item["size"])


def audit_stage(reader: Path, stock: Path, stage: Path, descriptor: Path,
                fstab: Path | None = None, policy_inputs=None,
                source_notice: Path | None = None, stage_inputs=None) -> None:
    entries = image.inventory(reader, stock)
    fstab_data = image.managed_fstab(reader, stock, entries, fstab)
    policy, _ = image.managed_policy(reader, stock, entries, policy_inputs)
    notice = image.managed_notice(reader, stock, entries, source_notice)
    if stage_inputs is not None:
        image.require(stage_inputs.stage.resolve() == stage.resolve(), "different stage inputs")
        image.resolve_stage_inputs(stage_inputs, reader, stock, entries,
                                   image.descriptor_bytes(descriptor), fstab_data, policy,
                                   source_notice)
        return
    problems = []
    found = logical_paths(stage)
    image.require(image.DESTINATION in found, "generated descriptor is missing from vendor stage")
    image.require(notice is None or image.NOTICE in found, "source NOTICE is missing from stage")
    image.require(set(policy) <= set(found), "managed policy provider is missing from vendor stage")
    for name, path in found.items():
        actual = path.lstat()
        if name == image.NOTICE and notice is not None:
            if not stat.S_ISREG(actual.st_mode) or path.read_bytes() != source_notice.read_bytes():
                problems.append("source NOTICE provider mismatch")
            continue
        if name in policy:
            if not stat.S_ISREG(actual.st_mode) or path.read_bytes() != policy[name]:
                problems.append(f"{os.fsdecode(name)}: managed policy provider mismatch")
            continue
        if name == image.DESTINATION:
            if not stat.S_ISREG(actual.st_mode) or path.read_bytes() != descriptor.read_bytes():
                problems.append(f"{os.fsdecode(name)}: descriptor mismatch")
            continue
        if name == image.FSTAB and fstab_data is not None:
            if not stat.S_ISREG(actual.st_mode) or path.read_bytes() != fstab_data:
                problems.append(f"{os.fsdecode(name)}: managed fstab mismatch")
            continue
        if name not in entries:
            problems.append(f"{os.fsdecode(name)}: unapproved new path")
            continue
        expected = entries[name]
        kind = stat.S_IFMT(actual.st_mode)
        if kind != stat.S_IFMT(expected["mode"]):
            problems.append(f"{os.fsdecode(name)}: inode type differs")
        elif kind == stat.S_IFLNK:
            target = image.run([reader, "cat", stock, os.fsdecode(name)]).stdout
            if os.fsencode(os.readlink(path)) != target:
                problems.append(f"{os.fsdecode(name)}: symlink target differs")
        elif kind == stat.S_IFREG:
            try:
                with path.open("rb") as stream:
                    compare_stream_to_image(reader, stock, name, stream, expected["size"])
            except ValueError:
                problems.append(f"{os.fsdecode(name)}: content differs")
    image.require(not problems, "unapproved vendor stage differences:\n" + "\n".join(problems))
