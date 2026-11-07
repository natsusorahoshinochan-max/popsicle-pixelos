#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
# Run only after applying the incremental candidate to this PixelOS tree.
set -eo pipefail
android_tree=${1:?Android tree required}
evidence=${2:?Build log directory required}
cd "$android_tree"
[ -f device/xiaomi/popsicle/source-config.mk ]
mkdir -p "$evidence"
export OUT_DIR=out-pixelos-user NINJA_HIGHMEM_NUM_JOBS=4 GOMEMLIMIT=40GiB
# Keep the installed ROM identity for matching preoptimization and manifests.
export BUILD_DATETIME=1790239639
source build/envsetup.sh
lunch custom_popsicle-cp2a-user > "$evidence/lunch.log" 2>&1
m -j16 -k20 services PopsicleSubscreenCenter \
    out-pixelos-user/target/product/popsicle/system/etc/security/fsverity/BuildManifest.apk \
    out-pixelos-user/target/product/popsicle/system_ext/etc/security/fsverity/BuildManifestSystemExt.apk \
    > "$evidence/candidate-build.log" 2>&1
