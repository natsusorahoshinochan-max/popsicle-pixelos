#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
if (( $# != 2 )); then
    echo "Usage: $0 ANDROID_SOURCE_ROOT OUTPUT_DIRECTORY" >&2
    exit 2
fi
android_source=$(cd -- "$1" && pwd)
module_source=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
mkdir -- "$2"
output_dir=$(cd -- "$2" && pwd)
stage="$output_dir/module"
relative=product/overlay/PopsicleFingerprintIcon.apk
mkdir -p "$stage/system/product/overlay"
cp "$android_source/out-pixelos-user/target/product/popsicle/$relative" "$stage/system/$relative"
cp "$module_source/module.prop" "$module_source/customize.sh" "$module_source/README.md" "$stage/"
find "$stage" -type d -exec chmod 0755 {} +
find "$stage" -type f -exec chmod 0644 {} +
chmod 0755 "$stage/customize.sh"
find "$stage" -type f | sort > "$output_dir/zip-inputs.txt"
archive="$output_dir/popsicle-fingerprint-icon-v0.1.zip"
"$android_source/out-pixelos-user/host/linux-x86/bin/soong_zip" -parallel 16 \
    -o "$archive" -C "$stage" -l "$output_dir/zip-inputs.txt"
(cd -- "$output_dir" && sha256sum "${archive##*/}" > "${archive##*/}.sha256")
echo "$archive"
