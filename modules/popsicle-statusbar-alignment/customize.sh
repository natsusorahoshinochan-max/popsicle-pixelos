#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.system.build.date.utc)" = "$(cat "$MODPATH/baseline-date")" ] \
    || abort "Requires the matching PixelOS ROM."
(cd "$MODPATH" && sha256sum -c payload.sha256) || abort "Payload checksum failed."
payload=system/product/overlay/PopsicleStatusbarSystemUI.apk
original=/product/overlay/PopsicleStatusbarSystemUI.apk
actual=$(sha256sum "$original")
actual=${actual%% *}
expected=$(cat "$MODPATH/baseline-apk.sha256")
candidate=$(sha256sum "$MODPATH/$payload")
candidate=${candidate%% *}
[ "$actual" = "$expected" ] || [ "$actual" = "$candidate" ] \
    || abort "Installed status bar overlay differs from the supported baseline."
for root in /data/adb/modules /data/adb/modules_update; do
    for other in "$root"/*; do
        [ -d "$other" ] || continue
        [ "${other##*/}" = popsicle-statusbar-alignment ] && continue
        [ -f "$other/disable" ] && continue
        [ -f "$other/remove" ] && continue
        for relative in "$payload" product/overlay/PopsicleStatusbarSystemUI.apk; do
            [ ! -e "$other/$relative" ] || abort "Overlay conflict: ${other##*/}"
            [ ! -e "/data/adb/metamodule/mnt/${other##*/}/$relative" ] \
                || abort "Mounted overlay conflict: ${other##*/}"
        done
    done
done
chown -R 0:0 "$MODPATH/system" || abort "Cannot set ownership."
find "$MODPATH/system" -type d -exec chmod 0755 {} \; || abort "Cannot set directory modes."
find "$MODPATH/system" -type f -exec chmod 0644 {} \; || abort "Cannot set file modes."
context=$(ls -Zd "$original" | awk '{print $1}')
case "$context" in
    u:object_r:*:s0) chcon -R "$context" "$MODPATH/system" || abort "Cannot preserve context." ;;
    *) abort "Cannot read original SELinux context." ;;
esac
ui_print "Status bar alignment trial installed; reboot to activate."
ui_print "Disable this module and reboot to restore the original ROM."
ui_print "ROM integration remains blocked until you confirm device tests pass."
