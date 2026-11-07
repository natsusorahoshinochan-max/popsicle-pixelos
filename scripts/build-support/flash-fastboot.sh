#!/bin/bash
# Fresh A16 -> PixelOS install. Bash 3.2 compatible; fixed B slot.
set -euo pipefail
export LC_ALL=C
if [ "$#" -gt 1 ]; then
    echo "Usage: bash $0 [IMAGE_DIRECTORY]" >&2
    exit 2
fi
cd -- "${1:-$(dirname -- "$0")}"
log="$PWD/flash-$(date +%Y%m%d-%H%M%S)-$$.log"
exec > >(tee "$log") 2>&1
tmp=$(mktemp -d "${TMPDIR:-/tmp}/popsicle-flash.XXXXXXXX")
cleanup() { rm -rf -- "$tmp"; }
trap cleanup EXIT
trap 'rc=$?; echo "STOPPED (exit $rc). No further writes, slot change or reboot. Log: $log"; exit "$rc"' ERR
die() { echo "STOPPED: $*; log: $log" >&2; exit 1; }
echo 'FRESH INSTALL ONLY: official A16 OS3.0.318.0 -> PixelOS user + OS4.0.0.23 firmware.'
echo 'ALL USER DATA WILL BE ERASED, including internal storage and encryption metadata.'
echo 'Full super replaces both logical slots. Only B is populated; A is not a rollback system.'

# Package metadata cannot introduce another flash target or change this order.
firmware=(abl xbl xbl_config multiimgqti tme_seq_patch tme_fw tme_config xbl_ac_config
    uefi aop aop_config tz hyp modem modemfirmware bluetooth dsp keymaster spuservice
    devcfg qupfw uefisecapp imagefv shrm cpucp idmanager featenabler xbl_ramdump
    cpucp_dtb soccp soccp_debug soccp_dcd pdp pdp_cdb tz_ac_config hyp_ac_config
    dcp tz_qti_config secretkeeper vm-bootsys qtvm_dtbo pvmfw)
parts=("${firmware[@]}" super boot dtbo vendor_boot vbmeta recovery vbmeta_system init_boot)
images=()
for part in "${parts[@]}"; do
    if [ "$part" = super ]; then name=super-install-b.img; else name="$part.img"; fi
    images+=("$name")
done
: > "$tmp/selected-sums"
for file in "${images[@]}" flash-manifest.tsv; do
    [ -f "$file" ] && [ ! -L "$file" ] && [ -s "$file" ] || die "missing/empty/symlink file: $file"
    awk -v name="$file" '$2 == name {
        if (NF != 2 || length($1) != 64 || $1 ~ /[^0-9a-f]/) exit 1
        count++; print $1 "  " name
    } END {if (count != 1) exit 1}' SHA256SUMS >> "$tmp/selected-sums" || die "missing/invalid checksum: $file"
done
if command -v sha256sum >/dev/null; then sha256sum -c "$tmp/selected-sums"; else shasum -a 256 -c "$tmp/selected-sums"; fi
sizes=()
index=0
while IFS=$'\t' read -r target file bytes expanded source rest; do
    [ "$index" -lt "${#parts[@]}" ] || die 'extra manifest row'
    part=${parts[$index]}
    expected_target="${part}_b"
    expected_source=a17-payload
    if [ "$part" = super ]; then
        expected_target=super
        expected_source=pixelos-super
    elif [ "$index" -ge 42 ]; then
        expected_source=pixelos-target-files
    fi
    [ "$target" = "$expected_target" ] && [ "$file" = "${images[$index]}" ] &&
        [ "$source" = "$expected_source" ] && [ -z "$rest" ] || die "invalid manifest row $index"
    [[ "$bytes" =~ ^[1-9][0-9]{0,11}$ ]] && [[ "$expanded" =~ ^[1-9][0-9]{0,11}$ ]] || die 'invalid image size'
    actual=$(wc -c < "$file" | tr -d '[:space:]')
    [ "$actual" = "$bytes" ] || die "file length mismatch: $file"
    if [ "$part" = super ]; then
        [ "$expanded" = 13421772800 ] || die 'wrong super capacity'
        magic=$(od -An -tx1 -N4 "$file" | tr -d '[:space:]')
        [ "$magic" = 3aff26ed ] || die 'expected verified sparse super'
        block_size=$(od -An -tu4 -j12 -N4 "$file" | tr -d '[:space:]')
        blocks=$(od -An -tu4 -j16 -N4 "$file" | tr -d '[:space:]')
        [ "$block_size" = 4096 ] && [ "$((block_size * blocks))" = "$expanded" ] || die 'wrong expanded super size'
    else
        [ "$bytes" = "$expanded" ] || die "expected raw image: $file"
    fi
    sizes+=("$expanded")
    index=$((index + 1))
done < flash-manifest.tsv
[ "$index" -eq 50 ] || die 'incomplete manifest'

# fastboot locates make_f2fs next to its actual executable, not a PATH symlink.
fastboot_bin=$(command -v "${FASTBOOT:-fastboot}") || die 'fastboot not found'
while [ -L "$fastboot_bin" ]; do
    link=$(readlink "$fastboot_bin")
    case "$link" in /*) fastboot_bin=$link ;; *) fastboot_bin="$(dirname "$fastboot_bin")/$link" ;; esac
done
tool_dir=$(cd -- "$(dirname "$fastboot_bin")" && pwd -P)
fastboot_bin="$tool_dir/$(basename "$fastboot_bin")"
[ -x "$fastboot_bin" ] && [ -x "$tool_dir/make_f2fs" ] || die 'use complete Platform Tools, including make_f2fs'
"$fastboot_bin" --version
FB_OUTPUT=
fb() {
    printf 'fastboot'; printf ' %s' "$@"; printf '\n'
    rc=0
    "$fastboot_bin" "$@" > "$tmp/command.log" 2>&1 || rc=$?
    cat "$tmp/command.log"
    FB_OUTPUT=$(tr -d '\r' < "$tmp/command.log")
    [ "$rc" -eq 0 ] || die "fastboot command failed (exit $rc)"
    if grep -Eiq '(^|[[:space:]])FAILED([[:space:]:!(]|$)|^fastboot: error:' "$tmp/command.log"; then
        die 'fastboot reported failure despite successful process exit'
    fi
}
value=
getvar() {
    fb getvar "$1"
    value=$(printf '%s\n' "$FB_OUTPUT" | awk -v key="$1:" '
        index($0,key)==1 {count++; v=substr($0,length(key)+1); sub(/^[ \t]+/,"",v); sub(/[ \t]+$/,"",v)}
        END {if (count != 1 || v == "") exit 1; print v}')
    [ -n "$value" ] && [[ "$value" != *$'\n'* ]] || die "missing/ambiguous getvar $1"
}
capacity=0
get_capacity() {
    getvar "partition-size:$1"
    if [[ "$value" =~ ^0[xX][0-9a-fA-F]{1,12}$ ]]; then
        capacity=$((16#${value:2}))
    elif [[ "$value" =~ ^[0-9a-fA-F]{1,12}$ ]]; then
        # Partition sizes without 0x are also hexadecimal protocol values.
        capacity=$((16#$value))
    else
        die "invalid partition capacity: $1"
    fi
    [ "$capacity" -gt 0 ] || die "empty partition: $1"
}
getvar product; [ "$value" = popsicle ] || die 'wrong device'
getvar is-userspace; [ "$value" = no ] || die 'bootloader fastboot required'
fb oem device-info
printf '%s\n' "$FB_OUTPUT" | grep -Eq 'Device unlocked: true$' || die 'unlocked Bootloader required'
getvar slot-count; [ "$value" = 2 ] || die 'two slots required'
getvar current-slot; [[ "$value" = a || "$value" = b ]] || die 'invalid current slot'
getvar anti
[[ "$value" =~ ^[01]$ ]] || die 'outside supported A16 anti boundary (0 or 1); A17 anti is not inferred'
for ((index=0; index<${#parts[@]}; index++)); do
    part=${parts[$index]}
    target="${part}_b"
    if [ "$part" = super ]; then target=super; fi
    # A16 does not expose has-slot for firmware. Query the explicit B partition
    # itself: a missing/invalid/undersized target still fails before any write.
    get_capacity "$target"
    [ "$capacity" -ge "${sizes[$index]}" ] || die "partition too small: $target"
    if [ "$part" = super ]; then [ "$capacity" -eq 13421772800 ] || die 'unexpected physical super'; fi
done
for part in userdata metadata; do
    get_capacity "$part"
    getvar "partition-type:$part"
    # A16 bootloader's advertised type may be raw. The product fstab owns the
    # desired filesystem; the explicit format:f2fs command overrides this hint.
    echo "$part advertised type: $value; will explicitly format as f2fs"
done
echo "Preflight passed. Writing fixed B-slot firmware and PixelOS images; do not disconnect."
for part in "${firmware[@]}"; do fb flash "${part}_b" "$part.img"; done
fb -S 256M flash super super-install-b.img
for part in boot dtbo vendor_boot vbmeta recovery vbmeta_system; do fb flash "${part}_b" "$part.img"; done
for part in userdata metadata; do
    fb erase "$part"
    fb format:f2fs "$part"
done
fb flash init_boot_b init_boot.img
fb set_active b
getvar current-slot; [ "$value" = b ] || die 'B slot selection did not take effect'
fb reboot
echo "All installation commands succeeded. Device acceptance is pending. Log: $log"
