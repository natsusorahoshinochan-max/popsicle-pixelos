#
# SPDX-License-Identifier: Apache-2.0
#

DEVICE_PATH := device/xiaomi/popsicle

# Explicit independent project input copy; no fallback to another ROM checkout.
-include $(DEVICE_PATH)/source-config.mk
ifeq ($(strip $(POPSICLE_PROJECT_INPUTS)),)
$(error Set POPSICLE_PROJECT_INPUTS in device/xiaomi/popsicle/source-config.mk to this project's input copy)
endif
ifneq ($(words $(POPSICLE_PROJECT_INPUTS)),1)
$(error POPSICLE_PROJECT_INPUTS must be a single path without whitespace)
endif
ifneq ($(PLATFORM_SDK_VERSION),37)
$(error popsicle supports AOSP-like Android 17 platforms with API 37)
endif

# Architecture
TARGET_ARCH := arm64
TARGET_ARCH_VARIANT := armv8-a-branchprot
TARGET_CPU_ABI := arm64-v8a
TARGET_CPU_VARIANT := oryon

# Platform
TARGET_BOARD_PLATFORM := canoe
TARGET_BOOTLOADER_BOARD_NAME := canoe

# The retained OEM qcrilNrd services provide the device radio instances.
ENABLE_VENDOR_RIL_SERVICE := true

# Retain the matching OEM identities and filesystem ownership/capability overrides.
TARGET_FS_CONFIG_GEN += $(DEVICE_PATH)/configs/fs_config.ini

# SELinux
TARGET_USES_PREBUILT_VENDOR_SEPOLICY := true
# Derive the reviewed OEM contracts against current platform policy, with neverallows.
$(call soong_config_set_bool,popsicle,managed_vendor_policy,true)
$(call soong_config_set_bool,popsicle,tinyxml2_oem_abi,true)
$(call soong_config_set_bool,popsicle,global_carrier_config,true)
include device/qcom/sepolicy/SEPolicy.mk

SYSTEM_EXT_PRIVATE_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/system_ext/private
PRODUCT_PRIVATE_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/product/private
BOARD_VENDOR_SEPOLICY_DIRS += $(DEVICE_PATH)/sepolicy/vendor

# VINTF
# Match the bootloader SKU selectors of the retained complete OEM manifests.
DEVICE_MATRIX_FILE := $(DEVICE_PATH)/vintf/device_compatibility_matrix.xml
# Preserve the OEM requirement and permit this release's isolated product APIs.
BOARD_SYSTEMSDK_VERSIONS := 36 37

DEVICE_FRAMEWORK_COMPATIBILITY_MATRIX_FILE += \
    $(DEVICE_PATH)/vintf/compatibility_matrix.device.xml

DEVICE_FRAMEWORK_MANIFEST_FILE += \
    $(DEVICE_PATH)/vintf/vendor.qti.hardware.qccsyshal_aidl-service.xml \
    $(DEVICE_PATH)/vintf/vendor.qti.hardware.sigma_miracast_aidl.xml

# A/B update selection and its partition list are declared by the root product.

# Boot images: immutable inputs from the matching official A17 firmware.
TARGET_NO_KERNEL := true
POPSICLE_STOCK_IMAGE_DIR := vendor/xiaomi/popsicle-private/prebuilt/firmware-a17
BOARD_PREBUILT_BOOTIMAGE := $(POPSICLE_STOCK_IMAGE_DIR)/boot.img
BOARD_PREBUILT_DTBOIMAGE := $(POPSICLE_STOCK_IMAGE_DIR)/dtbo.img
BOARD_PREBUILT_VENDOR_BOOTIMAGE := $(POPSICLE_STOCK_IMAGE_DIR)/vendor_boot.img
BOARD_PREBUILT_SYSTEM_DLKMIMAGE := $(POPSICLE_STOCK_IMAGE_DIR)/system_dlkm.img
# Full OTA deletes omitted target-slot dynamic partitions. Preserve the mounted
# OEM mi_product using the existing byte-copy custom-image path, including its
# original AVB footer; no new signing key or top-level chain is introduced.
BOARD_CUSTOMIMAGES_PARTITION_LIST += mi_product
BOARD_MI_PRODUCT_IMAGE_LIST := $(POPSICLE_STOCK_IMAGE_DIR)/mi_product.img
BOARD_PREBUILT_VENDOR_DLKMIMAGE := $(POPSICLE_STOCK_IMAGE_DIR)/vendor_dlkm.img
# Use the normal source-built init_boot ramdisk, without root injection.
BOARD_BOOT_HEADER_VERSION := 4
BOARD_INIT_BOOT_HEADER_VERSION := 4
BOARD_MKBOOTIMG_ARGS += --header_version $(BOARD_BOOT_HEADER_VERSION)
BOARD_MKBOOTIMG_INIT_ARGS += --header_version $(BOARD_INIT_BOOT_HEADER_VERSION)
BOARD_KERNEL_BASE := 0x00000000
BOARD_KERNEL_PAGESIZE := 4096
BOARD_RAMDISK_USE_LZ4 := true

# Partitions
BOARD_BOOTIMAGE_PARTITION_SIZE := 100663296
BOARD_DTBOIMG_PARTITION_SIZE := 33554432
BOARD_INIT_BOOT_IMAGE_PARTITION_SIZE := 8388608
BOARD_METADATAIMAGE_PARTITION_SIZE := 67108864
BOARD_RECOVERYIMAGE_PARTITION_SIZE := 104857600
BOARD_SUPER_PARTITION_SIZE := 13421772800
BOARD_USERDATAIMAGE_PARTITION_SIZE := 512378253312
BOARD_VENDOR_BOOTIMAGE_PARTITION_SIZE := 100663296

BOARD_SUPER_PARTITION_GROUPS := qti_dynamic_partitions
BOARD_QTI_DYNAMIC_PARTITIONS_SIZE := 13411287040
# mi_ext remains absent as on the verified deployed slot; mi_product is retained.
BOARD_QTI_DYNAMIC_PARTITIONS_PARTITION_LIST := \
    mi_product \
    odm \
    product \
    system \
    system_dlkm \
    system_ext \
    vendor \
    vendor_dlkm

BOARD_FLASH_BLOCK_SIZE := 262144

BOARD_USES_METADATA_PARTITION := true
BOARD_METADATAIMAGE_FILE_SYSTEM_TYPE := f2fs
BOARD_ODMIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_PRODUCTIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_SYSTEMIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_SYSTEM_DLKMIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_SYSTEM_EXTIMAGE_FILE_SYSTEM_TYPE := ext4
BOARD_USERDATAIMAGE_FILE_SYSTEM_TYPE := f2fs
BOARD_VENDORIMAGE_FILE_SYSTEM_TYPE := erofs
BOARD_VENDOR_DLKMIMAGE_FILE_SYSTEM_TYPE := erofs

TARGET_COPY_OUT_ODM := odm
TARGET_COPY_OUT_PRODUCT := product
TARGET_COPY_OUT_SYSTEM_DLKM := system_dlkm
TARGET_COPY_OUT_SYSTEM_EXT := system_ext
TARGET_COPY_OUT_VENDOR := vendor
TARGET_COPY_OUT_VENDOR_DLKM := vendor_dlkm

# property_service reads /odm_dlkm/etc; this cohort stores it inside vendor.
BOARD_ROOT_EXTRA_SYMLINKS += /vendor/odm_dlkm/etc:odm_dlkm/etc

# Display
TARGET_SCREEN_DENSITY := 480

# Recovery
BOARD_EXCLUDE_KERNEL_FROM_RECOVERY_IMAGE := true
TARGET_RECOVERY_FSTAB := $(DEVICE_PATH)/recovery.fstab
TARGET_RECOVERY_PIXEL_FORMAT := RGBX_8888
TARGET_USERIMAGES_USE_EXT4 := true
TARGET_USERIMAGES_USE_F2FS := true

# Verified boot
BOARD_AVB_ENABLE := true
# Keep the OEM root accepted by the unlocked debug device; this is not a
# relockable release trust chain for the modified subordinate images.
BOARD_PREBUILT_VBMETAIMAGE := $(POPSICLE_STOCK_IMAGE_DIR)/vbmeta.img
BOARD_VBMETAIMAGE_PARTITION_SIZE := 131072
# The A17 official package retains this Android 16 vendor cohort.
VENDOR_OS_VERSION := 16
ODM_OS_VERSION := 16
VENDOR_SECURITY_PATCH := 2026-07-01
BOARD_AVB_SYSTEM_ADD_HASHTREE_FOOTER_ARGS += --hash_algorithm sha256
BOARD_AVB_SYSTEM_EXT_ADD_HASHTREE_FOOTER_ARGS += --hash_algorithm sha256
BOARD_AVB_PRODUCT_ADD_HASHTREE_FOOTER_ARGS += --hash_algorithm sha256
BOARD_AVB_VBMETA_SYSTEM := system system_ext product
BOARD_AVB_VBMETA_SYSTEM_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_VBMETA_SYSTEM_ALGORITHM := SHA256_RSA4096
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX := $(PLATFORM_SECURITY_PATCH_TIMESTAMP)
BOARD_AVB_VBMETA_SYSTEM_ROLLBACK_INDEX_LOCATION := 2

BOARD_AVB_RECOVERY_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_AVB_RECOVERY_ALGORITHM := SHA256_RSA4096
BOARD_AVB_RECOVERY_ROLLBACK_INDEX := 1
BOARD_AVB_RECOVERY_ROLLBACK_INDEX_LOCATION := 1

# Required Make/Soong managed-image extensions for this Android 17 platform.
include device/xiaomi/popsicle/board/managed-images.mk
