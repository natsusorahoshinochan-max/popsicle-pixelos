#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.system.build.date.utc)" = 1790954511 ] \
    || abort "Requires the PixelOS 20261002 seven-fixes ROM delivered on October 3."

for root in /data/adb/modules /data/adb/modules_update; do
    for candidate in "$root"/*; do
        [ -d "$candidate" ] || continue
        [ "${candidate##*/}" = popsicle_color_modes ] && continue
        [ -f "$candidate/disable" ] && continue
        [ -f "$candidate/remove" ] && continue
        while IFS= read -r path; do
            [ ! -e "$candidate/$path" ] \
                || abort "Conflicting payload in ${candidate##*/}: $path. Disable it and reboot."
        done < "$MODPATH/payload-files.txt"
    done
done

set_perm_recursive "$MODPATH/system" 0 0 0755 0644
while IFS= read -r path; do
    [ -f "$MODPATH/$path" ] || abort "Missing payload: $path"
    [ -f "/$path" ] || abort "Missing matching ROM file: /$path"
    context=$(ls -Zd "/$path" | awk '{print $1}')
    case "$context" in
        u:object_r:*:s0) chcon "$context" "$MODPATH/$path" \
            || abort "Cannot preserve context: $path" ;;
        *) abort "Cannot read original context: $path" ;;
    esac
done < "$MODPATH/payload-files.txt"
set_perm "$MODPATH/system/bin/surfaceflinger" 0 2000 0755 \
    u:object_r:surfaceflinger_exec:s0 \
    || abort "Cannot set SurfaceFlinger permissions and execution context."
ui_print "Installed color mode repair. Reboot to activate."
ui_print "Natural and Boosted use main-panel SDR sRGB correction; Saturated retains native output."
ui_print "Disable this module and reboot to restore the ROM files."
