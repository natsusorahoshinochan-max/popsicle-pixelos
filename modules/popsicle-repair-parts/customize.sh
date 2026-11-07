#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.build.date.utc)" = 1790747209 ] \
    || abort "Requires the PixelOS 20260930 global-telephony ROM."
module_id=$(sed -n 's/^id=//p' "$MODPATH/module.prop")

# Detect both standard system/system_ext and older direct system_ext payloads.
# Ignore this module's previous installation so an ordinary upgrade is possible.
for root in /data/adb/modules /data/adb/modules_update; do
    for candidate in "$root"/*; do
        [ -d "$candidate" ] || continue
        [ "${candidate##*/}" = "$module_id" ] && continue
        [ -f "$candidate/disable" ] && continue
        [ -f "$candidate/remove" ] && continue
        case "$module_id:${candidate##*/}" in
            popsicle_brightness_event_order:popsicle_vpn_ingress_owner|\
            popsicle_vpn_ingress_owner:popsicle_brightness_event_order)
                abort "Brightness and VPN modules must be tested separately; disable the other module and reboot." ;;
        esac
        while read -r source target mode; do
            if [ -e "$candidate$target" ] || [ -e "$candidate/system$target" ]; then
                abort "Another module replaces $target: ${candidate##*/}. Disable it and reboot."
            fi
        done < "$MODPATH/payload-map.tsv"
    done
done

set_perm_recursive "$MODPATH/system" 0 0 0755 0644
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label system payload."
if [ -d "$MODPATH/connectivity" ]; then
    [ -x /system/bin/nsenter ] || abort "nsenter is required for early APEX mounting."
    [ -x /data/adb/ksu/bin/busybox ] || abort "KernelSU BusyBox is required."
    set_perm_recursive "$MODPATH/connectivity" 0 0 0755 0644
    set_perm "$MODPATH/post-mount.sh" 0 0 0755
    set_perm "$MODPATH/mount-connectivity.sh" 0 0 0755
fi
while read -r source target mode; do
    [ -f "$MODPATH/$source" ] || abort "Missing payload: $source"
    context=$(ls -Zd "$target" | awk '{print $1}')
    case "$context" in
        u:object_r:*:s0)
            set_perm "$MODPATH/$source" 0 0 "$mode"
            chcon "$context" "$MODPATH/$source" || abort "Cannot preserve context: $target" ;;
        *) abort "Cannot read original context: $target" ;;
    esac
done < "$MODPATH/payload-map.tsv"

case "$module_id" in
    popsicle_brightness_event_order|popsicle_vpn_ingress_owner)
        ui_print "Brightness and VPN modules are mutually exclusive; never enable both."
        ui_print "Disable the other module and reboot before installing or enabling this one." ;;
esac
ui_print "Installed $module_id. Reboot to activate this independent ROM repair."
ui_print "Disable this module and reboot to restore the matching ROM files."
