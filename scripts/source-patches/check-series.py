#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Compatibility entry for read-only ordered series preflight."""
import argparse
import subprocess
import sys
from pathlib import Path

sys.dont_write_bytecode = True
from replay import Replay

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('tree', type=Path)
    parser.add_argument('series', type=Path)
    args = parser.parse_args()
    try:
        Replay(args.tree, args.series).run('--check')
    except (ValueError, OSError, subprocess.CalledProcessError) as error:
        sys.exit(str(error))
