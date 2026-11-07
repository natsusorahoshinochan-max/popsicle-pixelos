#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.build.date.utc)" = 1791924330 ] \
    || abort "Requires the 20261014 navigation ROM."

apk=/system_ext/priv-app/Settings/Settings.apk
active=$(cmd package path com.android.settings) || abort "Cannot locate Settings."
[ "$active" = "package:$apk" ] \
    || abort "Restore the ROM's system Settings before installing."

for root in /data/adb/modules /data/adb/modules_update; do
    for module in "$root"/*; do
        [ -d "$module" ] || continue
        [ "${module##*/}" = popsicle-storage-accounting ] && continue
        if [ -f "$module/disable" ] || [ -f "$module/remove" ]; then continue; fi
        for relative in system/system_ext/priv-app/Settings system_ext/priv-app/Settings; do
            [ ! -e "$module/$relative" ] \
                || abort "Disable overlapping module ${module##*/} and reboot first."
        done
    done
done

actual=$(sha256sum "$apk") || abort "Cannot read Settings baseline."
actual=${actual%% *}
baseline=$(cat "$MODPATH/baseline-apk.sha256") || abort "Missing baseline digest."
candidate=$(cat "$MODPATH/candidate-apk.sha256") || abort "Missing candidate digest."
[ "$actual" = "$baseline" ] || [ "$actual" = "$candidate" ] \
    || abort "Unsupported Settings APK. Disable covering modules and reboot; requires the 20261014 ROM."

payload=$MODPATH/system/system_ext/priv-app/Settings/Settings.apk
packed=$(sha256sum "$payload") || abort "Cannot read module Settings."
[ "${packed%% *}" = "$candidate" ] || abort "Module APK is incomplete or corrupt."

# Hide the previous APK's compiled code. ART compiles this signed, dex-bearing
# APK normally in /data; no compiler or signature checks are disabled.
REPLACE="/system/system_ext/priv-app/Settings/oat"
mkdir -p "$MODPATH/system/system_ext/priv-app/Settings/oat" \
    || abort "Cannot prepare Settings oat directory."
set_perm_recursive "$MODPATH/system" 0 0 0755 0644 \
    || abort "Cannot set module permissions."
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label module payload."
context=$(ls -Zd "$apk" | awk '{print $1}')
case "$context" in
    u:object_r:*:s0) chcon "$context" "$payload" || abort "Cannot preserve Settings context." ;;
    *) abort "Cannot read Settings SELinux context." ;;
esac
ui_print "Installed for the 20261014 navigation ROM. Reboot to apply."
ui_print "Open Settings > Storage and allow the storage calculation to finish."
ui_print "The capacity can exceed 512 GB because actual storage size is used."
