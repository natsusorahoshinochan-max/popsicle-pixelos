#
# SPDX-License-Identifier: Apache-2.0
#

# Requires the Android 17 WM/Shell, notification/media and OEM resource contracts.
# Original rear-App rendering runtime (prepared from the matching official system_ext).
PRODUCT_PACKAGES += \
    popsicle-pag-hyperos \
    libpag.hyperos \
    libffavc.hyperos \
    popsicle-pag-library \
    popsicle-pag-public-libraries

PRODUCT_PACKAGES += PopsicleSubscreenCenter popsicle-rear-resources
