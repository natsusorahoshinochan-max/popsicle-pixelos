#!/bin/bash
# SPDX-License-Identifier: Apache-2.0
set -euo pipefail
if [ "$#" -lt 6 ]; then
    echo "Usage: $0 JDK ASM_CLASSPATH WORK FRAMEWORK_JAR CORE_JAR CONFIGINFRA_JAR" >&2
    exit 2
fi
java="$1/bin"
cpasm=$2
work=$3
shift 3
here=$(cd "$(dirname "$0")" && pwd)
mkdir -p "$work/classes"
"$java/javac" -cp "$cpasm" -d "$work/classes" "$here/NormalizeTurbo.java"
"$java/java" -cp "$work/classes:$cpasm" NormalizeTurbo \
    "$work/TurboAdapter-a17-raw.jar" "$work/TurboAdapter-a17-frames.jar" \
    "$work/original-types.txt" "$@"
