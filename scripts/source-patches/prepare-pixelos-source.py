#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Apply the complete PixelOS user series and its maintained source inputs."""
import runpy
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True

if __name__ == '__main__':
    try:
        prepare = runpy.run_path(str(Path(__file__).with_name('prepare-public-source.py')))
        prepare['main']('pixelos-public-user.series',
                        ('boot', 'dtbo', 'vendor_boot', 'vbmeta', 'vbmeta-witness',
                         'vendor', 'odm', 'mi_product', 'vendor_dlkm', 'system_dlkm'))
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
