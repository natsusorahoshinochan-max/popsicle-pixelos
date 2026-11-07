#!/bin/bash
# Shared installer. Sourced only by the two platform entries; Bash 3.2 compatible.
set -euo pipefail
export LC_ALL=C
mkdir -p -- logs
log="$PWD/logs/flash-$(date +%Y%m%d-%H%M%S)-$$.log"
# Keep the user's terminal separate from the complete plain-text log.
exec 3>&1
exec >> "$log" 2>&1
ui() { printf '%s\n' "$*"; printf '%s\n' "$*" >&3; }
prompt() { printf '%s' "$*" >&3; printf '%s\n' "$*"; }
banner() {
    if [ -r assets/kanoe-64.ansi ]; then
        cat assets/kanoe-64.ansi >&3 || printf 'KANOE · PixelOS · popsicle\n' >&3
    else
        printf 'KANOE · PixelOS · popsicle\n' >&3
    fi
}

tmp=$(mktemp -d "${TMPDIR:-/tmp}/popsicle-flash.XXXXXXXX")
cleanup() { printf "\033[0m" >&3; rm -rf -- "$tmp"; }
trap cleanup EXIT
trap 'rc=$?; ui "已停止（退出码 $rc），不再执行后续操作。日志：$log"; exit "$rc"' ERR
die() { ui "已停止：$*。日志：$log"; exit 1; }
trap 'ui "已中断，不再执行后续操作。日志：$log"; exit 130' INT
trap 'ui "已中断，不再执行后续操作。日志：$log"; exit 143' TERM
echo 'PixelOS user + OS4.0.0.23 firmware. Supported base: official A16 OS3.0.318.0.'
echo 'Choose whether to erase or preserve userdata and metadata after preflight. Back up first.'
echo 'Full super replaces both logical slots. Only B is populated; A is not a rollback system.'

banner
ui '请将手机进入 Bootloader Fastboot 模式，并使用 USB 连接电脑。'
prompt '按回车继续：'
if ! IFS= read -r connection; then
    ui "已取消，未执行任何刷写。日志：$log"
    exit 0
fi
ui '请稍等'

tool_files=("tools/$platform/fastboot")
if [ "$platform" = Linux ]; then
    tool_files+=("tools/Linux/lib64/libc++.so")
else
    tool_files+=("tools/macOS/lib64/libc++.dylib")
fi
verify_files() {
    local file
    : > "$tmp/selected-sums"
    for file in "$@"; do
        [ -f "$file" ] && [ ! -L "$file" ] && [ -s "$file" ] || die "missing/empty/symlink file: $file"
        awk -v name="$file" '$2 == name {
            if (NF != 2 || length($1) != 64 || $1 ~ /[^0-9a-f]/) exit 1
            count++; print $1 "  " name
        } END {if (count != 1) exit 1}' metadata/SHA256SUMS >> "$tmp/selected-sums" || die "missing/invalid checksum: $file"
    done
    if command -v sha256sum >/dev/null; then
        sha256sum -c "$tmp/selected-sums"
    else
        shasum -a 256 -c "$tmp/selected-sums"
    fi
}

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
    images+=("images/$name")
done
verify_files "${images[@]}" "${tool_files[@]}" metadata/flash-manifest.tsv
sizes=()
index=0
while IFS=$'\t' read -r target file bytes expanded source rest; do
    [ "$index" -lt "${#parts[@]}" ] || die 'extra manifest row'
    part=${parts[$index]}
    expected_target="${part}_b"
    expected_source=a17-payload
    if [ "$index" -ge 42 ]; then expected_source=pixelos-target-files; fi
    if [ "$part" = super ]; then expected_target=super; expected_source=pixelos-super; fi
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
done < metadata/flash-manifest.tsv
[ "$index" -eq 50 ] || die 'incomplete manifest'

# Use the verified bundled tools regardless of PATH or FASTBOOT settings.
tool_dir="$PWD/tools/$platform"
fastboot_bin="$tool_dir/fastboot"
[ -x "$fastboot_bin" ] || die "bundled tool is not executable: $fastboot_bin"
echo "Using bundled Platform Tools: $tool_dir"
"$fastboot_bin" --version
FB_OUTPUT=
fb() {
    local visible=1
    case "$1" in getvar|oem|--version) visible=0 ;; esac
    printf 'fastboot'; printf ' %s' "$@"; printf '\n'
    if [ "$visible" -eq 1 ]; then
        printf 'fastboot' >&3; printf ' %s' "$@" >&3; printf '\n' >&3
    fi
    # Stream stderr/stdout immediately; preserve both pipeline exit statuses.
    local command_status
    local destination=/dev/null
    if [ "$visible" -eq 1 ]; then destination=/dev/fd/3; fi
    if "$fastboot_bin" "$@" 2>&1 | tee "$tmp/command.log" "$destination"; then
        command_status=("${PIPESTATUS[@]}")
    else
        command_status=("${PIPESTATUS[@]}")
    fi
    local rc=${command_status[0]}
    [ "${command_status[1]}" -eq 0 ] || die 'cannot record fastboot output'
    FB_OUTPUT=$(tr -d '\r' < "$tmp/command.log")
    if [ "$rc" -ne 0 ]; then
        if [ "$visible" -eq 0 ]; then cat "$tmp/command.log" >&3; fi
        die "fastboot command failed (exit $rc)"
    fi
    if grep -Eiq '(^|[[:space:]])FAILED([[:space:]:!(]|$)|^fastboot: error:' "$tmp/command.log"; then
        if [ "$visible" -eq 0 ]; then cat "$tmp/command.log" >&3; fi
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
    echo "$part advertised type: $value; format as f2fs only if erase mode is selected"
done
ui '请选择数据处理方式：'
ui '1：清空数据，擦除并格式化 userdata 和 metadata，包括内部存储、应用及加密信息。'
ui '2：保留数据，跳过上述两个分区的擦除和格式化；仍会重写系统与固件。'
ui '保留模式未实机验证，不能保证跨 ROM/版本的数据及加密兼容性。请先备份。'
prompt '输入 1 或 2（其他输入或无输入均取消）： '
data_mode=
if ! IFS= read -r data_mode; then data_mode=; fi
case "$data_mode" in
    1) ui '已选择：清空数据。手机全部用户数据将被删除。' ;;
    2) ui '已选择：保留数据。脚本不会擦除或格式化 userdata 和 metadata。' ;;
    *) ui "已取消，未执行任何刷写、擦除、切槽或重启。日志：$log"; exit 0 ;;
esac
if [ "$data_mode" = 1 ]; then
    verify_files "tools/$platform/make_f2fs" "tools/$platform/make_f2fs_casefold"
    for executable in make_f2fs make_f2fs_casefold; do
        [ -x "$tool_dir/$executable" ] || die "bundled tool is not executable: $tool_dir/$executable"
    done
fi
ui '只有输入小写 yes 并按回车才会按所选模式开始刷写；其他输入或无输入均取消。'
prompt '确认按所选模式刷机？输入 yes： '
confirmation=
if ! IFS= read -r confirmation || [ "$confirmation" != yes ]; then
    ui "已取消，未执行任何刷写、擦除、切槽或重启。日志：$log"
    exit 0
fi
ui '开始刷写，请勿断开连接。'
for part in "${firmware[@]}"; do fb flash "${part}_b" "images/$part.img"; done
fb -S 256M flash super images/super-install-b.img
for part in boot dtbo vendor_boot vbmeta recovery vbmeta_system; do fb flash "${part}_b" "images/$part.img"; done
if [ "$data_mode" = 1 ]; then
    for part in userdata metadata; do
        fb erase "$part"
        fb format:f2fs "$part"
    done
else
    ui '保留数据：已跳过 userdata 和 metadata 的擦除、格式化。'
fi
fb flash init_boot_b images/init_boot.img
fb set_active b
getvar current-slot; [ "$value" = b ] || die 'B slot selection did not take effect'
fb reboot
banner
ui "已完成刷写，已发送重启命令。首次启动请耐心等待。日志：$log"
