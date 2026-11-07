#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.build.date.utc)" = 1790954511 ] \
    || abort "Requires the PixelOS 20261002 seven-fixes ROM."

for root in /data/adb/modules /data/adb/modules_update; do
    for candidate in "$root"/*; do
        [ -d "$candidate" ] || continue
        [ "${candidate##*/}" = popsicle_nr_registration ] && continue
        [ -f "$candidate/disable" ] && continue
        [ -f "$candidate/remove" ] && continue
        while read -r source target mode; do
            if [ -e "$candidate$target" ] || [ -e "$candidate/system$target" ]; then
                abort "Conflicting module: ${candidate##*/} replaces $target. Disable it and reboot first."
            fi
        done < "$MODPATH/payload-map.tsv"
    done
done

set_perm_recursive "$MODPATH/system" 0 0 0755 0644
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label payload."
while read -r source target mode; do
    [ -f "$MODPATH/$source" ] || abort "Missing payload: $source"
    context=$(ls -ZdL "$target" | awk '{print $1}')
    case "$context" in
        u:object_r:*:s0)
            set_perm "$MODPATH/$source" 0 0 "$mode"
            chcon "$context" "$MODPATH/$source" || abort "Cannot preserve context: $target" ;;
        *) abort "Cannot read original context: $target" ;;
    esac
done < "$MODPATH/payload-map.tsv"
ui_print "Popsicle NR_CA registration compatibility installed."
ui_print "Reboot to activate. The first boot may take longer for ART recompilation."
ui_print "Disable this module and reboot to restore the ROM."
