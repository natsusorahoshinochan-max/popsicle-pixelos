#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
MODDIR=${0%/*}
# APEX activation precedes KernelSU overlays on this ROM. Bind in init's mount
# namespace before zygote/Bluetooth start; do not replace the CAPEX after activation.
exec /system/bin/nsenter -t 1 -m -- /system/bin/sh "$MODDIR/mount-bluetooth.sh" "$MODDIR"
