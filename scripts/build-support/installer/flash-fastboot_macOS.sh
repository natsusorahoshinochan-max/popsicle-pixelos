#!/bin/bash
# Platform entry; the installer core is shared by macOS and Linux.
set -euo pipefail
if [ "$#" -gt 1 ]; then
    printf 'Usage: bash %s [PACKAGE_DIRECTORY]\n' "$0" >&2
    exit 2
fi
[ "$(uname -s)" = Darwin ] || { echo '请使用对应操作系统的入口。' >&2; exit 1; }
cd -- "${1:-$(dirname -- "$0")}"
platform=macOS
source ./scripts/flash-common.sh
