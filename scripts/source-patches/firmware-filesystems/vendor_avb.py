# SPDX-License-Identifier: MIT
"""Seal the verified filesystem using current signing inputs and OEM vendor properties."""
from __future__ import annotations

import contextlib
import io
import os
from pathlib import Path
import shlex
import shutil
import struct
import tempfile

import avbtool
import build_image
import verity_utils

if __package__:
    from . import derive_vendor as image
else:
    import derive_vendor as image

COHORT = {
    "com.android.build.vendor.os_version": b"ro.vendor.build.version.release",
    "com.android.build.vendor.fingerprint": b"ro.vendor.build.fingerprint",
    "com.android.build.vendor.security_patch": b"ro.vendor.build.security_patch",
}
ODM_COHORT = {
    "com.android.build.odm.os_version": b"ro.odm.build.version.release",
    "com.android.build.odm.fingerprint": b"ro.odm.build.fingerprint",
}


def require_partition_contract(partition: str, cohort: dict[str, bytes]) -> None:
    # These two retained firmware cohorts have distinct, fixed property sets.
    # In particular, the OEM ODM has no security-patch property to invent.
    expected = {"vendor": COHORT, "odm": ODM_COHORT}
    image.require(partition in expected and cohort == expected[partition],
                  "unsupported partition/cohort contract")



def target_files_properties(sealed: Path, *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> dict[str, str]:
    require_partition_contract(partition, cohort)
    _, header, tree, props, size = parse(sealed, partition=partition, cohort=cohort)
    arguments = ["--hash_algorithm", tree.hash_algorithm, "--block_size", str(tree.data_block_size),
                 "--fec_num_roots", str(tree.fec_num_roots),
                 "--rollback_index", str(header.rollback_index),
                 "--rollback_index_location", str(header.rollback_index_location)]
    for key, value in sorted(props.items()):
        arguments += ["--prop", key + ":" + value.decode()]
    return {f"avb_{partition}_add_hashtree_footer_args": shlex.join(arguments),
            f"avb_{partition}_salt": tree.salt.hex(), f"{partition}_size": str(size),
            f"avb_{partition}_algorithm": avbtool.lookup_algorithm_by_type(header.algorithm_type)[0]}


def parse_info(data: bytes) -> dict[str, str]:
    result = {}
    for line in data.decode().splitlines():
        if line and not line.startswith("#"):
            name, value = line.split("=", 1)
            image.require(name not in result, "duplicate target-files image property")
            result[name] = value
    return result


def verify_info(sealed: Path, data: bytes, key: Path, public_key: Path, fec: Path,
                *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> None:
    require_partition_contract(partition, cohort)
    values = parse_info(data)
    image.require(values.get("avb_enable") == "true"
                  and values.get(f"avb_{partition}_hashtree_enable") == "true"
                  and values.get(f"{partition}_fs_type") == "erofs"
                  and bool(values.get(f"avb_{partition}_key_path")), "target-files vendor AVB setup differs")
    image.require(os.path.samefile(values[f"avb_{partition}_key_path"], key),
                  "target-files vendor signing key path differs")
    verify_signature(sealed, key, public_key, partition=partition, cohort=cohort)
    verify_fec(sealed, fec, partition=partition, cohort=cohort)
    for name, value in target_files_properties(sealed, partition=partition, cohort=cohort).items():
        image.require(values.get(name) == value, f"target-files vendor AVB property differs: {name}")


def sync_info(sealed: Path, path: Path, key: Path, public_key: Path, fec: Path,
              *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> None:
    require_partition_contract(partition, cohort)
    image.require(path.is_file() and not path.is_symlink() and not os.path.samefile(path, sealed),
                  "misc_info must be a separate existing regular file")
    source = path.read_bytes()
    existing = parse_info(source)
    updates = target_files_properties(sealed, partition=partition, cohort=cohort)
    # Standard Board AVB_VENDOR_KEY_PATH would request a top-level chain
    # descriptor. The managed independent key enters only this vendor's build/TF
    # properties. Refuse an existing different path instead of silently fixing it.
    if f"avb_{partition}_key_path" in existing:
        image.require(os.path.samefile(existing[f"avb_{partition}_key_path"], key),
                      "target-files vendor signing key path differs")
    updates[f"avb_{partition}_key_path"] = str(key)
    # Only this partition's image-derived AVB properties change. The remaining
    # global/partition build metadata stays byte-for-byte in its original lines.
    lines = [line for line in source.decode().splitlines(keepends=True)
             if line.split("=", 1)[0] not in updates]
    if lines and not lines[-1].endswith("\n"):
        lines[-1] += "\n"
    contents = "".join(lines) + "".join(key + "=" + value + "\n" for key, value in updates.items())
    verify_info(sealed, contents.encode(), key, public_key, fec, partition=partition, cohort=cohort)
    with tempfile.NamedTemporaryFile(prefix=f".{partition}-misc-", dir=path.parent, delete=False) as output:
        candidate = Path(output.name)
        try:
            output.write(contents.encode())
            output.close()
            candidate.chmod(path.stat().st_mode & 0o777)
            os.replace(candidate, path)
        finally:
            candidate.unlink(missing_ok=True)


def parse(path: Path, *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT):
    require_partition_contract(partition, cohort)
    handle = avbtool.ImageHandler(str(path), read_only=True)
    try:
        image.require(not handle.is_sparse, "vendor AVB input must be a raw image")
        footer, header, descriptors, size = avbtool.Avb()._parse_image(handle)
        image.require(footer is not None and footer.original_image_size > 0,
                      "vendor AVB footer is missing")
        image.require(header.flags == 0, "AVB verification/hashtree flags must remain enabled")
        image.require(footer.original_image_size <= footer.vbmeta_offset
                      and footer.vbmeta_size >= header.SIZE
                      and footer.vbmeta_offset + footer.vbmeta_size <= size - footer.SIZE,
                      "invalid vendor AVB extents")
        trees = [d for d in descriptors if isinstance(d, avbtool.AvbHashtreeDescriptor)]
        props = [d for d in descriptors if isinstance(d, avbtool.AvbPropertyDescriptor)]
        image.require(len(trees) == 1 and len(trees) + len(props) == len(descriptors),
                      "unexpected vendor AVB descriptor types/count")
        tree = trees[0]
        image.require(tree.partition_name == partition and tree.flags == 0
                      and tree.image_size == footer.original_image_size
                      and tree.tree_offset == tree.image_size and tree.tree_size > 0,
                      "invalid vendor hashtree contract")
        values = {d.key: d.value for d in props}
        image.require(len(values) == len(props) and set(cohort) <= set(values),
                      "vendor AVB properties are missing or duplicated")
        return footer, header, tree, values, size
    finally:
        handle._image.close()


def verify_signature(path: Path, key: Path | None, expected_public_key: Path | None,
                     *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> None:
    require_partition_contract(partition, cohort)
    # avbtool resolves descriptor files by partition name. A canonical basename
    # prevents a correct neighbour from masking corruption of another input.
    image.require(path.name == partition + ".img", f"AVB verification requires canonical {partition}.img")
    expected = expected_public_key.read_bytes() if expected_public_key is not None else None
    image.require(expected_public_key is None or bool(expected), "empty expected AVB public key")
    with contextlib.redirect_stdout(io.StringIO()):
        avbtool.Avb().verify_image(str(path), str(key) if key else None, None, False, False, expected)


def verify_fec(path: Path, fec: Path, *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> None:
    require_partition_contract(partition, cohort)
    footer, _, tree, _, _ = parse(path, partition=partition, cohort=cohort)
    image.require(tree.fec_num_roots > 0 and tree.fec_size > 0
                  and tree.fec_offset == tree.tree_offset + tree.tree_size
                  and tree.fec_offset + tree.fec_size <= footer.vbmeta_offset,
                  "invalid vendor FEC extents")
    image.require(shutil.disk_usage(path.parent).free > tree.fec_offset + tree.fec_size + 32 * 1024**2,
                  "insufficient scratch space for independent FEC verification")
    with tempfile.TemporaryDirectory(prefix=f".{partition}-fec-", dir=path.parent) as temporary:
        prefix = Path(temporary) / "filesystem-and-hashtree.img"
        encoded = Path(temporary) / "fec.bin"
        with path.open("rb") as source, prefix.open("xb") as output:
            remaining = tree.fec_offset
            while remaining:
                block = source.read(min(remaining, 1024 * 1024))
                image.require(bool(block), "truncated image before FEC")
                output.write(block)
                remaining -= len(block)
        # avbtool's verifier deliberately skips FEC. Re-encode only the exact
        # protected prefix with the built fec tool, never the original image.
        image.run([fec, "--encode", "--roots", str(tree.fec_num_roots), prefix, encoded])
        header_size = struct.calcsize(avbtool.FEC_FOOTER_FORMAT)
        with encoded.open("rb") as expected, path.open("rb") as actual:
            image.require(encoded.stat().st_size >= tree.fec_size + header_size,
                          "truncated independently generated FEC output")
            expected.seek(-header_size, os.SEEK_END)
            magic, version, size, roots, fec_size, input_size, _ = struct.unpack(
                avbtool.FEC_FOOTER_FORMAT, expected.read(header_size))
            image.require(magic == avbtool.FEC_MAGIC and version == 0 and size == header_size
                          and roots == tree.fec_num_roots and fec_size == tree.fec_size
                          and input_size == tree.fec_offset, "generated FEC header differs")
            expected.seek(0)
            actual.seek(tree.fec_offset)
            remaining = tree.fec_size
            while remaining:
                count = min(remaining, 1024 * 1024)
                block = expected.read(count)
                image.require(len(block) == count and actual.read(count) == block,
                              "vendor FEC bytes differ from independent encoding")
                remaining -= count


def original_properties(reader: Path, stock: Path,
                        *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> tuple:
    require_partition_contract(partition, cohort)
    parsed = parse(stock, partition=partition, cohort=cohort)
    verify_signature(stock, None, None, partition=partition, cohort=cohort)
    source = image.run([reader, "cat", stock, "build.prop" if partition == "vendor" else "etc/build.prop"]).stdout
    props = {}
    for line in source.splitlines():
        if b"=" in line and not line.lstrip().startswith(b"#"):
            key, value = line.split(b"=", 1)
            # OEM build.prop legitimately repeats unrelated, equal-valued
            # properties. This parser interprets only the three AVB cohort keys;
            # the complete file, including every repeated line, stays unchanged.
            if key in cohort.values():
                image.require(key not in props, "duplicate OEM cohort property")
                props[key] = value
    for avb_key, prop_key in cohort.items():
        image.require(props.get(prop_key) == parsed[3][avb_key],
                      f"OEM build.prop disagrees with AVB property {avb_key}")
    return parsed


def signing_properties(info: Path, avb: Path, key: Path, algorithm: str,
                       original: tuple, *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> dict:
    require_partition_contract(partition, cohort)
    values = {}
    for line in info.read_text().splitlines():
        if line and not line.startswith("#"):
            name, value = line.split("=", 1)
            image.require(name not in values, "duplicate image property")
            values[name] = value
    props = build_image.ImagePropFromGlobalDict(values, partition)
    image.require(props.get("avb_enable") == "true"
                  and props.get("avb_hashtree_enable") == "true"
                  and props.get("fs_type") == "erofs", "derived vendor requires EROFS and AVB")
    image.require(props.get("avb_algorithm") == algorithm and algorithm != "NONE"
                  and props.get("avb_key_path") and os.path.samefile(props["avb_key_path"], key),
                  "image properties do not match the expected vendor signing key/algorithm")
    configured_avb = props.get("avb_avbtool")
    resolved_avb = shutil.which(configured_avb) if configured_avb else None
    image.require(resolved_avb is not None and os.path.samefile(resolved_avb, avb),
                  "image properties refer to another avbtool")
    props["avb_avbtool"] = str(avb.resolve(strict=True))
    footer, header, tree, original_cohort, _ = original
    words = shlex.split(props.get("avb_add_hashtree_footer_args", ""))
    forwarded = []
    seen_props = set()
    options = {"--hash_algorithm": tree.hash_algorithm,
               "--block_size": str(tree.data_block_size),
               "--fec_num_roots": str(tree.fec_num_roots),
               "--rollback_index": str(header.rollback_index),
               "--rollback_index_location": str(header.rollback_index_location)}
    seen_options = set()
    while words:
        option = words.pop(0)
        image.require(bool(words), "footer option lacks a value")
        value = words.pop(0)
        if option == "--prop":
            name, text = value.split(":", 1)
            image.require(name in original_cohort and name not in seen_props, "unapproved footer property")
            seen_props.add(name)
            # Make unconditionally supplies the framework fingerprint. This
            # explicitly managed OEM vendor preserves its own original cohort.
            if name != f"com.android.build.{partition}.fingerprint":
                image.require(text.encode() == original_cohort[name], "vendor cohort property changed")
        else:
            image.require(option in options and option not in seen_options
                          and value == options[option], "unsupported or changed footer option")
            seen_options.add(option)
    image.require(tree.data_block_size == tree.hash_block_size and tree.fec_num_roots > 0,
                  "unsupported original vendor hashtree layout")
    for name, value in options.items():
        forwarded += [name, value]
    for name, value in sorted(original_cohort.items()):
        forwarded += ["--prop", name + ":" + value.decode("utf-8")]
    props["avb_add_hashtree_footer_args"] = shlex.join(forwarded)
    props["avb_salt"] = tree.salt.hex()
    return props


def verify(reader: Path, stock: Path, raw: Path, sealed: Path, key: Path,
           public_key: Path, algorithm: str, fec: Path,
           *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> dict:
    require_partition_contract(partition, cohort)
    original = original_properties(reader, stock, partition=partition, cohort=cohort)
    footer, header, tree, props, size = parse(sealed, partition=partition, cohort=cohort)
    image.require(avbtool.lookup_algorithm_by_type(header.algorithm_type)[0] == algorithm
                  and algorithm != "NONE", "vendor signature algorithm differs")
    verify_signature(sealed, key, public_key, partition=partition, cohort=cohort)
    verify_fec(sealed, fec, partition=partition, cohort=cohort)
    image.require(props == original[3], "vendor AVB properties differ from OEM cohort")
    for name in ("rollback_index", "rollback_index_location", "flags"):
        image.require(getattr(header, name) == getattr(original[1], name),
                      "vendor AVB rollback/flags changed")
    for name in ("dm_verity_version", "hash_algorithm", "data_block_size", "hash_block_size",
                 "fec_num_roots", "flags", "salt"):
        image.require(getattr(tree, name) == getattr(original[2], name),
                      f"vendor hashtree property changed: {name}")
    image.require(footer.original_image_size == raw.stat().st_size,
                  "sealed filesystem extent differs from verified raw image")
    meta = image.superblock(reader, raw)
    image.require(meta["blocks"] * meta["block_size"] == raw.stat().st_size,
                  "raw intermediate contains non-filesystem tail")
    with raw.open("rb") as expected, sealed.open("rb") as actual:
        while block := expected.read(1024 * 1024):
            image.require(actual.read(len(block)) == block, "AVB step changed filesystem bytes")
    return {"filesystem_bytes": raw.stat().st_size, "partition_bytes": size,
            "algorithm": algorithm, "expected_public_key_verified": True,
            "fec_verified": "independent encoding and complete FEC byte comparison",
            partition + "_properties": {k: v.decode() for k, v in props.items()}}


def seal(reader: Path, stock: Path, raw: Path, output: Path, info: Path,
         avb: Path, key: Path, public_key: Path, algorithm: str, fec: Path,
         *, partition: str = "vendor", cohort: dict[str, bytes] = COHORT) -> dict:
    require_partition_contract(partition, cohort)
    image.require(not output.exists() and not output.is_symlink(), "AVB output already exists")
    image.require(output.parent.is_dir(), "AVB output parent must exist")
    original = original_properties(reader, stock, partition=partition, cohort=cohort)
    props = signing_properties(info, avb, key, algorithm, original, partition=partition, cohort=cohort)
    builder = verity_utils.CreateVerityImageBuilder(props)
    image.require(builder is not None, "AVB builder is missing")
    if not props.get("partition_size"):
        image.require(props.get("use_dynamic_partition_size") == "true",
                      "vendor partition size is neither fixed nor dynamic")
        builder.CalculateDynamicPartitionSize(raw.stat().st_size)
    image.require(builder.CalculateMaxImageSize() >= raw.stat().st_size,
                  "vendor filesystem exceeds its partition capacity")
    with tempfile.TemporaryDirectory(prefix=f".{partition}-avb-", dir=output.parent) as temporary:
        candidate = Path(temporary) / (partition + ".img")
        shutil.copyfile(raw, candidate)
        builder.Build(str(candidate))
        report = verify(reader, stock, raw, candidate, key, public_key, algorithm, fec,
                        partition=partition, cohort=cohort)
        os.link(candidate, output)
        return report
