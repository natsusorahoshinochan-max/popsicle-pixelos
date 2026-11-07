#
# SPDX-License-Identifier: Apache-2.0
#

# Use the OEM Face HAL; Sense has no service-availability fallback.
TARGET_FACE_UNLOCK_SUPPORTED := false

include device/xiaomi/popsicle/product/hardware-boot.mk

$(call inherit-product, $(SRC_TARGET_DIR)/product/core_64_bit_only.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/full_base_telephony.mk)
$(call inherit-product, $(SRC_TARGET_DIR)/product/generic_ramdisk.mk)

$(call inherit-product, device/xiaomi/popsicle/product/pixelos.mk)

$(call inherit-product, vendor/custom/config/common_full_phone.mk)

PRODUCT_NAME := custom_popsicle
PRODUCT_DEVICE := popsicle
PRODUCT_MANUFACTURER := Xiaomi
PRODUCT_BRAND := Xiaomi
PRODUCT_MODEL := 2509FPN0BC

PRODUCT_GMS_CLIENTID_BASE := android-xiaomi
