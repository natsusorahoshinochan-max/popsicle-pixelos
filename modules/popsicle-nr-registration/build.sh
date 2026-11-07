#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -e
tree=$(realpath "${1:?Android tree required}")
work=$(realpath -m "${2:?New build log directory required}")
module_dir=$(cd "$(dirname "$0")" && pwd)
mkdir "$work"
exec > "$work/build.log" 2>&1
trap 'status=$?; echo "$status" > "$work/build.exit"' EXIT
cd "$tree"
export OUT_DIR=out-pixelos-user NINJA_HIGHMEM_NUM_JOBS=4 GOMEMLIMIT=40GiB
export BUILD_DATETIME=1790954511
source build/envsetup.sh
lunch custom_popsicle-cp2a-user
mapfile -t targets < <(python3 "$module_dir/package.py" targets "$tree")
[ "${#targets[@]}" -gt 0 ]
m -j16 -k20 "${targets[@]}"
