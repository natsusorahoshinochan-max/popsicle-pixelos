#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
# Compile and validate at packaging time; KernelSU waits only 10 seconds here.
set -eu
umask 077
POLICY_TOOLS=${0%/*}
POLICY_CURRENT=$(mktemp /data/adb/popsicle-camera-policy.XXXXXX)
trap 'rm -f "$POLICY_CURRENT"' EXIT
trap 'exit 1' HUP INT TERM
cat /sys/fs/selinux/policy > "$POLICY_CURRENT"
cmp -s "$POLICY_CURRENT" "$POLICY_TOOLS/policy-baseline.bin" || {
    echo "Live policy differs from the validated baseline; camera policy not loaded" >&2
    exit 1
}
/system/bin/load_policy "$POLICY_TOOLS/camera-policy.bin"
/system/bin/log -p i -t OemAppPort "Loaded validated camera policy on matching live baseline"
