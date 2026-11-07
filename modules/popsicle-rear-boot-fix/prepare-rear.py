#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compatibility entry point for the maintained full-ROM rear adaptation."""
from pathlib import Path
import runpy

if __name__ == '__main__':
    runpy.run_path(str(Path(__file__).resolve().parents[2]
                      / 'device/xiaomi/popsicle/oem-rear/adaptation/prepare-rear.py'), run_name='__main__')
