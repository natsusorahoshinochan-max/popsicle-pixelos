#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.build.date.utc)" = 1791303107 ] || abort "Requires the 20261007 four-fixes ROM."
for root in /data/adb/modules /data/adb/modules_update; do
    for module in "$root"/*; do
        [ -d "$module" ] || continue
        [ "${module##*/}" = popsicle-rear-personalization ] && continue
        if [ -f "$module/disable" ] || [ -f "$module/remove" ]; then continue; fi
        for path in system_ext/priv-app/Settings/Settings.apk system_ext/app/PopsicleSubscreenCenter/PopsicleSubscreenCenter.apk; do
            if [ -f "$module/system/$path" ] || [ -f "$module/$path" ] \
                || { [ -f "$module/payload-files.txt" ] && grep -F -q "$path" "$module/payload-files.txt"; }; then
                abort "Disable overlapping module ${module##*/} and reboot first."
            fi
        done
    done
done
while read -r expected path; do
    actual=$(sha256sum "/$path") || abort "Cannot read ROM baseline $path"
    actual=${actual%% *}
    if [ "$actual" != "$expected" ]; then
        candidate=$(awk -v path="$path" '$2 == path {print $1}' "$MODPATH/candidate-apks.sha256")
        previous=$(awk -v path="$path" '$2 == path {print $1}' "$MODPATH/previous-apks.sha256")
        if [ "$actual" != "$candidate" ] && [ "$actual" != "$previous" ]; then
            abort "Unsupported APK: $path. Disable other covering modules and reboot; requires the 20261007 ROM."
        fi
    fi
done < "$MODPATH/baseline-apks.sha256"
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label system payload."
ui_print "Rear personalization installed. Reboot, then open Settings > Display > Rear display."
ui_print "No framework or SELinux policy is replaced. Disable and reboot to restore the ROM apps."
