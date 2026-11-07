#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.system.build.date.utc)" = "$(cat "$MODPATH/baseline-date")" ] \
    || abort "Requires the matching PixelOS baseline."
[ -z "$(getprop ro.vendor.qti.va_aosp.support)" ] \
    || abort "Restore the original platform property and reboot before installing."
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
while read -r relative original expected label; do
    live=/${relative#system/}
    actual=$(sha256sum "$live" | awk '{print $1}')
    [ "$actual" = "$original" ] || [ "$actual" = "$expected" ] \
        || abort "Unsupported active file: $live"
    [ "$(sha256sum "$MODPATH/$relative" | awk '{print $1}')" = "$expected" ] \
        || abort "Candidate checksum mismatch: $relative"
    for root in /data/adb/modules /data/adb/modules_update; do
        for candidate in "$root"/*; do
            [ -d "$candidate" ] || continue
            [ "${candidate##*/}" = popsicle-audio-fixes ] && continue
            [ -f "$candidate/disable" ] && continue
            [ -f "$candidate/remove" ] && continue
            [ ! -e "$candidate/$relative" ] && [ ! -e "$candidate/${relative#system/}" ] \
                || abort "Payload conflict: ${candidate##*/}"
            if [ -f "$candidate/system.prop" ] && grep -q '^ro.vendor.qti.va_aosp.support=' "$candidate/system.prop"; then
                abort "Audio platform property conflict: ${candidate##*/}"
            fi
        done
    done
    context=$(ls -Zd "$live" | awk '{print $1}')
    [ "$context" = "u:object_r:$label:s0" ] || abort "Unexpected label: $live"
    chcon "$context" "$MODPATH/$relative" || abort "Cannot label: $relative"
done < "$MODPATH/payload-manifest.txt"
ui_print "Audio candidate installed. Reboot to activate; user recordings are preserved."
ui_print "Disable popsicle-audio-fixes and reboot to restore the baseline."
