#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -eo pipefail
android=${1:?Android tree required}
record=${2:?Build record required}
mkdir -p "$record"
cd "$android"
export OUT_DIR=out-pixelos-user NINJA_HIGHMEM_NUM_JOBS=4 GOMEMLIMIT=40GiB
export BUILD_DATETIME=1791303107
source build/envsetup.sh
lunch custom_popsicle-cp2a-user > "$record/lunch.log" 2>&1
set +e
m -j16 -k20 Settings PopsicleSubscreenCenter > "$record/build.log" 2>&1
result=$?
printf '%s\n' "$result" > "$record/exit-code"
exit "$result"
