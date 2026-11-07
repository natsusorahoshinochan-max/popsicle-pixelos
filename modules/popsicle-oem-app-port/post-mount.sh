#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
MODDIR=${0%/*}
# servicemanager opened its label handle before post-fs-data. A policy load changes
# the SELinux status sequence, making Access::getSehandle reopen the mounted contexts.
/data/adb/ksu/bin/ksud sepolicy apply "$MODDIR/sepolicy.rule" \
    || /system/bin/log -p e -t OemAppPort "OEM App policy reload failed"
if ! "$MODDIR/tools/load-camera-policy.sh"; then
    /system/bin/log -p e -t OemAppPort "Camera policy load failed; camera domain is not validated"
fi
