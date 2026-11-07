#
# SPDX-License-Identifier: Apache-2.0
#

# Include before the ROM common product: its A/B helpers consume these values.
# The preserved OEM kernel is built exclusively with CONFIG_ARM64_4K_PAGES.
# Declare its actual ABI while retaining strict prebuilt segment alignment checks.
PRODUCT_MAX_PAGE_SIZE_SUPPORTED := 4096
PRODUCT_CHECK_PREBUILT_MAX_PAGE_SIZE := true

# Product inheritance runs before BoardConfig. The ROM's A/B helpers need this
# declaration while common.mk is imported, as do the final image/OTA consumers.
AB_OTA_UPDATER := true
AB_OTA_PARTITIONS += \
    boot \
    dtbo \
    init_boot \
    mi_product \
    odm \
    product \
    recovery \
    system \
    system_dlkm \
    system_ext \
    vbmeta \
    vbmeta_system \
    vendor \
    vendor_boot \
    vendor_dlkm

# ART uses the target system read-only and stages compiled artifacts in /data.
AB_OTA_POSTINSTALL_CONFIG += \
    RUN_POSTINSTALL_system=true \
    POSTINSTALL_PATH_system=system/bin/otapreopt_script \
    FILESYSTEM_TYPE_system=ext4 \
    POSTINSTALL_OPTIONAL_system=false
