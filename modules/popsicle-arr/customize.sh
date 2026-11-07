#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0

[ "$KSU" = true ] || abort "KernelSU is required."
[ "$(getprop ro.product.device)" = popsicle ] || abort "This module is for popsicle."

base_hash=3d64a31b906ef7f23b98c52ff34831258c33cc5f8f6fbf56c33d5fb247586221
previous_hash=bb3f457af8e4df6fe0c544017e4c7590f17b7c6ed618a04529c5776268e7cc0c
current_hash=$(sha256sum /system/framework/services.jar) || abort "Cannot read services.jar."
current_hash=${current_hash%% *}
module_hash=$(sha256sum "$MODPATH/system/framework/services.jar") || abort "Missing payload."
module_hash=${module_hash%% *}
if [ "$current_hash" != "$base_hash" ] && [ "$current_hash" != "$previous_hash" ] \
        && [ "$current_hash" != "$module_hash" ]; then
    abort "services.jar does not match the tested PixelOS build."
fi
# Native payload must match the same installed base as the tested device.
for entry in 'lib64/libgui.so:f993b7e8b9e6a0fcde09bdf9f310440e07464426bc618ddd4eb284963df280da' \
        'lib64/libandroid_servers.so:ed784d96f8ed35cb9580c5d0cadfb777d69c685ec4ab32c06a6f76270410de54' \
        'bin/surfaceflinger:8d8b013fc3d079ae91afc32430e809a1a8f45074210ff8dab2f4546138d5d133'; do
    path=${entry%%:*}
    expected=${entry#*:}
    actual=$(sha256sum "/system/$path") || abort "Cannot read $path."
    actual=${actual%% *}
    payload=$(sha256sum "$MODPATH/system/$path") || abort "Missing $path."
    payload=${payload%% *}
    [ "$actual" = "$expected" ] || [ "$actual" = "$payload" ] || abort "Mismatched $path."
done
ui_print "Framework ARR default and capability synchronization; reboot required."
ui_print "Disable this module and reboot to restore the original framework."

chmod 0755 "$MODPATH/system/bin/surfaceflinger" || abort "Cannot set SF executable mode."
chown 0:2000 "$MODPATH/system/bin/surfaceflinger" || abort "Cannot set SF ownership."
chcon u:object_r:surfaceflinger_exec:s0 "$MODPATH/system/bin/surfaceflinger" || abort "Cannot label SF."
for lib in libgui.so libandroid_servers.so; do
    chmod 0644 "$MODPATH/system/lib64/$lib" || abort "Cannot set library mode."
    chcon u:object_r:system_lib_file:s0 "$MODPATH/system/lib64/$lib" || abort "Cannot label library."
done
