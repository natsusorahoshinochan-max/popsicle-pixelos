#!/bin/sh
# SPDX-License-Identifier: Apache-2.0
set -eu
patch_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
exec python3 "$patch_dir/../replay.py" "$@" "$patch_dir/series"
