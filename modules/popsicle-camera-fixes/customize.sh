#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.system.build.date.utc)" = "$(cat "$MODPATH/baseline-date")" ] \
    || abort "This incremental payload requires its matching PixelOS ROM."
for root in /data/adb/modules /data/adb/modules_update; do
    for candidate in "$root"/*; do
        [ -d "$candidate" ] || continue
        [ "${candidate##*/}" = popsicle-camera-fixes ] && continue
        [ -f "$candidate/disable" ] && continue
        [ -f "$candidate/remove" ] && continue
        while IFS= read -r path; do
            [ ! -e "$candidate/$path" ] || abort "Payload conflict with ${candidate##*/}: $path"
        done < "$MODPATH/payload-files.txt"
    done
done
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
set_perm "$MODPATH/system/bin/cameraserver" 0 2000 0755
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label payload."
while IFS= read -r path; do
    [ -e "/$path" ] || continue
    context=$(ls -Zd "/$path" | awk '{print $1}')
    case "$context" in
        u:object_r:*:s0) chcon "$context" "$MODPATH/$path" \
            || abort "Cannot preserve context: $path" ;;
        *) abort "Cannot read context: $path" ;;
    esac
done < "$MODPATH/payload-files.txt"
ui_print "Camera buffer and default gallery repair installed; reboot to activate."
ui_print "Disable popsicle-camera-fixes and reboot to restore the ROM payload."
