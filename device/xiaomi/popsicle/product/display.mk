#
# SPDX-License-Identifier: Apache-2.0
#

# Keep the paired lux/nits curve above the retained ODM legacy lux overlay.
PRODUCT_PACKAGES += PopsicleBrightnessCurve

PRODUCT_PACKAGES += popsicle_display_layout_configuration

PRODUCT_COPY_FILES += \
    device/xiaomi/popsicle/configs/permissions/privapp-permissions-popsicle-systemui.xml:$(TARGET_COPY_OUT_SYSTEM_EXT)/etc/permissions/privapp-permissions-popsicle-systemui.xml \
    device/xiaomi/popsicle/configs/displayconfig/display_id_4630946457447247251.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/displayconfig/display_id_4630946457447247251.xml \
    device/xiaomi/popsicle/configs/displayconfig/display_id_4630946457447247252.xml:$(TARGET_COPY_OUT_PRODUCT)/etc/displayconfig/display_id_4630946457447247252.xml
