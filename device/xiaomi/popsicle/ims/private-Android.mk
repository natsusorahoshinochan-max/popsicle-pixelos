# SPDX-License-Identifier: Apache-2.0
LOCAL_PATH := $(call my-dir)
include $(CLEAR_VARS)
LOCAL_MODULE := PopsicleTelephonySelection
LOCAL_MODULE_CLASS := APPS
LOCAL_PRODUCT_MODULE := true
LOCAL_MODULE_SUFFIX := $(COMMON_ANDROID_PACKAGE_SUFFIX)
LOCAL_SRC_FILES := TelephonyResCommon_Sys.apk
LOCAL_MODULE_PATH := $(TARGET_OUT_PRODUCT)/overlay
LOCAL_CERTIFICATE := PRESIGNED
# This official RRO has resources only; prepare.py rejects any DEX input.
LOCAL_DEX_PREOPT := false
LOCAL_NOTICE_FILE := $(LOCAL_PATH)/NOTICE
include $(BUILD_PREBUILT)
