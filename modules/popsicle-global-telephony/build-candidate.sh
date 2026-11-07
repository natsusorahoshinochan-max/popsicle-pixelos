#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -eo pipefail
android_tree=${1:?Android tree required}
evidence=${2:?Build log directory required}
cd "$android_tree"
mkdir -p "$evidence"
export OUT_DIR=out-pixelos-user NINJA_HIGHMEM_NUM_JOBS=4 GOMEMLIMIT=40GiB
export BUILD_DATETIME=1790675184
source build/envsetup.sh
lunch custom_popsicle-cp2a-user > "$evidence/lunch.log" 2>&1
m -j16 -k20 CarrierConfig PopsicleImsCarrier apns-conf.xml \
    > "$evidence/build.log" 2>&1
