#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.build.fingerprint)" = 'Xiaomi/custom_popsicle/popsicle:17/CP2A.260605.016/eng.root:user/test-keys' ] \
    || abort "Requires the matching PixelOS build."
expected_date=1789233999
[ ! -f "$MODPATH/native-rom" ] || expected_date=$(cat "$MODPATH/native-rom")
[ "$(getprop ro.system.build.date.utc)" = "$expected_date" ] \
    || abort "Installed ROM build date does not match the tested baseline."
for root in /data/adb/modules /data/adb/modules_update; do
    for candidate in "$root"/*; do
        [ -d "$candidate" ] || continue
        [ "${candidate##*/}" = popsicle-oem-app-port ] && continue
        [ -f "$candidate/disable" ] && continue
        [ -f "$candidate/remove" ] && continue
        for path in system/framework/framework.jar system/framework/services.jar \
            system/framework/framework-res.apk system/system_ext/priv-app/SystemUI/SystemUI.apk; do
            [ ! -e "$candidate/$path" ] || abort "Conflicting runtime owner: ${candidate##*/}"
        done
    done
done
chown -R 0:0 "$MODPATH/system" || abort "Cannot set ownership."
find "$MODPATH/system" -type d -exec chmod 0755 {} + || abort "Cannot set directory modes."
find "$MODPATH/system" -type f -exec chmod 0644 {} + || abort "Cannot set file modes."
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label runtime files."
if [ -d "$MODPATH/system/vendor/etc/displayconfig" ]; then
    chcon -R u:object_r:vendor_configs_file:s0 "$MODPATH/system/vendor/etc/displayconfig" \
        || abort "Cannot label the physical display layout."
fi
for path in system/lib64 system/system_ext/lib64; do
    [ ! -d "$MODPATH/$path" ] || chcon -R u:object_r:system_lib_file:s0 "$MODPATH/$path" \
        || abort "Cannot label native libraries."
done
while IFS= read -r path; do
    case "$path" in
        system/*) local_path="$MODPATH/$path" ;;
        *) local_path="$MODPATH/system/$path" ;;
    esac
    [ ! -e "/$path" ] || chcon --reference="/$path" "$local_path" \
        || abort "Cannot preserve context for /$path"
done < "$MODPATH/payload-files.txt"
chown 0:0 "$MODPATH/system/bin/installd" || abort "Cannot own installd."
chmod 0755 "$MODPATH/system/bin/installd" || abort "Cannot make installd executable."
# Preserve the installed executable label after applying ownership and mode.
chcon --reference=/system/bin/installd "$MODPATH/system/bin/installd" \
    || abort "Cannot preserve installd executable context."
if [ ! -f "$MODPATH/native-rom" ]; then
    set_perm "$MODPATH/post-mount.sh" 0 0 0755
    set_perm "$MODPATH/tools/load-camera-policy.sh" 0 0 0755
    set_perm "$MODPATH/tools/policy-export" 0 0 0755
fi
ui_print "Original camera/rear APKs and matching runtime payload installed."
ui_print "SELinux stays enforcing. Property label limitations remain visible in logs."
ui_print "Disable popsicle-oem-app-port and reboot to restore the installed ROM."
