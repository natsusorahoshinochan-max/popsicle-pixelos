#
# SPDX-License-Identifier: Apache-2.0
#

# Preserve the official APK and the platform-integrated CameraOpt implementation.
PRODUCT_PACKAGES += PopsicleMiuiCamera

# Original CameraOpt server adapters share services.jar package-private access.
PRODUCT_SYSTEM_SERVER_JARS += system_ext:miui-cameraopt
