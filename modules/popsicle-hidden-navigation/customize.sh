#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.build.date.utc)" = 1791303107 ] || abort "Requires the 20261007 four-fixes ROM."

for root in /data/adb/modules /data/adb/modules_update; do
    for module in "$root"/*; do
        [ -d "$module" ] || continue
        [ "${module##*/}" = popsicle-hidden-navigation ] && continue
        if [ -f "$module/disable" ] || [ -f "$module/remove" ]; then continue; fi
        while IFS= read -r path; do
            relative=${path#system/}
            if [ -f "$module/$path" ] || [ -f "$module/$relative" ] \
                || { [ -f "$module/payload-files.txt" ] && grep -F -x -q "$path" "$module/payload-files.txt"; }; then
                abort "Disable overlapping module ${module##*/} before installing."
            fi
        done < "$MODPATH/payload-files.txt"
    done
done

launcher_path=$(cmd package path com.google.android.apps.nexuslauncher) \
    || abort "Cannot locate Pixel Launcher."
[ "$launcher_path" = "package:/system_ext/priv-app/NexusLauncherRelease/NexusLauncherRelease.apk" ] \
    || abort "Requires the ROM's original Pixel Launcher. Restore it before installing."

while read -r expected path; do
    actual=$(sha256sum "/$path") || abort "Cannot read ROM baseline $path"
    actual=${actual%% *}
    if [ "$actual" != "$expected" ]; then
        candidate=$(awk -v path="$path" '$2 == path {print $1}' "$MODPATH/candidate-files.sha256")
        previous=$(awk -v path="$path" '$2 == path {print $1}' "$MODPATH/rear-v02-files.sha256")
        if [ "$actual" != "$candidate" ] && [ "$actual" != "$previous" ]; then
            abort "Unsupported ROM file: $path. Disable covering modules and reboot; requires the 20261007 ROM."
        fi
    fi
done < "$MODPATH/baseline-files.sha256"

set_perm_recursive "$MODPATH/system" 0 0 0755 0644
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label system payload."
while IFS= read -r path; do
    case "$path" in
        system/system_ext/*|system/product/*) original=/${path#system/} ;;
        system/*) original=/$path ;;
        *) abort "Unexpected mount path: $path" ;;
    esac
    if [ -f "$original" ]; then
        context=$(ls -Zd "$original" | awk '{print $1}')
        case "$context" in
            u:object_r:*:s0) chcon "$context" "$MODPATH/$path" \
                || abort "Cannot preserve context: $path" ;;
            *) abort "Cannot read original context: $path" ;;
        esac
    else
        case "$path" in
            system/product/overlay/PopsicleHiddenNavigationFramework.apk|system/product/overlay/PopsicleHiddenNavigationLauncher.apk) ;;
            *) abort "Missing ROM baseline path: $path" ;;
        esac
    fi
done < "$MODPATH/payload-files.txt"
ui_print "Installed. Reboot, then open Settings > System > Gestures > System navigation."
ui_print "Open gesture navigation settings and enable Hide gesture navigation bar."
ui_print "Rear personalization v0.2 is included. Keep the old rear module disabled."
