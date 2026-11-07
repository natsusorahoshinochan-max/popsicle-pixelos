#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -eo pipefail
android_tree=${1:?Android tree required}
evidence=${2:?Build log directory required}
build_datetime=${3:?Matching ROM build datetime required}
cd "$android_tree"
mkdir -p "$evidence"
export OUT_DIR=out-pixelos-user NINJA_HIGHMEM_NUM_JOBS=4 GOMEMLIMIT=40GiB
export BUILD_DATETIME="$build_datetime"
source build/envsetup.sh
lunch custom_popsicle-cp2a-user > "$evidence/lunch.log" 2>&1
camera_intermediates="$OUT_DIR/soong/.intermediates/vendor/xiaomi/popsicle-private/prebuilt/oem-camera/PopsicleMiuiCamera/android_common"
m -j16 -k20 "$camera_intermediates/signed/PopsicleMiuiCamera.apk" \
    "$camera_intermediates/dexpreopt/PopsicleMiuiCamera/oat/arm64/package.odex" \
    "$camera_intermediates/dexpreopt/PopsicleMiuiCamera/oat/arm64/package.vdex" \
    > "$evidence/build-exact.log" 2>&1
