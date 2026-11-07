# SPDX-License-Identifier: MIT
"""Derive only the reviewed OEM policy contracts, then compile the complete policy.

No CIL replacement input, success marker, or precompiled policy is accepted as
evidence. Both modified files are regenerated from the supplied raw stock image.
"""
from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
import tempfile
import zipfile

if __package__:
    from . import derive_vendor as image
    from .policy import (repair_vendor_binder_policy as binder,
                         derive_vendor_app_debug_policy as app,
                         derive_vendor_codec_debug_policy as codec,
                         adapt_vendor_property_policy as prop,
                         adapt_vendor_avf_policy as avf,
                         repair_display_config_binder_policy as display)
else:
    import derive_vendor as image
    from policy import (repair_vendor_binder_policy as binder,
                        derive_vendor_app_debug_policy as app,
                        derive_vendor_codec_debug_policy as codec,
                        adapt_vendor_property_policy as prop,
                        adapt_vendor_avf_policy as avf,
                        repair_display_config_binder_policy as display)

VENDOR_CIL = b"etc/selinux/vendor_sepolicy.cil"
PUBLIC_CIL = b"etc/selinux/plat_pub_versioned.cil"
ODM_CIL = b"etc/selinux/odm_sepolicy.cil"
POLICY_PATHS = frozenset((VENDOR_CIL, PUBLIC_CIL))
# These are the actual files selected by fixed init/selinux.cpp for this OEM's
# plat_sepolicy_vers=202504 and genfs_labels_version=202504.
PLATFORM_PATHS = {
    "plat": ("SYSTEM", "etc/selinux/plat_sepolicy.cil"),
    "plat-map": ("SYSTEM", "etc/selinux/mapping/202504.cil"),
    "plat-compat": ("SYSTEM", "etc/selinux/mapping/202504.compat.cil"),
    "system-ext": ("SYSTEM_EXT", "etc/selinux/system_ext_sepolicy.cil"),
    "system-ext-map": ("SYSTEM_EXT", "etc/selinux/mapping/202504.cil"),
    "system-ext-compat": ("SYSTEM_EXT", "etc/selinux/mapping/202504.compat.cil"),
    "product": ("PRODUCT", "etc/selinux/product_sepolicy.cil"),
    "product-map": ("PRODUCT", "etc/selinux/mapping/202504.cil"),
    "genfs": ("SYSTEM", "etc/selinux/plat_sepolicy_genfs_202504.cil"),
}
HASH_PATHS = {
    name + "-hash": (partition, "etc/selinux/" + name.replace("-", "_")
                    + "_sepolicy_and_mapping.sha256")
    for name, partition in (("plat", "SYSTEM"), ("system-ext", "SYSTEM_EXT"),
                            ("product", "PRODUCT"))
}
# Exact original files consumed by the installed vendor/ODM policy modules.
# They are exported, never added to the image's allowed modification set.
RAW_VENDOR_FILES = (
    "plat_sepolicy_vers.txt", "genfs_labels_version.txt", "selinux_denial_metadata",
    "vendor_file_contexts", "vendor_hwservice_contexts", "vendor_keystore2_key_contexts",
    "vendor_mac_permissions.xml", "vendor_property_contexts", "vendor_seapp_contexts",
    "vendor_service_contexts", "vendor_tee_service_contexts", "vndservice_contexts")
RAW_ODM_FILES = (
    "odm_sepolicy.cil", "odm_file_contexts", "odm_hwservice_contexts",
    "odm_mac_permissions.xml", "odm_property_contexts", "odm_seapp_contexts",
    "odm_service_contexts", "precompiled_sepolicy",
    *("precompiled_sepolicy." + relative.rsplit("/", 1)[1]
      for _, relative in HASH_PATHS.values()))

REQUIRED_INPUTS = frozenset(PLATFORM_PATHS) | {
    "odm-stock", "macros", "global-macros", "codec-source", "secilc", "m4", "workspace"}


@dataclass(frozen=True)
class Inputs:
    paths: dict[str, Path]
    build_variant: str = "userdebug"

    @classmethod
    def parse(cls, arguments: list[str], build_variant: str | None = None) -> "Inputs | None":
        if not arguments:
            return None
        image.require(build_variant in {"user", "userdebug"}, "explicit user/userdebug policy variant required")
        values = {}
        for argument in arguments:
            name, separator, value = argument.partition("=")
            image.require(separator and value and name not in values,
                          "invalid or duplicate policy input")
            values[name] = Path(value)
        image.require(set(values) == REQUIRED_INPUTS | set(HASH_PATHS),
                      "policy inputs must contain the complete fixed contract")
        for name in REQUIRED_INPUTS - {"workspace"}:
            image.require(values[name].is_file(), "missing policy input: " + name)
        image.require(values["workspace"].is_dir(), "policy workspace must already exist")
        return cls(values, build_variant)

    def read(self, name: str) -> bytes:
        return self.paths[name].read_bytes()


def read_regular(reader: Path, stock: Path, entries: dict, path: bytes) -> bytes:
    image.require(path in entries and stat.S_ISREG(entries[path]["mode"])
                  and entries[path]["nlink"] == 1,
                  "policy input must be an unaliased regular inode: " + os.fsdecode(path))
    return image.run([reader, "cat", stock, os.fsdecode(path)]).stdout


# Original system_ext definitions and labels, retained as platform compatibility
# types. Their permissions and executable/app installation are not synthesized.
OEM_PLATFORM_CORE_TYPES = frozenset(b"cameramind_app hypsys_ssi_default joyose_app misight "
                                    b"mslg_app swapboost_native theme".split())
# Unused legacy names in the OEM vendor policy. Actual vendor/ODM HALs have
# distinct hal_*_default types; none of these names has a process entrypoint.
LEGACY_HAL_CORE_TYPES = frozenset(b"ntn_rild mimd2 mtdservice tidaservice vsimapp otrpagent "
                                 b"mrm micrtk misecmedia mseccam idmanager miguardca "
                                 b"mikeybag midevauth miweaver".split())


def adapt_coredomain_ownership(data: bytes, system_ext: bytes) -> bytes:
    definitions = set(re.findall(rb"^\(type ([A-Za-z0-9_]+)\)$", system_ext, re.M))
    core_sets = re.findall(rb"^\(typeattributeset coredomain \(([^()]*)\)\)$", system_ext, re.M)
    image.require(len(core_sets) == 1 and OEM_PLATFORM_CORE_TYPES <= definitions
                  and OEM_PLATFORM_CORE_TYPES <= set(core_sets[0].split()),
                  "OEM system_ext compatibility types must be owned by actual platform policy")
    pattern = rb"^\(typeattributeset coredomain \(([^()]*)\)\)\n"
    matches = list(re.finditer(pattern, data, re.M))
    image.require(len(matches) == 1, "expected one OEM coredomain membership set")
    match = matches[0]
    words = match[1].split()
    avf_names = (b"crosvm", b"early_virtmgr", b"virtualizationmanager")
    replacements = {name + b"_202504": name + b"_vendor" for name in avf_names}
    retired = OEM_PLATFORM_CORE_TYPES | LEGACY_HAL_CORE_TYPES
    image.require(len(words) == len(set(words)) and retired | replacements.keys() <= set(words)
                  and not set(replacements.values()).intersection(words),
                  "OEM coredomain ownership contract changed or already adapted")
    for name in LEGACY_HAL_CORE_TYPES:
        image.require(not re.search(rb"^\(typetransition [^\n]* process " + name + rb"\)$", data, re.M)
                      and not re.search(rb"^\(allow " + name + rb" [^\n]*\bentrypoint\b", data, re.M),
                      "legacy HAL type acquired a process entrypoint: " + name.decode())
    replacement = b"(typeattributeset coredomain (" + b" ".join(
        replacements.get(word, word) for word in words if word not in retired) + b"))\n"
    return data[:match.start()] + replacement + data[match.end():]


def adapt_public_avf_core_ownership(data: bytes) -> bytes:
    # The retained public CIL independently expands the same legacy aliases.
    # Bind only core membership to the current platform-owned vendor clients;
    # all compatibility aliases and their allow/neverallow rules remain intact.
    pattern = rb"^\(typeattributeset coredomain \(([^()]*)\)\)\n"
    matches = list(re.finditer(pattern, data, re.M))
    image.require(len(matches) == 1, "expected one public coredomain membership set")
    match = matches[0]
    words = match[1].split()
    replacements = {name + b"_202504": name + b"_vendor"
                    for name in (b"crosvm", b"early_virtmgr", b"virtualizationmanager")}
    image.require(len(words) == len(set(words)) and replacements.keys() <= set(words)
                  and not set(replacements.values()).intersection(words),
                  "public AVF core ownership contract changed or already adapted")
    replacement = b"(typeattributeset coredomain (" + b" ".join(
        replacements.get(word, word) for word in words) + b"))\n"
    return data[:match.start()] + replacement + data[match.end():]


def verify_platform_hal_contract(data: bytes) -> None:
    # Compiler output uses explicit members; refuse a different/ambiguous
    # attribute expression rather than assuming the three HAL clients exist.
    view = re.sub(rb'"(?:\\.|[^"\\])*"|;[^\n]*',
                  lambda m: b" " if m[0].startswith(b";") else m[0], data)
    for client, hal in ((b"virtualizationmanager_vendor", b"hal_secretkeeper"),
                        (b"virtualizationmanager_vendor", b"hal_vm_capabilities"),
                        (b"early_virtmgr_vendor", b"hal_secretkeeper")):
        matches = re.findall(rb"\(\s*typeattributeset\s+" + hal
                             + rb"_client\s+\(([^()]*)\)\s*\)", view)
        image.require(sum(m.split().count(client) for m in matches) == 1,
                      "missing or duplicated actual AVF HAL client")
        for source, target in ((client, hal), (hal, client)):
            expression = (rb"\(\s*allow\s+" + source + rb"\s+" + target
                          + rb"\s+\(\s*memfd_file\s+\(([^()]*)\)\s*\)\s*\)")
            rules = re.findall(expression, view)
            image.require(len(rules) == 1 and Counter(rules[0].split())
                          == Counter(b"read write getattr map".split()),
                          "actual AVF HAL memfd contract differs")


CAMERA_DOMAIN = b"popsicle_camera_app"
CAMERA_XDSP_CLIENT_SET = (
    b"(typeattributeset base_typeattr_297_202504 (and (domain) (not ("
    b"init_202504 platform_app_202504 shell_202504 system_app_202504 ueventd_202504 "
    b"vendor_init_202504 hal_audio_default hal_camera_default hal_contexthub_default "
    b"hal_sensors_default vendor_adsprpcd vendor_audioadsprpcd vendor_cdsprpcd vendor_chre "
    b"vendor_dspservice vendor_sensors vendor_lowirpcd_service vendor_hexlpservice "
    b"vendor_vppservice theme vendor_hal_miaon_frame_default hal_seaaudio_default))))\n"
)
# Original platform-app grants exercised by the camera's actual SDK/DSP and
# capability consumers. Keep the exact permission sets and duplicate counts;
# the camera does not receive every OEM platform-app permission.
CAMERA_VENDOR_RULES = Counter({
    b"(allow platform_app_202504 adsprpcd_file (dir (getattr search)))\n": 2,
    b"(allow platform_app_202504 vendor_xdsp_device (chr_file (ioctl read open)))\n": 1,
    b"(allow platform_app_202504 vendor_camera_sensor_prop (file (read getattr map open)))\n": 1,
    b"(allow platform_app_202504 vendor_displayfeature_prop (file (read getattr map open)))\n": 2,
})


def adapt_camera_app_contract(data: bytes, system_ext: bytes, platform_map: bytes) -> bytes:
    """Preserve the camera's priv-app baseline and add its proven OEM consumers."""
    image.require(not re.search(rb"\b" + CAMERA_DOMAIN + rb"\b", data),
                  "OEM camera policy was already adapted")
    image.require(len(re.findall(rb"^\(type " + CAMERA_DOMAIN + rb"\)$", system_ext, re.M)) == 1,
                  "camera domain must be defined by actual system_ext policy")
    for attribute in (b"domain", b"coredomain", b"appdomain", b"priv_app_all",
                      b"netdomain", b"bluetoothdomain", b"halclientdomain"):
        sets = re.findall(rb"^\(typeattributeset " + attribute + rb" \(([^()]*)\)\)$",
                          system_ext, re.M)
        image.require(sum(members.split().count(CAMERA_DOMAIN) for members in sets) == 1,
                      "camera platform sandbox membership differs: " + attribute.decode())
    original_priv = re.findall(rb"^\(typeattributeset priv_app_202504 \(([^()]*)\)\)$",
                               platform_map, re.M)
    image.require(len(original_priv) == 1
                  and Counter(original_priv[0].split()) == Counter((b"priv_app", b"priv_app_36")),
                  "camera's original SDK 36 vendor compatibility mapping differs")
    clients = re.findall(rb"^\(typeattributeset hal_misys_vendor_client \(([^()]*)\)\)$",
                         data, re.M)
    image.require(len(clients) == 1 and clients[0].split().count(b"platform_app_202504") == 1,
                  "original platform camera MiSys client contract differs")
    image.require(data.count(b"(typeattributeset hal_misys_vendor_server (hal_misys_vendor_default))\n") == 1,
                  "original MiSys AIDL process owner differs")
    discovery = b"(allow hal_misys_vendor_client hal_misys_vendor_service (service_manager (find)))\n"
    image.require(data.count(discovery) == 1,
                  "original MiSys AIDL discovery contract differs")
    actual = Counter(line for line in data.splitlines(keepends=True) if line in CAMERA_VENDOR_RULES)
    image.require(actual == CAMERA_VENDOR_RULES,
                  "original camera DSP/property contract differs")
    image.require(data.count(CAMERA_XDSP_CLIENT_SET) == 1,
                  "original XDSP client restriction differs")
    # Carry the original camera's XDSP client qualification into its new domain.
    # Keep both neverallow rules; the separate write restriction (298) still
    # covers this camera, so only the proven ioctl/read/open grant is added.
    data = data.replace(CAMERA_XDSP_CLIENT_SET, CAMERA_XDSP_CLIENT_SET.replace(
        b"(not (", b"(not (" + CAMERA_DOMAIN + b" ", 1), 1)
    # priv_app_202504 currently contains priv_app_36. Retaining that membership
    # preserves the camera's existing BGService/postproc/QuickCamera grants and
    # all vendor restrictions. It does not modify any other app's membership.
    # The MiSys client attribute preserves its find neverallow, Binder callbacks
    # and FD transfer rules. No service label is used as a process domain.
    additions = [b"(typeattributeset priv_app_202504 (" + CAMERA_DOMAIN + b"))\n",
                 b"(typeattributeset hal_misys_vendor_client (" + CAMERA_DOMAIN + b"))\n"]
    additions.extend(rule.replace(b"platform_app_202504", CAMERA_DOMAIN)
                     for rule in CAMERA_VENDOR_RULES)
    return data + b"\n; Platform-signed popsicle camera: retained sandbox and OEM clients.\n" + b"".join(additions)


def cache_selection(reader: Path, odm: Path, entries: dict,
                    actual_hashes: dict[str, bytes | None]) -> list[str]:
    binary = b"etc/selinux/precompiled_sepolicy"
    if binary not in entries:
        return ["ODM has no precompiled policy"]
    read_regular(reader, odm, entries, binary)
    reasons = []
    for key, (_, relative) in HASH_PATHS.items():
        old_path = b"etc/selinux/precompiled_sepolicy." + relative.rsplit("/", 1)[1].encode()
        old = (read_regular(reader, odm, entries, old_path).split(b"\n", 1)[0:1]
               if old_path in entries else [])
        current = actual_hashes[key]
        first = current.split(b"\n", 1)[0:1] if current is not None else []
        # Match FindPrecompiledSplitPolicy: missing/empty/mismatched current or
        # old hashes invalidate the cache; both absent leaves this pair neutral.
        if current is None:
            if old_path in entries:
                reasons.append(key + ": current hash missing")
        elif not first or not first[0] or not old or first != old:
            reasons.append(key + ": hash differs or is empty")
    image.require(bool(reasons), "old ODM precompiled policy would bypass the derived CIL")
    return reasons


def generate(reader: Path, stock: Path, entries: dict, inputs: Inputs,
             artifacts: dict[str, bytes] | None = None) -> tuple[dict[bytes, bytes], dict]:
    paths = inputs.paths
    image.require(read_regular(reader, stock, entries,
                               b"etc/selinux/plat_sepolicy_vers.txt").strip() == b"202504",
                  "unexpected OEM platform policy version")
    image.require(read_regular(reader, stock, entries,
                               b"etc/selinux/genfs_labels_version.txt").strip() == b"202504",
                  "unexpected OEM genfs policy version")
    original_vendor = read_regular(reader, stock, entries, VENDOR_CIL)
    original_public = read_regular(reader, stock, entries, PUBLIC_CIL)
    odm = image.inventory(reader, paths["odm-stock"])
    original_odm = read_regular(reader, paths["odm-stock"], odm, ODM_CIL)
    for variant in ("user", "userdebug"):
        app.macro_exclusions(paths["m4"], paths["macros"], variant)
        codec.validate_producer(paths["m4"], paths["macros"], paths["codec-source"], variant)
    avf.validate_producer(paths["m4"], paths["global-macros"], paths["macros"])
    verify_platform_hal_contract(inputs.read("product"))
    vendor, binder_count = binder.repair(original_vendor)
    vendor, app_count = app.derive(vendor, inputs.build_variant)
    vendor, codec_count = codec.derive(vendor, inputs.build_variant)
    vendor, avf_count = avf.adapt(vendor)
    vendor = adapt_coredomain_ownership(vendor, inputs.read("system-ext"))
    vendor = display.repair(vendor)
    vendor = adapt_camera_app_contract(vendor, inputs.read("system-ext"), inputs.read("plat-map"))
    public, property_count = prop.adapt(original_public, inputs.read("plat"), inputs.read("plat-map"))
    public = adapt_public_avf_core_ownership(public)
    changes = {VENDOR_CIL: vendor, PUBLIC_CIL: public}
    hashes = {name: paths[name].read_bytes() if paths[name].is_file() else None for name in HASH_PATHS}
    reasons = cache_selection(reader, paths["odm-stock"], odm, hashes)
    with tempfile.TemporaryDirectory(prefix="popsicle-strict-policy-", dir=paths["workspace"]) as temporary:
        root = Path(temporary)
        for name, content in (("vendor.cil", vendor), ("public.cil", public), ("odm.cil", original_odm)):
            (root / name).write_bytes(content)
        # Fixed policy version and required full input list. There is deliberately
        # no caller-supplied compiler argument or ignore-neverallow switch.
        image.run([paths["secilc"], "-m", "-M", "true", "-G", "-v", "-c", "30",
                   *(paths[name] for name in PLATFORM_PATHS if name != "genfs"),
                   root / "public.cil", root / "odm.cil", paths["genfs"], root / "vendor.cil",
                   "-o", root / "policy", "-f", root / "file_contexts"])
        image.require((root / "policy").is_file() and (root / "policy").stat().st_size > 0,
                      "strict compiler produced no policy")
        if artifacts is not None:
            artifacts["strict-policy"] = (root / "policy").read_bytes()
            artifacts["strict-inputs.cil"] = b"\n".join([
                *(inputs.read(name) for name in PLATFORM_PATHS if name != "genfs"),
                public, original_odm, inputs.read("genfs"), vendor]) + b"\n"
            for original, inventory, names in ((stock, entries, RAW_VENDOR_FILES),
                                                (paths["odm-stock"], odm, RAW_ODM_FILES)):
                for name in names:
                    artifacts[name] = read_regular(reader, original, inventory,
                                                  b"etc/selinux/" + name.encode())
    return changes, {"build_variant": inputs.build_variant, "binder_rules": sum(binder_count.values()), "app_sets": app_count,
                     "codec_guards": codec_count, "property_guards": property_count,
                     "avf_transitions": avf_count, "avf_added_rules": len(avf.ADDITIONS),
                     "display_rules": sum(display.expected_rules().values()),
                     "camera_vendor_rules": len(CAMERA_VENDOR_RULES),
                     "camera_client_memberships": 2,
                     "old_odm_cache_rejected": reasons, "strict_neverallow": "passed"}


def publish(reader: Path, stock: Path, inputs: Inputs, output: Path) -> dict:
    image.require(not output.is_symlink(), "policy output directory is a symlink")
    output = output.resolve()
    for path in [stock, *(p for name, p in inputs.paths.items() if name != "workspace")]:
        image.require(not path.resolve().is_relative_to(output), "policy output contains an input")
    image.require(output.parent.is_dir(), "policy output parent must already exist")
    outputs = {}
    changes, report = generate(reader, stock, image.inventory(reader, stock), inputs, outputs)
    outputs.update({os.fsdecode(path.rsplit(b"/", 1)[1]): data for path, data in changes.items()})
    with tempfile.TemporaryDirectory(prefix=".policy-publish-", dir=output.parent) as temporary:
        prepared = Path(temporary)
        for name, data in outputs.items():
            (prepared / name).write_bytes(data)
        output.mkdir(exist_ok=True)
        for name in outputs:
            existing = output / name
            if existing.exists() or existing.is_symlink():
                image.require(not existing.is_symlink() and existing.is_file()
                              and existing.stat().st_nlink == 1,
                              "policy output aliases another file")
        for name in outputs:
            os.replace(prepared / name, output / name)
    return report


def verify_target_files(reader: Path, stock: Path, derived: Path, inputs: Inputs, directory: Path | None,
                        archive: Path | None) -> None:
    image.require(bool(directory) != bool(archive), "select one policy target-files view")
    before = image.inventory(reader, stock)
    changes, _ = generate(reader, stock, before, inputs)
    after = image.inventory(reader, derived)
    for path, expected in changes.items():
        image.require(read_regular(reader, derived, after, path) == expected,
                      "target-files image policy differs from the proven contract")
        for field in set(before[path]) - {"nid", "size"}:
            image.require(after[path][field] == before[path][field],
                          "target-files image policy metadata changed")

    with _Archive(archive) if archive else _Directory(directory) as view:
        hashes = {}
        for name, (partition, relative) in (PLATFORM_PATHS | HASH_PATHS).items():
            candidates = [partition + "/" + relative]
            if partition == "SYSTEM":
                candidates.append("SYSTEM/system/" + relative)
            present = [path for path in candidates if view.exists(path)]
            image.require(len(present) <= 1, "ambiguous platform policy path in target-files")
            content = view.read(present[0]) if present else None
            expected = inputs.paths[name].read_bytes() if inputs.paths[name].is_file() else None
            image.require(content == expected, "target-files policy input differs: " + name)
            if name in HASH_PATHS:
                hashes[name] = content
        stock = inputs.paths["odm-stock"]
        cache_selection(reader, stock, image.inventory(reader, stock), hashes)


class _Directory:
    def __init__(self, root: Path):
        self.root = root

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        pass

    def exists(self, path: str) -> bool:
        candidate = self.root / path
        image.require(not candidate.is_symlink(), "target-files policy file is a symlink")
        image.require(candidate.resolve().is_relative_to(self.root.resolve()),
                      "target-files policy path leaves its view")
        return candidate.is_file()

    def read(self, path: str) -> bytes:
        return (self.root / path).read_bytes()


class _Archive:
    def __init__(self, path: Path):
        self.archive = zipfile.ZipFile(path)

    def __enter__(self):
        return self

    def __exit__(self, *unused):
        self.archive.close()

    def exists(self, path: str) -> bool:
        count = self.archive.namelist().count(path)
        image.require(count <= 1, "duplicate target-files policy member")
        if count:
            entry = self.archive.getinfo(path)
            image.require(not entry.is_dir() and stat.S_IFMT(entry.external_attr >> 16)
                          in (0, stat.S_IFREG), "target-files policy member is not a file")
        return count == 1

    def read(self, path: str) -> bytes:
        return self.archive.read(path)
