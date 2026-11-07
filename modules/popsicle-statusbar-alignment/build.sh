#!/usr/bin/env bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
[[ $# == 2 ]] || { echo "Usage: $0 ANDROID_SOURCE OUTPUT_DIRECTORY" >&2; exit 2; }
source_dir=$(cd -- "$(dirname -- "$0")" && pwd)
android=$(cd -- "$1" && pwd)
mkdir -p -- "$2"
output=$(cd -- "$2" && pwd)
host="$android/out-pixelos-user/host/linux-x86"
product="$android/out-pixelos-user/target/product/popsicle"
java="$android/prebuilts/jdk/jdk21/linux-x86/bin/java"
keys="$android/build/target/product/security"
base="$product/product/overlay/PopsicleStatusbarSystemUI.apk"
expected=356128eb75bc8ec5110254dd64247cf1084957c39d836ee7a532c732339582f4
[[ $(sha256sum "$base" | cut -d ' ' -f1) == "$expected" ]] \
    || { echo 'Unsupported baseline overlay' >&2; exit 1; }
work=$(mktemp -d "$output/.build.XXXXXX")
trap 'rm -rf -- "$work"' EXIT
stage="$work/module"
relative=system/product/overlay/PopsicleStatusbarSystemUI.apk
mkdir -p "$stage/system/product/overlay"
"$host/bin/aapt2" compile --dir "$source_dir/overlay/res" -o "$work/resources.zip"
"$host/bin/aapt2" link -I "$android/prebuilts/sdk/current/public/android.jar" \
    --manifest "$source_dir/overlay/AndroidManifest.xml" --auto-add-overlay \
    -o "$work/unsigned.apk" "$work/resources.zip"
"$java" -Djava.library.path="$host/lib64" -jar "$host/framework/signapk.jar" \
    "$keys/platform.x509.pem" "$keys/platform.pk8" "$work/unsigned.apk" "$stage/$relative"
export JAVA_HOME="$android/prebuilts/jdk/jdk21/linux-x86"
export PATH="$JAVA_HOME/bin:$PATH"
"$host/bin/apksigner" verify --print-certs "$base" > "$output/baseline-signature.txt"
"$host/bin/apksigner" verify --print-certs "$stage/$relative" > "$output/candidate-signature.txt"
diff -u <(grep 'certificate SHA-256 digest:' "$output/baseline-signature.txt") \
    <(grep 'certificate SHA-256 digest:' "$output/candidate-signature.txt")
"$host/bin/aapt2" dump resources "$base" > "$output/baseline-resources.txt"
"$host/bin/aapt2" dump resources "$stage/$relative" > "$output/candidate-resources.txt"
printf '%s\n' "$expected" > "$stage/baseline-apk.sha256"
printf '%s\n' 1790225821 > "$stage/baseline-date"
cp "$source_dir/module.prop" "$source_dir/customize.sh" "$source_dir/README.md" "$stage/"
(cd "$stage" && sha256sum "$relative" > payload.sha256)
find "$stage" -type d -exec chmod 0755 {} +
find "$stage" -type f -exec chmod 0644 {} +
chmod 0755 "$stage/customize.sh"
archive=popsicle-statusbar-alignment-v0.1.zip
rm -f -- "$output/$archive"
(cd "$stage" && zip -q -r "$output/$archive" .)
(cd "$output" && sha256sum "$archive" > "$archive.sha256")
unzip -t "$output/$archive"
