#
# SPDX-License-Identifier: Apache-2.0
#

# PixelOS composition. Keep Google choices out of the common device assembly.
# Complete Play-delivered signed APK set in this project's private vendor tree.
PRODUCT_PACKAGES += PopsicleAICore
PRODUCT_COPY_FILES += \
    device/xiaomi/popsicle/configs/permissions/popsicle-private-compute.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/sysconfig/popsicle-private-compute.xml

include device/xiaomi/popsicle/device.mk

# AppFunctions and the selected Aperture UI belong to this product. These
# symbols are disjoint from the common overlay, preserving resource precedence.
DEVICE_PACKAGE_OVERLAYS += device/xiaomi/popsicle/product/overlay-pixelos

# Keep the existing APK identities, signatures and installation partitions.
# StatusbarSystemUI mixes hardware corners and a landscape split preference;
# leave that RRO intact until a separately validated overlay-structure change.
PRODUCT_PACKAGES += PopsicleStatusbarFramework PopsicleStatusbarSystemUI

# Physical main-panel pixel pitch for SystemUI's UDFPS icon sizing.
PRODUCT_PACKAGES += PopsicleFingerprintIcon

# Optional gesture navigation visibility; keep the original input window sizes.
PRODUCT_PACKAGES += PopsicleHiddenNavigationFramework PopsicleHiddenNavigationLauncher

# PixelOS common_full_phone.mk retains its Google-first WebView configuration.
