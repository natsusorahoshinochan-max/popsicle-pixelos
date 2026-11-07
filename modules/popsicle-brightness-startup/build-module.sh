#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
[[ $# == 2 ]] || { echo "Usage: $0 ANDROID_TREE NEW_OUTPUT_DIR" >&2; exit 2; }
android_tree=$(realpath "$1")
source_dir=$(cd -- "$(dirname -- "$0")" && pwd)
output_dir=$2
[[ ! -e "$output_dir" ]] || { echo "Output already exists" >&2; exit 1; }
product_out="$android_tree/out-pixelos-user/target/product/popsicle"
mkdir -p "$output_dir/staging/system/framework/oat/arm64"
output_dir=$(realpath "$output_dir")
staging="$output_dir/staging"
cp "$source_dir/module.prop" "$source_dir/customize.sh" "$source_dir/README.md" "$staging/"
for path in services.jar services.jar.fsv_meta services.jar.prof services.jar.prof.fsv_meta \
        oat/arm64/services.art oat/arm64/services.art.fsv_meta \
        oat/arm64/services.odex oat/arm64/services.odex.fsv_meta \
        oat/arm64/services.vdex oat/arm64/services.vdex.fsv_meta; do
    if [[ "$path" != *.fsv_meta && "$product_out/system/framework/$path" -nt \
            "$product_out/system/framework/$path.fsv_meta" ]]; then
        echo "Rebuild matching fs-verity metadata for $path before packaging" >&2
        exit 1
    fi
    cp "$product_out/system/framework/$path" "$staging/system/framework/$path"
done
(cd "$staging" && find system -type f -print0 | LC_ALL=C sort -z | xargs -0 sha256sum > payload.sha256)
"$android_tree/out-pixelos-user/host/linux-x86/bin/soong_zip" -parallel 16 \
    -o "$output_dir/popsicle-arr-brightness-v0.7.zip" -C "$staging" -D "$staging"
(cd "$output_dir" && sha256sum popsicle-arr-brightness-v0.7.zip > SHA256SUMS)
