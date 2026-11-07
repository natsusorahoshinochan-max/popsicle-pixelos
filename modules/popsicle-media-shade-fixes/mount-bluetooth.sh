#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
MODDIR=$1
TARGET=/apex/com.android.bt/lib64/libbluetooth_jni.so
SOURCE=$MODDIR/bluetooth/libbluetooth_jni.so
STATUS=$MODDIR/bluetooth-mount.status
fail() {
    echo "FAILED: $1" > "$STATUS"
    /system/bin/log -p e -t PixelOSMediaShade "$1"
    exit 1
}
[ -f "$MODDIR/disable" ] && exit 0
[ -f "$MODDIR/remove" ] && exit 0
# Never hot-swap a library used by an already running Bluetooth process.
if pidof com.android.bluetooth >/dev/null 2>&1; then
    fail "Bluetooth already running; boot-time binding was not performed"
fi
mount -o bind "$SOURCE" "$TARGET" || fail "Bluetooth bind mount failed"
if ! /data/adb/ksu/bin/busybox mount -o remount,bind,ro "$SOURCE" "$TARGET"; then
    umount "$TARGET"
    fail "Cannot make Bluetooth bind mount read-only"
fi
echo "MOUNTED" > "$STATUS"
/system/bin/log -p i -t PixelOSMediaShade "Source-built Bluetooth candidate mounted before process start"
