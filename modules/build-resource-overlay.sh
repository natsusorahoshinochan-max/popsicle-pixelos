#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
if (( $# != 3 )); then
    echo "Usage: $0 MODULE_DIRECTORY ANDROID_SOURCE_ROOT OUTPUT_DIRECTORY" >&2
    exit 2
fi
module_source=$(cd -- "$1" && pwd)
android_source=$(cd -- "$2" && pwd)
script_dir=$(cd -- "$(dirname -- "$0")" && pwd)
mkdir -p -- "$3"
output_dir=$(cd -- "$3" && pwd)
module_id=$(sed -n 's/^id=//p' "$module_source/module.prop")
[[ $module_id =~ ^popsicle-[a-z0-9-]+$ ]] || { echo "Invalid module ID" >&2; exit 1; }
aapt2="$android_source/out-final/host/linux-x86/bin/aapt2"
java="$android_source/prebuilts/jdk/jdk21/linux-x86/bin/java"
sdk="$android_source/prebuilts/sdk/current/public/android.jar"
signapk="$android_source/out-final/host/linux-x86/framework/signapk.jar"
keys="$android_source/build/make/target/product/security"
for input in "$aapt2" "$java" "$sdk" "$signapk" "$keys/testkey.x509.pem" "$keys/testkey.pk8"; do
    [[ -f $input ]] || { echo "Missing input: $input" >&2; exit 1; }
done
work_dir=$(mktemp -d "$output_dir/.resource-overlay.XXXXXX")
trap 'rm -rf -- "$work_dir"' EXIT
mkdir -p "$work_dir/module/system/product/overlay"
"$aapt2" compile --dir "$module_source/res" -o "$work_dir/resources.zip"
"$aapt2" link -I "$sdk" --manifest "$module_source/AndroidManifest.xml" \
    --auto-add-overlay -o "$work_dir/unsigned.apk" "$work_dir/resources.zip"
"$java" -Djava.library.path="$android_source/out-final/host/linux-x86/lib64" \
    -jar "$signapk" "$keys/testkey.x509.pem" "$keys/testkey.pk8" \
    "$work_dir/unsigned.apk" "$work_dir/$module_id.apk"
cp "$work_dir/$module_id.apk" "$work_dir/module/system/product/overlay/"
cp "$module_source/module.prop" "$work_dir/module/"
if [[ -f $module_source/system.prop ]]; then
    cp "$module_source/system.prop" "$work_dir/module/"
fi
cp "$script_dir/resource-overlay-customize.sh" "$work_dir/module/customize.sh"
if [[ -d $module_source/system ]]; then
    cp -R "$module_source/system/." "$work_dir/module/system/"
fi
find "$work_dir/module" -type d -exec chmod 0755 {} +
find "$work_dir/module" -type f -exec chmod 0644 {} +
chmod 0755 "$work_dir/module/customize.sh"
(cd "$work_dir/module" && zip -q -r "$work_dir/$module_id.zip" .)
"$aapt2" dump resources "$work_dir/$module_id.apk" > "$work_dir/$module_id.resources.txt"
cp "$work_dir/$module_id.apk" "$work_dir/$module_id.zip" "$work_dir/$module_id.resources.txt" "$output_dir/"
echo "Built $output_dir/$module_id.zip"
