# SPDX-License-Identifier: MIT
"""Resolve the product file list against exact build outputs and Android metadata."""
from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import stat
import struct
import subprocess


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def image_path(value: bytes) -> bytes:
    require(value and not value.startswith(b"/") and len(value) < 1000
            and all(32 < byte < 127 for byte in value)
            and all(part not in {b"", b".", b".."} for part in value.split(b"/")),
            "unsafe product file-list path")
    return value


def selected_paths(stage: Path, file_list: Path) -> dict[bytes, Path]:
    require(stage.is_dir() and not stage.is_symlink(), "stage must be a real directory")
    data = file_list.read_bytes()
    require(data.endswith(b"\n"), "product file list must end with a newline")
    names = [image_path(line) for line in data.splitlines()]
    require(len(names) == len(set(names)), "duplicate product file-list path")
    closure = {b"", *names}
    for name in names:
        parent = name.rpartition(b"/")[0]
        while parent:
            closure.add(parent)
            parent = parent.rpartition(b"/")[0]
    found = {b"": stage}
    for directory, directories, files in os.walk(stage, followlinks=False):
        for name in directories + files:
            path = Path(directory) / name
            found[os.fsencode(path.relative_to(stage))] = path
    require(set(found) == closure,
            "stage differs from product file list and parent closure: missing="
            + repr(sorted(closure - set(found))) + " extra=" + repr(sorted(set(found) - closure)))
    for name in closure - {b""}:
        parent = name.rpartition(b"/")[0]
        require(stat.S_ISDIR(found[parent].lstat().st_mode),
                "product path traverses a non-directory or symlink parent")
    return found


@dataclass(frozen=True)
class AndroidMetadata:
    fs_config: Path
    target_out: Path
    selabel_lookup: Path
    file_contexts: Path
    partition: str = "vendor"

    def __post_init__(self) -> None:
        require(self.partition in {"vendor", "odm"}, "unsupported stage metadata partition")

    def for_paths(self, kinds: dict[bytes, int], timestamp: dict) -> dict[bytes, dict]:
        if not kinds:
            return {}
        ordered = sorted(kinds)
        prefix = self.partition.encode("ascii") + b"/"
        names = {prefix + image_path(path): path for path in ordered}
        input_data = b"".join(prefix + path
                              + (b"/" if kinds[path] == stat.S_IFDIR else b"") + b"\n"
                              for path in ordered)
        result = subprocess.run([str(self.fs_config), "-C", "-D", str(self.target_out),
                                 "-R", self.partition + "/"],
                                input=input_data, capture_output=True, check=True)
        configs = {}
        for line in result.stdout.splitlines():
            fields = line.split()
            require(len(fields) == 5 and fields[0] in names
                    and fields[0] not in configs and fields[4].startswith(b"capabilities=0x"),
                    "unexpected Android fs_config result")
            uid, gid, mode = int(fields[1]), int(fields[2]), int(fields[3], 8)
            capability = int(fields[4].split(b"=", 1)[1], 16)
            require(0 <= uid <= 0xffffffff and 0 <= gid <= 0xffffffff
                    and 0 <= mode <= 0o7777 and 0 <= capability < (1 << 64),
                    "Android fs_config value is out of range")
            configs[fields[0]] = (uid, gid, mode, capability)
        require(set(configs) == set(names), "Android fs_config omitted a selected path")
        metadata = {}
        for full_name, path in names.items():
            uid, gid, mode, capability = configs[full_name]
            kind = kinds[path]
            require(kind in {stat.S_IFDIR, stat.S_IFREG},
                    "new stage inode type needs a dedicated contract")
            label_result = subprocess.run(
                [str(self.selabel_lookup), "-r", "-b", "file", "-f", str(self.file_contexts),
                 "-k", "/" + os.fsdecode(full_name), "-t", str(kind | mode)],
                capture_output=True, check=True)
            prefix = b"Default context: "
            output = label_result.stdout
            require(output.startswith(prefix) and output.endswith(b"\n")
                    and output.count(b"\n") == 1, "unexpected selabel_lookup result")
            label = output[len(prefix):-1]
            require(label and all(32 < byte < 127 for byte in label), "invalid SELinux label")
            # The pinned EROFS writer stores strlen(secontext), without the C terminator.
            xattrs = {b"security.selinux": label}
            if capability:
                xattrs[b"security.capability"] = struct.pack(
                    "<5I", 0x02000001, capability & 0xffffffff, 0, capability >> 32, 0)
            metadata[path] = {"mode": kind | mode, "uid": uid, "gid": gid, "size": 0,
                              "mtime": timestamp["mtime"], "mtime_nsec": timestamp["mtime_nsec"],
                              "nlink": 2 if kind == stat.S_IFDIR else 1, "rdev": 0,
                              "xattrs": xattrs}
        return metadata


@dataclass
class Resolution:
    replacements: dict[bytes, bytes]
    additions: dict[bytes, tuple[dict, bytes | None]]


@dataclass(frozen=True)
class Inputs:
    stage: Path
    file_list: Path
    # Exact reviewed module/generated outputs, never directory or suffix exemptions.
    sources: dict[bytes, Path]
    metadata: AndroidMetadata

    def resolve(self, original: dict[bytes, dict], read_original,
                managed_stage: dict[bytes, bytes]) -> Resolution:
        found = selected_paths(self.stage, self.file_list)
        require(set(self.sources) <= set(found), "selected source has no product stage path")
        require(not set(self.sources) & set(managed_stage), "multiple providers for managed path")
        require(set(managed_stage) <= set(found), "managed provider missing from product file list")
        replacements = {}
        new_contents = {}
        new_kinds = {}
        source_data = {}
        for name, path in sorted(found.items()):
            kind = stat.S_IFMT(path.lstat().st_mode)
            old = original.get(name)
            require(old is None or kind == stat.S_IFMT(old["mode"]), "stage inode type conflict")
            if kind == stat.S_IFDIR:
                require(name not in self.sources, "source output cannot replace a directory")
                if old is None:
                    new_kinds[name] = kind
                    new_contents[name] = None
                continue
            require(kind in {stat.S_IFREG, stat.S_IFLNK}, "unsupported stage inode type")
            actual = path.read_bytes() if kind == stat.S_IFREG else os.fsencode(os.readlink(path))
            if name in managed_stage:
                require(kind == stat.S_IFREG and actual == managed_stage[name],
                        "managed stage provider differs from its validated input")
                continue
            if name in self.sources:
                source = self.sources[name]
                require(kind == stat.S_IFREG and source.is_file() and not source.is_symlink()
                        and not source.resolve().is_relative_to(self.stage.resolve()),
                        "stage source must be an external regular build output")
                expected = source.read_bytes()
                require(actual == expected, "stage differs from selected build output")
                source_data[name] = expected
                if old is None:
                    new_kinds[name] = kind
                    new_contents[name] = expected
                elif expected != read_original(name):
                    replacements[name] = expected
            else:
                require(old is not None, "new stage path lacks a reviewed build output: " + os.fsdecode(name))
                require(actual == read_original(name), "unreviewed stage content differs from OEM: " + os.fsdecode(name))
        groups = {}
        for path, item in original.items():
            if not stat.S_ISDIR(item["mode"]):
                groups.setdefault(item["nid"], set()).add(path)
        for group in groups.values():
            if group & replacements.keys():
                require(group <= replacements.keys()
                        and len({replacements[path] for path in group}) == 1,
                        "replacement must preserve the entire original hardlink group")
        new_meta = self.metadata.for_paths(new_kinds, original[b""])
        additions = {}
        for name, data in new_contents.items():
            meta = new_meta[name]
            meta["size"] = 0 if data is None else len(data)
            if data is None:
                meta["nlink"] += sum(kind == stat.S_IFDIR and path.rpartition(b"/")[0] == name
                                     for path, kind in new_kinds.items())
            additions[name] = (meta, data)
        # Catch ordinary concurrent source/stage edits before publishing the resolved input.
        require(selected_paths(self.stage, self.file_list).keys() == found.keys(),
                "stage changed during input resolution")
        for name, expected in source_data.items():
            require(self.sources[name].read_bytes() == expected and found[name].read_bytes() == expected,
                    "selected input changed during stage resolution")
        return Resolution(replacements, additions)
