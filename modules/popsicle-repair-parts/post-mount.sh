#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
MODDIR=${0%/*}
# APEX is active at this stage. Use init's mount namespace before zygote starts;
# replacing the CAPEX would not update the active APEX mount.
exec /system/bin/nsenter -t 1 -m -- /system/bin/sh "$MODDIR/mount-connectivity.sh" "$MODDIR"
