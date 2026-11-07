#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.build.date.utc)" = 1790747209 ] \
    || abort "Requires the PixelOS 20260930 global-telephony ROM."
chown -R 0:0 "$MODPATH/system" || abort "Cannot set payload ownership."
find "$MODPATH/system" -type d -exec chmod 0755 {} \;
find "$MODPATH/system" -type f -exec chmod 0644 {} \;
chcon -R u:object_r:system_file:s0 "$MODPATH/system" \
    || abort "Cannot label the overlay."
ui_print "- Fingerprint icon pixel pitch: 60.5833 um/px"
ui_print "- Reboot to apply. Disable and reboot to restore ROM resources."
