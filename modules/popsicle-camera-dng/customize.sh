#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle."
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17."
[ "$(getprop ro.build.date.utc)" = 1790954511 ] \
    || abort "Requires the 2026-10-02 seven-fixes PixelOS ROM (1790954511)."
for root in /data/adb/modules /data/adb/modules_update; do
    for module in "$root"/*; do
        [ -d "$module" ] || continue
        [ "${module##*/}" = popsicle-camera-dng ] && continue
        [ -f "$module/disable" ] || [ -f "$module/remove" ] && continue
        if [ -f "$module/system/system_ext/priv-app/PopsicleMiuiCamera/PopsicleMiuiCamera.apk" ] \
            || [ -f "$module/system_ext/priv-app/PopsicleMiuiCamera/PopsicleMiuiCamera.apk" ]; then
            abort "Disable overlapping camera module: ${module##*/}"
        fi
    done
done
set_perm_recursive "$MODPATH/system" 0 0 0755 0644
chcon -R u:object_r:system_file:s0 "$MODPATH/system" || abort "Cannot label payload."
while IFS= read -r path; do
    original=/${path#system/}
    context=$(ls -Zd "$original" | awk '{print $1}')
    case "$context" in
        u:object_r:*:s0) chcon "$context" "$MODPATH/$path" || abort "Cannot label $path" ;;
        *) abort "Cannot identify original context: $original" ;;
    esac
done < "$MODPATH/payload-files.txt"
ui_print "DNG repair v0.3 installed; reboot to activate."
ui_print "Full-resolution remosaic and OEM lossless RAW tile writers enabled."
ui_print "UltraRAW per-frame white-balance metadata corrected."
ui_print "Failure payload capture is off by default."
ui_print "Disable this module and reboot to restore the ROM camera."
