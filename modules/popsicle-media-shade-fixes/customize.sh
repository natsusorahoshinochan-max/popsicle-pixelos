#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
set_perm_recursive "$MODPATH/bluetooth" 0 0 0755 0644
set_perm "$MODPATH/post-mount.sh" 0 0 0755
set_perm "$MODPATH/mount-bluetooth.sh" 0 0 0755
chcon u:object_r:system_lib_file:s0 "$MODPATH/bluetooth/libbluetooth_jni.so" \
    || abort "Cannot preserve Bluetooth library context."
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label payload."
while IFS= read -r path; do
    context=$(ls -Zd "/${path#system/}" | awk '{print $1}')
    case "$context" in
        u:object_r:*:s0) chcon "$context" "$MODPATH/$path" || abort "Cannot preserve context: $path" ;;
        *) abort "Cannot read original context: $path" ;;
    esac
done < "$MODPATH/payload-files.txt"
ui_print "Candidate installed. Reboot to activate SystemUI and the source-built Bluetooth library."
ui_print "Disable popsicle-media-shade-fixes and reboot to return to the ROM baseline."
