#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0

[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "This module is for popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Android 17 is required."

# The delivered brightness ROM already includes the native ARR implementation.
# Reuse the old module ID so an upgrade cannot leave two services.jar owners.
base_hash=eb1f669b6e73ac291d21840cfafe1ccfebba594a4b8cd109529f21a6f356f1f1
actual=$(sha256sum /system/framework/services.jar) || abort "Cannot read services.jar."
actual=${actual%% *}
payload=$(sha256sum "$MODPATH/system/framework/services.jar") || abort "Missing services.jar."
payload=${payload%% *}
[ "$actual" = "$base_hash" ] || [ "$actual" = "$payload" ] \
    || abort "Requires the matching PixelOS brightness ROM; unknown services.jar."

for root in /data/adb/modules /data/adb/modules_update; do
    for candidate in "$root"/*; do
        [ -d "$candidate" ] || continue
        [ "${candidate##*/}" = popsicle-arr ] && continue
        [ -f "$candidate/disable" ] && continue
        [ -f "$candidate/remove" ] && continue
        [ ! -f "$candidate/system/framework/services.jar" ] \
            || abort "Another module replaces services.jar: ${candidate##*/}"
    done
done

# Verify the actual framework payload and its precompiled companions together.
(cd "$MODPATH" && sha256sum -c payload.sha256) || abort "Payload checksum mismatch."
# Match the existing PixelOS module permission setup across installer versions.
chown -R 0:0 "$MODPATH/system" || abort "Cannot set ownership."
find "$MODPATH/system" -type d -exec chmod 0755 {} + || abort "Cannot set directory modes."
find "$MODPATH/system" -type f -exec chmod 0644 {} + || abort "Cannot set file modes."
ui_print "ARR remains integrated in this matching ROM and framework."
ui_print "Brightness startup correction installed; reboot to activate."
ui_print "Disable popsicle-arr and reboot to restore the ROM framework."
