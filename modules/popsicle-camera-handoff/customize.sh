#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label payload."
while IFS= read -r path; do
    original=/${path#system/}
    context=$(ls -Zd "$original" | awk '{print $1}')
    case "$context" in
        u:object_r:*:s0) chcon "$context" "$MODPATH/$path" \
            || abort "Cannot preserve context: $path" ;;
        *) abort "Cannot read original context: $path" ;;
    esac
done < "$MODPATH/payload-files.txt"
ui_print "Camera screen handoff repair installed; reboot to activate."
ui_print "Disable popsicle-camera-handoff and reboot to restore the ROM camera."
