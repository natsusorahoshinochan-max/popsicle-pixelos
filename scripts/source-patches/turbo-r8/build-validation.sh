#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -e -o pipefail
tree=$(realpath "$1")
evidence=$(realpath "$2")
trap 'rc=$?; printf "%s\n" "$rc" > "$evidence/narrow.exit"' EXIT
cd "$tree"
export OUT_DIR=out-pixelos-user NINJA_HIGHMEM_NUM_JOBS=4 PYTHONDONTWRITEBYTECODE=1
source build/envsetup.sh
lunch custom_popsicle-cp2a-user
m -j16 -k20 r8 d8 retrace process-keep-rules tracereferences \
    TurboAdapter_NoBatt TeleService VmTerminalApp Settings SystemUI \
    out-pixelos-user/soong/.intermediates/packages/modules/Telephony/telecom/framework/framework-telecom.impl/android_common/dex/framework-telecom.jar
