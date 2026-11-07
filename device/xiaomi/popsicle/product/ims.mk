#
# SPDX-License-Identifier: Apache-2.0
#

# OEM IMS/QCC integration requires the matching Android 17 platform adapters.
# Global carrier resources are generated from matching stock data into the
# private carrier-config input. They replace the former 46001-only overlay.
PRODUCT_PACKAGES += \
    PopsicleImsDevice \
    PopsicleImsCarrier

PRODUCT_PACKAGES += \
    popsicle_ims_audio_adapter \
    PopsicleImsAudioBridge \
    PopsicleIms \
    qti-telephony-utils \
    ims-ext-common \
    qti_telephony_utils.xml \
    ims_ext_common.xml \
    popsicle-ims-privapp-permissions \
    PopsicleTelephonySelection

PRODUCT_SYSTEM_EXT_PROPERTIES += ro.audio.ihaladaptervendorextension_enabled=true
