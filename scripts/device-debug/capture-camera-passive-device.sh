#!/system/bin/sh
# Passive stock-camera metadata/log capture. Run detached on the device.
# Usage: sh SCRIPT NEW_OUTPUT_DIRECTORY TAG_FILE SECONDS
# Request early completion by creating OUTPUT_DIRECTORY/stop.
set -u
dir=${1:?output directory required}
tags_file=${2:?tag file required}
seconds=${3:?duration required}
case "$dir" in /data/local/tmp/popsicle-camera-*) ;; *) exit 2 ;; esac
case "$seconds" in ''|*[!0-9]*) exit 2 ;; esac
[ "$seconds" -ge 1 ] && [ "$seconds" -le 3600 ] || exit 2
[ -r "$tags_file" ] || exit 2
tags=$(cat "$tags_file")
case "$tags" in ''|*[!a-zA-Z0-9_.,]*) exit 2 ;; esac
umask 077
mkdir "$dir" || exit 2
reason=setup_error
watch_pid=
log_pid=
watch_owned=0
feed_started=0
started=$(date +%s)
state() {
    {
        echo "owner=$$"
        echo "watch_pid=$watch_pid"
        echo "log_pid=$log_pid"
        echo "started=$started"
        echo "updated=$(date +%s)"
        echo "deadline=$((started + seconds))"
        echo "status=$1"
        echo "provider=$(pidof vendor.qti.camera.provider-service_64)"
        echo "cameraserver=$(pidof cameraserver)"
    } > "$dir/state.tmp"
    mv "$dir/state.tmp" "$dir/state.txt"
}
cleanup() {
    trap - EXIT INT TERM
    # CameraService's live observer accepts newline on its input FD.
    # Its output remains a regular file through cleanup, never a host pipe.
    if [ "$feed_started" = 1 ]; then touch "$dir/feed-stop"; fi
    if [ -n "$watch_pid" ]; then
        n=0
        while kill -0 "$watch_pid" 2>/dev/null && [ "$n" -lt 10 ]; do
            sleep 1
            n=$((n + 1))
        done
        if kill -0 "$watch_pid" 2>/dev/null; then
            echo "watch_exit_timeout" >> "$dir/cleanup.txt"
            kill "$watch_pid" 2>/dev/null || :
        fi
        wait "$watch_pid"
        echo "watch_exit=$?" >> "$dir/cleanup.txt"
    fi
    if [ -n "$log_pid" ]; then
        kill "$log_pid" 2>/dev/null || :
        wait "$log_pid"
        echo "log_exit=$?" >> "$dir/cleanup.txt"
    fi
    if [ "$watch_owned" = 1 ]; then
        cmd media.camera watch stop > "$dir/watch-stop.txt" 2>&1
        echo "watch_stop_exit=$?" >> "$dir/cleanup.txt"
    fi
    state "$reason"
}
trap cleanup EXIT
trap 'reason=signal; exit 130' INT TERM
cat /proc/sys/kernel/random/boot_id > "$dir/boot-id.txt"
getprop ro.boot.slot_suffix > "$dir/slot.txt"
cmd media.camera watch dump > "$dir/watch-before.txt" 2>&1 || exit 1
if [ "$(cat "$dir/watch-before.txt")" != 'No monitoring information to print.' ]; then
    reason=existing_monitor
    exit 1
fi
cp "$tags_file" "$dir/tags.txt" || exit 1
cmd media.camera watch start -m "$tags" -c com.android.camera > "$dir/watch-start.txt" 2>&1 || exit 1
watch_owned=1
logcat -b all -v threadtime -T 1 > "$dir/live.log" 2> "$dir/log-error.txt" &
log_pid=$!
# Use an anonymous pipe: cameraserver may read shell pipes but not a named
# shell_data_file FIFO. The feeder exits on owner death or a stop marker.
sh -c '
    echo $$ > "$1/feed.pid"
    while [ ! -e "$1/feed-stop" ] && kill -0 "$2" 2>/dev/null; do sleep 1; done
    printf "\\n"
' camera-watch-feed "$dir" "$$" | cmd media.camera watch live > "$dir/watch-live.txt" 2> "$dir/watch-error.txt" &
watch_pid=$!
feed_started=1
state running
while :; do
    if [ -e "$dir/stop" ]; then reason=requested_stop; break; fi
    if ! kill -0 "$watch_pid" 2>/dev/null || ! kill -0 "$log_pid" 2>/dev/null; then
        reason=child_exit
        break
    fi
    if [ "$(date +%s)" -ge "$((started + seconds))" ]; then reason=deadline; break; fi
    log_bytes=$(stat -c %s "$dir/live.log")
    watch_bytes=$(stat -c %s "$dir/watch-live.txt")
    if [ "$((log_bytes + watch_bytes))" -ge 1073741824 ]; then reason=size_limit; break; fi
    state running
    sleep 5
done
