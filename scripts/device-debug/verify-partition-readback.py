#!/usr/bin/env python3
"""Read an entire device partition and compare every byte with a raw image.

Read-only. An explicit zero-padding option covers the known firmware images
smaller than their partitions. No digest or sampled comparison replaces the read.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import subprocess
import threading
import time

CHUNK = 1024 * 1024


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adb", type=Path, required=True)
    parser.add_argument("--serial", required=True)
    parser.add_argument("--partition", required=True)
    parser.add_argument("--image", type=Path, required=True)
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument("--zero-pad", action="store_true")
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.partition) or args.timeout <= 0:
        raise ValueError("invalid partition or timeout")
    if args.report.exists() or args.report.with_suffix(".stderr").exists():
        raise ValueError("readback evidence destination already exists")
    args.report.parent.mkdir(parents=True, exist_ok=True)
    adb = [str(args.adb.resolve()), "-s", args.serial]
    block = "/dev/block/by-name/" + args.partition

    def shell(command: str) -> str:
        return subprocess.run(adb + ["shell", "-T", command], capture_output=True,
                              check=True, timeout=30).stdout.decode().strip()

    report = {"partition": args.partition, "image": str(args.image.resolve()),
              "serial": args.serial, "read_only": True, "passed": False,
              "zero_padding_requested": args.zero_pad}
    try:
        report["boot_before"] = shell("cat /proc/sys/kernel/random/boot_id")
        if shell("id -u") != "0":
            raise ValueError("root ADB required for full partition readback")
        size = int(shell("blockdev --getsize64 " + block))
        if not args.image.is_file():
            raise ValueError("reference image is not a regular file")
        image_stat = args.image.stat()
        image_size = image_stat.st_size
        report.update(partition_bytes=size, image_bytes=image_size)
        if size <= 0 or image_size <= 0 or image_size > size or \
                (not args.zero_pad and image_size != size):
            raise ValueError("image/partition sizes do not match the requested comparison")
        with args.image.open("rb") as image:
            if image.read(4) == b"\x3a\xff\x26\xed":
                raise ValueError("expand sparse images with simg2img before readback")
        started = time.monotonic()
        total = 0
        difference = None
        timed_out = threading.Event()
        with args.report.with_suffix(".stderr").open("xb") as errors, \
                args.image.open("rb") as image:
            process = subprocess.Popen(adb + ["shell", "-T", "dd if=" + block
                                       + " bs=1048576 status=none"], stdout=subprocess.PIPE,
                                       stderr=errors)

            def terminate() -> None:
                timed_out.set()
                process.kill()

            timer = threading.Timer(args.timeout, terminate)
            timer.start()
            try:
                while True:
                    actual = process.stdout.read(CHUNK)
                    if not actual:
                        break
                    expected = image.read(len(actual))
                    if len(expected) < len(actual):
                        expected += bytes(len(actual) - len(expected))
                    if difference is None and actual != expected:
                        difference = total + next(i for i, (a, b) in
                                                  enumerate(zip(actual, expected)) if a != b)
                    total += len(actual)
                result = process.wait()
            finally:
                timer.cancel()
                if process.poll() is None:
                    process.kill()
                    process.wait()
                process.stdout.close()
        report.update(read_bytes=total, first_difference=difference, adb_exit=result,
                      timed_out=timed_out.is_set(), elapsed_seconds=time.monotonic() - started,
                      complete_partition_read=total == size,
                      complete_reference_read=image_size <= total)
        after_stat = args.image.stat()
        report["reference_unchanged"] = all(
            getattr(image_stat, field) == getattr(after_stat, field)
            for field in ("st_dev", "st_ino", "st_size", "st_mtime_ns"))
        report["boot_after"] = shell("cat /proc/sys/kernel/random/boot_id")
        report["passed"] = (result == 0 and not timed_out.is_set() and total == size
                            and difference is None and report["reference_unchanged"]
                            and report["boot_before"] == report["boot_after"])
        if not report["passed"]:
            raise ValueError("full readback failed; do not reboot a pending flashing round")
    except Exception as error:
        report["error"] = f"{type(error).__name__}: {error}"
        raise
    finally:
        args.report.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
