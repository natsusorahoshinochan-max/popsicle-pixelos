#!/system/bin/sh
# SPDX-License-Identifier: Apache-2.0
[ "$(getprop ro.product.device)" = popsicle ] || abort "Requires popsicle"
[ "$(getprop ro.build.version.sdk)" = 37 ] || abort "Requires Android 17 / SDK 37"
# Avoid installer-specific set_perm_recursive argument conventions.
chown -R 0:0 "$MODPATH/system" || abort "Cannot set ownership"
find "$MODPATH/system" -type d -exec chmod 0755 {} \;
find "$MODPATH/system" -type f -exec chmod 0644 {} \;
