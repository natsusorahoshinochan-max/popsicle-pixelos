#!/usr/bin/env python3
"""Persist Frida messages immediately; bounded attach observation, no return rewriting."""
import argparse
import json
from pathlib import Path
import signal
import threading
import time
import frida


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pid", type=int)
    parser.add_argument("script", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--serial", help="ADB device ID, including wireless devices")
    parser.add_argument("--stop-file", type=Path, help="Finish when this file appears")
    args = parser.parse_args()
    if not 1 <= args.seconds <= 300:
        parser.error("Duration must be 1..300 seconds")
    detached = threading.Event()
    stopped = threading.Event()
    signal.signal(signal.SIGINT, lambda *_: stopped.set())
    signal.signal(signal.SIGTERM, lambda *_: stopped.set())
    lock = threading.Lock()
    with args.output.open("w", buffering=1) as output:
        def record(message, data=None):
            with lock:
                output.write(json.dumps({"message": message, "binary_bytes": len(data) if data else 0}) + "\n")
            payload = message.get("payload")
            event = payload.get("event") if isinstance(payload, dict) else None
            if message.get("type") == "error" or (isinstance(payload, dict)
                                                   and isinstance(event, str)
                                                   and event.endswith("_error")):
                stopped.set()
        device = (frida.get_device(args.serial, timeout=10) if args.serial
                  else frida.get_usb_device(timeout=10))
        session = device.attach(args.pid)
        def on_detached(reason, crash=None):
            record({"event": "detached", "reason": reason, "crash": str(crash) if crash else None})
            detached.set()
            stopped.set()
        session.on("detached", on_detached)
        try:
            script = session.create_script(args.script.read_text())
            script.on("message", record)
            script.load()
            deadline = time.monotonic() + args.seconds
            while time.monotonic() < deadline and not stopped.wait(.2):
                if args.stop_file and args.stop_file.exists():
                    break
        finally:
            if not detached.is_set():
                session.detach()


if __name__ == "__main__":
    main()
