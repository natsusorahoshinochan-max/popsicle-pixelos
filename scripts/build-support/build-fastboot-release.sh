#!/bin/bash
# Run on the cloud Linux host; reuse the selected user output, never old out-final.
set -e -o pipefail
build_jobs=${BUILD_JOBS:-8}
export NINJA_HIGHMEM_NUM_JOBS=${NINJA_HIGHMEM_NUM_JOBS:-2}
for count in "$build_jobs" "$NINJA_HIGHMEM_NUM_JOBS"; do
    [[ "$count" =~ ^[1-9][0-9]*$ ]] || { echo "Build job counts must be positive integers" >&2; exit 2; }
done
if [ "$#" -lt 3 ] || [ "$#" -gt 4 ]; then
    echo "Usage: $0 ANDROID_TREE OUT_DIR NEW_RELEASE_DIRECTORY [pixelos]" >&2
    exit 2
fi
rom=${4:-pixelos}
case "$rom" in
    pixelos) target_product=custom_popsicle ;;
    *) echo "Unsupported ROM: $rom" >&2; exit 2 ;;
esac
support=$(cd "$(dirname "$0")" && pwd)
tree=$(realpath "$1")
output=$(realpath -m "$2")
# Reuse only this PixelOS product's Soong configuration.
for previous in "$output"/soong/soong.*.variables; do
    [ -f "$previous" ] || continue
    case "$(basename "$previous")" in
        "soong.${target_product}.variables"|"soong.${target_product}.extra.variables") ;;
        *) echo "Output contains another product configuration: $previous" >&2; exit 2 ;;
    esac
done
# Soong stores path spellings in its graph; preserve the tree-relative OUT_DIR.
export OUT_DIR=$(realpath --relative-to="$tree" "$output")
if [ -n "${FIRMWARE_ROOT:-}" ]; then
    if [ -n "${OFFICIAL_PAYLOAD:-}${OFFICIAL_IMAGES:-}" ]; then
        echo "Set FIRMWARE_ROOT or both explicit firmware inputs" >&2
        exit 2
    fi
    OFFICIAL_PAYLOAD="$FIRMWARE_ROOT/inputs/popsicle_official_OTA_A17/payload.bin"
    OFFICIAL_IMAGES="$FIRMWARE_ROOT/extracted/a17-payload"
fi
if [ ! -f "${OFFICIAL_PAYLOAD:-}" ] || [ ! -r "${OFFICIAL_PAYLOAD:-}" ] ||
   [ ! -d "${OFFICIAL_IMAGES:-}" ] || [ ! -r "${OFFICIAL_IMAGES:-}" ]; then
    echo "Provide readable OFFICIAL_PAYLOAD and OFFICIAL_IMAGES inputs" >&2
    exit 2
fi
OFFICIAL_PAYLOAD=$(realpath "$OFFICIAL_PAYLOAD")
OFFICIAL_IMAGES=$(realpath "$OFFICIAL_IMAGES")
firmware_args=(--payload "$OFFICIAL_PAYLOAD" --firmware-images "$OFFICIAL_IMAGES")
python=$(command -v python3)
release=$(realpath -m "$3")
test ! -e "$release"
mkdir -p "$release"
trap 'result=$?; printf "%s\n" "$result" > "$release/exit-code"' EXIT
cd "$tree"
export PYTHONDONTWRITEBYTECODE=1
unset USE_CCACHE CCACHE_DIR CCACHE_EXEC USE_GOMA
export CCACHE_DISABLE=1 USE_RBE=false
source build/envsetup.sh
lunch "${target_product}-cp2a-user"
m -j"$build_jobs" -k20 target-files-package lpmake simg2img img2simg
product="$output/target/product/popsicle"
tf="$product/obj/PACKAGING/target_files_intermediates/${target_product}-target_files"
host="$output/host/linux-x86/bin"
cp "$tf.zip" "$release/target_files.zip"
# The same exporter serves new builds and existing completed releases.
"$python" "$support/export-fastboot-release.py" \
    --rom "$rom" --source-release "$release" --tools-bin "$host" \
    "${firmware_args[@]}" \
    --output "$release/generated"
cp "$release/generated/READY.txt" "$release/READY.txt"
