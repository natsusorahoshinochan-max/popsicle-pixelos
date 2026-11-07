#
# SPDX-License-Identifier: Apache-2.0
#

$(call inherit-product, $(SRC_TARGET_DIR)/product/virtual_ab_ota/compression_with_xor.mk)
$(call inherit-product, packages/modules/Virtualization/apex/product_packages.mk)

DEVICE_PACKAGE_OVERLAYS += device/xiaomi/popsicle/overlay

# The retained Wi-Fi HAL supports WPA3-SAE Soft AP.
PRODUCT_PACKAGES += PopsicleWifiSae

PRODUCT_USE_DYNAMIC_PARTITIONS := true
PRODUCT_BUILD_SUPER_PARTITION := false
PRODUCT_VIRTUAL_AB_COMPRESSION_METHOD := lz4
PRODUCT_BUILD_RECOVERY_IMAGE := true
# Keep the official vendor ramdisk with its matching prebuilt kernel.
PRODUCT_BUILD_VENDOR_BOOT_IMAGE := false

PRODUCT_SHIPPING_API_LEVEL := 36
BOARD_SHIPPING_API_LEVEL := 202504

DEVICE_PRODUCT_COMPATIBILITY_MATRIX_FILE += \
    device/xiaomi/popsicle/vintf/compatibility_matrix.product.xml \
    device/xiaomi/popsicle/vintf/touch_framework_compatibility_matrix.xml

PRODUCT_SOONG_NAMESPACES += \
    hardware/qcom-caf/bootctrl \
    vendor/xiaomi/popsicle-private/prebuilt/oem-abi

# Actual native provider for the retained vendor QCC Binder client.
PRODUCT_PACKAGES += popsicle_qccsyshal_aidl_service

# Managed vendor derivation consumes this generated descriptor. Select it in
# the product so the partition file list includes the installed output.
PRODUCT_PACKAGES += vendor_tracing_descriptors

# The retained Widevine APEX explicitly requires this vendor-provided library.
PRODUCT_VENDOR_LINKER_CONFIG_FRAGMENTS += device/xiaomi/popsicle/configs/linker/vendor.json

PRODUCT_PRODUCT_PROPERTIES += \
    ro.sf.lcd_density=480 \
    ro.config.media_vol_steps=20

# The retained ODM ignores HWC mounting orientation. Use SurfaceFlinger's actual
# secondary-internal-display property; the OEM mi_sf key has no AOSP consumer.
PRODUCT_SYSTEM_PROPERTIES += \
    ro.surface_flinger.secondary_display_orientation=ORIENTATION_90

# Select the matching OEM profiles before zygote preloads CamcorderProfile.
PRODUCT_SYSTEM_PROPERTIES += \
    ro.media.xml_variant.profiles=_canoe_v2 \
    tombstoned.max_tombstone_count=50 \
    bluetooth.profile.a2dp.source.enabled=true \
    bluetooth.profile.avrcp.target.enabled=true \
    bluetooth.profile.hfp.ag.enabled=true \
    bluetooth.profile.opp.enabled=true \
    bluetooth.profile.hid.host.enabled=true \
    bluetooth.profile.hid.device.enabled=true \
    bluetooth.profile.pan.nap.enabled=true \
    bluetooth.profile.pan.panu.enabled=true \
    doze.display.supported=true

PRODUCT_PACKAGES += \
    PopsicleNetworkValidationOverlay \
    android.hardware.boot-service.qti.recovery \
    android.hardware.fastboot-service.example_recovery \
    android.hardware.health-service.qti_recovery \
    fastbootd \
    update_engine_sideload

# Normal-boot A/B services and the selected ART postinstall entry point.
PRODUCT_PACKAGES += \
    otapreopt_script \
    update_engine \
    update_verifier

include device/xiaomi/popsicle/product/display.mk

PRODUCT_COPY_FILES += \
    device/xiaomi/popsicle/recovery/root/init.recovery.qcom.rc:$(TARGET_COPY_OUT_RECOVERY)/root/init.recovery.qcom.rc

# The generic ramdisk is loaded after vendor_boot. Keep the original fstab
# entries, adding the native standalone AVB key for derived vendor and ODM.
PRODUCT_COPY_FILES += \
    device/xiaomi/popsicle/configs/fstab.qcom:$(TARGET_COPY_OUT_RAMDISK)/first_stage_ramdisk/fstab.qcom \
    device/xiaomi/popsicle/configs/avb/popsicle-userdebug.avbpubkey:$(TARGET_COPY_OUT_RAMDISK)/avb/popsicle-userdebug.avbpubkey \
    device/xiaomi/popsicle/configs/avb/popsicle-userdebug.avbpubkey:$(TARGET_COPY_OUT_RAMDISK)/first_stage_ramdisk/avb/popsicle-userdebug.avbpubkey \
    device/xiaomi/popsicle/configs/avb/popsicle-userdebug.avbpubkey:$(TARGET_COPY_OUT_RECOVERY)/root/avb/popsicle-userdebug.avbpubkey
