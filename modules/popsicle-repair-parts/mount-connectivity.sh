#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
MODDIR=$1
STATUS=$MODDIR/connectivity-mount.status
MOUNTED=
fail() {
    for target in $MOUNTED; do
        umount "$target" || /system/bin/log -p e -t PopsicleVpnIngress "Cannot undo bind: $target"
    done
    echo "FAILED: $1" > "$STATUS"
    /system/bin/log -p e -t PopsicleVpnIngress "$1"
    exit 1
}
[ -f "$MODDIR/disable" ] && exit 0
[ -f "$MODDIR/remove" ] && exit 0

# This is a boot-stage operation, never a running-system_server replacement.
if pidof zygote zygote32 zygote64 system_server >/dev/null 2>&1; then
    fail "Zygote or system_server already running; refusing a hot replacement"
fi
for service in zygote zygote_secondary; do
    [ "$(getprop "init.svc.$service")" != running ] \
        || fail "Zygote service already started; refusing a hot replacement"
done
for name in service-connectivity.jar service-connectivity.jar.prof; do
    [ -f "$MODDIR/connectivity/$name" ] || fail "Missing Connectivity payload: $name"
    [ -f "/apex/com.android.tethering/javalib/$name" ] || fail "Missing active APEX file: $name"
done
for name in service-connectivity.jar service-connectivity.jar.prof; do
    source=$MODDIR/connectivity/$name
    target=/apex/com.android.tethering/javalib/$name
    mount -o bind "$source" "$target" || fail "Connectivity bind mount failed: $name"
    MOUNTED="$target $MOUNTED"
    /data/adb/ksu/bin/busybox mount -o remount,bind,ro "$source" "$target" \
        || fail "Cannot make Connectivity bind mount read-only: $name"
done
echo MOUNTED > "$STATUS"
/system/bin/log -p i -t PopsicleVpnIngress "Connectivity candidate mounted before zygote start"
