#
# SPDX-License-Identifier: Apache-2.0
#

# Common device assembly for AOSP-like Android 17 (API 37) products.
# Include hardware-boot.mk before the ROM common product in each product entry.
# All selected OEM features require the platform interfaces documented in
# docs/pixelos/device-layering-analysis-20260917.md; missing modules/resources
# remain build errors. Google and ROM preferences belong to product/pixelos.mk.
include device/xiaomi/popsicle/product/hardware.mk
include device/xiaomi/popsicle/product/ims.mk
include device/xiaomi/popsicle/product/oem-rear.mk
include device/xiaomi/popsicle/product/oem-camera.mk
