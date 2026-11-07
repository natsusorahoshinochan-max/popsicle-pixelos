#
# SPDX-License-Identifier: Apache-2.0
#

# Platform producer contract, not stock hardware constants. The matching
# Make/Soong extensions in the maintained source sequence consume these inputs.
# Preserve strict derivation, NOTICE, AVB and SELinux checks; never raw-copy the
# modified vendor/ODM partitions as a fallback when an extension is missing.
BOARD_VENDOR_EROFS_MANIFEST_SKUS := canoe
BOARD_ODM_EROFS_MANIFEST_SKUS := popsicle
BOARD_ODM_EROFS_STOCK_IMAGE := $(POPSICLE_STOCK_IMAGE_DIR)/odm.img
BOARD_ODM_EROFS_MERGE_NOTICE := true
BOARD_ODM_EROFS_ID_BUFFER_PATCH := $(POPSICLE_PROJECT_INPUTS)/scripts/source-patches/firmware-filesystems/camera_id_buffer.py
BOARD_ODM_EROFS_EXTENSION_CONFIG_PATCH := $(POPSICLE_PROJECT_INPUTS)/scripts/source-patches/camera-extensions/patch-chi.py
BOARD_ODM_EROFS_DEVICE_CONFIG_PATCH := $(POPSICLE_PROJECT_INPUTS)/scripts/source-patches/firmware-filesystems/camera_device_config.py
BOARD_AVB_PRESERVE_PREBUILT_IMAGES := boot dtbo vendor_boot
BOARD_PREBUILT_VBMETA_WITNESS := $(POPSICLE_STOCK_IMAGE_DIR)/vbmeta-witness.img
BOARD_PREBUILT_VBMETA_ALGORITHM := SHA256_RSA4096
BOARD_VENDOR_EROFS_AVB_KEY_PATH := external/avb/test/data/testkey_rsa4096.pem
BOARD_VENDOR_EROFS_AVB_ALGORITHM := SHA256_RSA4096
BOARD_VENDOR_EROFS_MERGE_NOTICE := true
BOARD_VENDOR_EROFS_REPAIR_AMBIENT_LABEL := true
BOARD_VENDOR_EROFS_AUDIO_REPAIR := true
BOARD_VENDOR_EROFS_PRODUCT_STAGE := true
BOARD_VENDOR_EROFS_STOCK_IMAGE := $(POPSICLE_STOCK_IMAGE_DIR)/vendor.img
BOARD_PREBUILT_VENDOR_BUILD_PROP := vendor/xiaomi/popsicle-private/prebuilt/firmware-a17/vendor-build.prop
BOARD_PREBUILT_ODM_BUILD_PROP := vendor/xiaomi/popsicle-private/prebuilt/firmware-a17/odm-build.prop
BOARD_PREBUILT_ODM_DLKM_BUILD_PROP := vendor/xiaomi/popsicle-private/prebuilt/firmware-a17/odm-dlkm-build.prop
BOARD_PREBUILT_VENDOR_DLKM_BUILD_PROP := vendor/xiaomi/popsicle-private/prebuilt/firmware-a17/vendor-dlkm-build.prop
BOARD_PREBUILT_SYSTEM_DLKM_BUILD_PROP := vendor/xiaomi/popsicle-private/prebuilt/firmware-a17/system-dlkm-build.prop
BOARD_VENDOR_EROFS_FSTAB := $(DEVICE_PATH)/configs/fstab.qcom
BOARD_VENDOR_EROFS_AVB_PUBLIC_KEY := $(DEVICE_PATH)/configs/avb/popsicle-userdebug.avbpubkey

# Required tracked transformation sources must resolve in the explicitly supplied
# project copy. Preparation also verifies the complete source and private inputs.
$(foreach input,$(BOARD_ODM_EROFS_ID_BUFFER_PATCH) $(BOARD_ODM_EROFS_EXTENSION_CONFIG_PATCH) $(BOARD_ODM_EROFS_DEVICE_CONFIG_PATCH),$(if $(wildcard $(input)),,$(error Missing popsicle project input: $(input))))
