#!/system/bin/sh
# Capture stock algorithm-node buffers; never patch sensor binaries or modes.
# Run as root on popsicle: sh SCRIPT capture /data/local/tmp/popsicle-raw-NAME [seconds]
# Emergency recovery: sh SCRIPT restore /data/local/tmp/popsicle-raw-NAME
set -u
umask 077
action=${1:-}
dir=${2:-}
seconds=${3:-180}
case "$action" in capture|restore) ;; *) echo 'Expected capture or restore' >&2; exit 2 ;; esac
case "$dir" in /data/local/tmp/popsicle-raw-*) ;; *) echo 'Invalid output directory' >&2; exit 2 ;; esac
name=${dir#/data/local/tmp/}
case "$name" in *[!a-zA-Z0-9_-]*) echo 'Invalid output name' >&2; exit 2 ;; esac
[ "$(id -u)" = 0 ] || { echo 'Root is required' >&2; exit 1; }
[ "$(getprop ro.product.device)" = popsicle ] || { echo 'Expected popsicle' >&2; exit 1; }
lock=/data/local/tmp/popsicle-raw-capture.lock
keys='persist.vendor.camera.REMOSAIC.debug
persist.vendor.camera.algoengine.chioffline.dump
persist.vendor.algoengine.extendbuffer.dump
cam.app.debug.dump.metadata
cam.app.debug.dump.metadata2file'

restart_provider() {
    setprop ctl.restart vendor.camera-provider || return 1
    sleep 2
    count=0
    while [ "$count" -lt 15 ]; do
        if [ "$(getprop init.svc.vendor.camera-provider)" = running ] &&
                pidof vendor.qti.camera.provider-service_64 >/dev/null; then
            return 0
        fi
        sleep 1
        count=$((count + 1))
    done
    echo 'Camera provider did not restart' >&2
    return 1
}

restore_properties() {
    result=0
    for key in $keys; do
        [ -f "$dir/properties/$key" ] || { echo "Missing saved property: $key" >&2; return 1; }
    done
    am force-stop com.android.camera || result=1
    for key in $keys; do
        value=$(cat "$dir/properties/$key")
        setprop "$key" "$value" || result=1
    done
    restart_provider || result=1
    return "$result"
}

if [ "$action" = restore ]; then
    [ -d "$dir" ] && [ ! -L "$dir" ] || exit 1
    if [ -f "$lock/owner" ]; then
        read -r owner owned_dir < "$lock/owner"
        if kill -0 "$owner" 2>/dev/null; then
            echo "Capture is running; request completion with: touch $owned_dir/stop" >&2
            exit 1
        fi
        [ "$owned_dir" = "$dir" ] || { echo 'Another capture owns the lock' >&2; exit 1; }
    fi
    trap '' INT TERM HUP
    restore_properties || exit 1
    echo restored > "$dir/recovery.txt"
    if [ -f "$lock/owner" ]; then rm "$lock/owner"; rmdir "$lock"; fi
    echo 'Saved camera properties restored.'
    exit 0
fi

case "$seconds" in ''|*[!0-9]*) exit 2 ;; esac
[ "$seconds" -ge 30 ] && [ "$seconds" -le 300 ] || exit 2
[ "$(getprop init.svc.vendor.camera-provider)" = running ] || { echo 'Camera provider is not running' >&2; exit 1; }
old_debug=$(getprop persist.vendor.camera.REMOSAIC.debug)
case "$old_debug" in *[!0-9]*) echo 'Unexpected remosaic debug value' >&2; exit 1 ;; esac
debug_value=${old_debug:-0}
# Parse decimal explicitly; a property such as 08 is not shell octal.
debug_value=$(printf '%s\n' "$debug_value" | sed 's/^0*//')
debug_value=${debug_value:-0}
[ "${#debug_value}" -le 9 ] || exit 2
[ "$((debug_value & 4))" -eq 0 ] || { echo 'Existing remosaic bypass is enabled; restore your baseline first' >&2; exit 1; }
mkdir "$lock" || { echo 'Capture lock exists; finish or recover the previous capture first' >&2; exit 1; }
if ! mkdir "$dir"; then rmdir "$lock"; exit 1; fi
printf '%s %s\n' "$$" "$dir" > "$lock/owner"
armed=0
log_pid=
reason=setup_error

collect_files() {
    : > "$dir/files.txt"
    for base in /sdcard/DCIM/Camera /data/vendor/camera; do
        [ -d "$base" ] || continue
        find "$base" -type f -newer "$dir/start" \( \
            -name '*RemosaicPlugin*' -o -name '*FormatConvertor*' -o \
            -name '*EhdrDecompandPlugin*' \) -print >> "$dir/files.txt" || return 1
    done
    base=/sdcard/DCIM/Camera
    if [ -d "$base" ]; then
        find "$base" -type f -newer "$dir/start" \( -iname '*.dng' -o -iname '*.jpg' -o -iname '*.jpeg' \
            -o -iname '*.heic' -o -iname '*.heif' \) \
            -print >> "$dir/files.txt" || return 1
    fi
    sort -u "$dir/files.txt" > "$dir/files.sorted"
    mv "$dir/files.sorted" "$dir/files.txt"
    base=/sdcard/Android/data/com.android.camera/cache/debug/memory/meta
    if [ -d "$base" ]; then
        find "$base" -type f -newer "$dir/start" -print >> "$dir/files.txt" || return 1
    fi
    sed 's@^/@@' "$dir/files.txt" > "$dir/archive-files.txt"
    find "$dir" -type f ! -name 'capture.tar.gz' ! -name 'archive-files.txt' -print |
        sed 's@^/@@' >> "$dir/archive-files.txt"
    tar -czf "$dir/capture.tar.gz" -C / -T "$dir/archive-files.txt"
}

cleanup() {
    exit_status=$?
    trap - EXIT
    trap '' INT TERM HUP
    if [ "$armed" = 1 ]; then
        if restore_properties > "$dir/restore.log" 2>&1; then
            echo restored > "$dir/recovery.txt"
        else
            echo restore_failed > "$dir/recovery.txt"
            echo "Restore failed. Run: sh $0 restore $dir" >&2
            exit_status=1
        fi
    fi
    if [ -n "$log_pid" ]; then
        kill "$log_pid" 2>/dev/null || :
        wait "$log_pid" 2>/dev/null || :
    fi
    printf 'reason=%s\nexit=%s\n' "$reason" "$exit_status" > "$dir/status.txt"
    archived=0
    if [ -f "$dir/start" ]; then
        if collect_files; then
            archived=1
        else
            echo 'Archiving failed; source dumps are retained. Do not use the partial archive.' >&2
            exit_status=1
            printf 'reason=archive_failed\nexit=1\n' > "$dir/status.txt"
        fi
    fi
    if [ "$armed" = 0 ] || [ "$(cat "$dir/recovery.txt")" = restored ]; then
        rm "$lock/owner"
        rmdir "$lock"
    fi
    if [ "$archived" = 1 ]; then
        echo "Capture archive: $dir/capture.tar.gz ($reason; exit=$exit_status)"
    else
        echo "Capture stopped without a complete archive: $dir (exit=$exit_status)" >&2
    fi
    exit "$exit_status"
}
trap cleanup EXIT
trap 'reason=signal; exit 130' INT TERM HUP
mkdir "$dir/properties" || exit 1
for key in $keys; do getprop "$key" > "$dir/properties/$key" || exit 1; done
{
    getprop ro.build.fingerprint
    getprop ro.system.build.fingerprint
    getprop ro.product.build.fingerprint
    getprop ro.boot.slot_suffix
    getenforce
} > "$dir/device.txt"
dumpsys media.camera > "$dir/camera-before.txt" 2>&1 || exit 1
am force-stop com.android.camera || exit 1
touch "$dir/start" || exit 1
armed=1
setprop persist.vendor.camera.REMOSAIC.debug "$((debug_value | 2))" || exit 1
setprop persist.vendor.camera.algoengine.chioffline.dump 1 || exit 1
setprop persist.vendor.algoengine.extendbuffer.dump 1 || exit 1
setprop cam.app.debug.dump.metadata 7 || exit 1
setprop cam.app.debug.dump.metadata2file true || exit 1
restart_provider > "$dir/restart.log" 2>&1 || exit 1
logcat -v threadtime -T 1 -s CamX CHI MiCamAlgoEng RemosaicPlugin EhdrDecompandPlugin \
    > "$dir/camera.log" 2>&1 &
log_pid=$!
echo "READY: open Xiaomi Camera and take the requested photos within $seconds seconds."
echo "Early finish: touch $dir/stop"
deadline=$(($(date +%s) + seconds))
reason=deadline
while [ "$(date +%s)" -lt "$deadline" ]; do
    if [ -e "$dir/stop" ]; then reason=requested_stop; break; fi
    free_kb=$(df -Pk /data | awk 'END { print $4 }')
    case "$free_kb" in ''|*[!0-9]*) reason=storage_query_failed; exit 1 ;; esac
    if [ "$free_kb" -lt 4194304 ]; then reason=low_space; exit 1; fi
    sleep 2
done
dumpsys media.camera > "$dir/camera-after.txt" 2>&1 || exit 1
exit 0
