#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Replace only the battery service implementation, retaining the original A17 interfaces."""
from pathlib import Path
import sys
import zipfile

prefix = 'com/google/android/turboadapter/GoogleBatteryService'
replaced = {prefix + suffix + '.class' for suffix in (
    '', '$1', '$GetBatteryPropertyRunnable', '$GetChargingStageAndDeadlineRunnable',
    '$GoogleBatteryProxy')}
with zipfile.ZipFile(sys.argv[1]) as source:
    names = set(source.namelist())
    if not replaced <= names or len(names) != 200:
        raise ValueError('Unexpected normalized Android 17 input')
    with zipfile.ZipFile(sys.argv[2], 'w', zipfile.ZIP_DEFLATED, compresslevel=9) as output:
        for name in sorted(names - replaced):
            info = zipfile.ZipInfo(name, (1980, 1, 1, 0, 0, 0))
            info.compress_type = zipfile.ZIP_DEFLATED
            output.writestr(info, source.read(name))
print('PASS retained 195 original classes; 5 battery service classes replaced by source')
