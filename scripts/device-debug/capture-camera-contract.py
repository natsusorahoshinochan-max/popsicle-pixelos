#!/usr/bin/env python3
"""Bounded CameraService/AIDL capture; no injection into the camera application."""
import argparse
from collections import Counter
import json
import os
from pathlib import Path
import signal
import subprocess
import threading
import time

import frida


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--serial', required=True)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--tags', required=True, type=Path)
    parser.add_argument('--server-pid', type=int)
    parser.add_argument('--seconds', type=int, default=720)
    args = parser.parse_args()
    if not 1 <= args.seconds <= 900:
        parser.error('seconds must be between 1 and 900')
    tags = args.tags.read_text().strip()
    if not tags or len(tags) > 100000 or any(c not in 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_.,' for c in tags):
        parser.error('Expected a bounded comma-separated metadata name list')
    args.output.mkdir(parents=True, exist_ok=True)
    (args.output / 'metadata').mkdir(exist_ok=True)
    adb = [args.adb, '-s', args.serial]
    stop = threading.Event()
    signal.signal(signal.SIGTERM, lambda *_: stop.set())
    signal.signal(signal.SIGINT, lambda *_: stop.set())
    lock = threading.Lock()
    counts = Counter()
    phase = 'preflight'
    started = time.monotonic()
    deadline = started + 480
    reason = 'deadline'
    session = None
    service_session = None
    children = []
    handles = []
    last_pid_check = 0
    binary_number = 0
    server_start = None
    watch_started = False

    def shell(*command):
        return subprocess.check_output(adb + ['shell', *command], text=True, timeout=15).strip()

    def atomic(name, value):
        path = args.output / name
        temp = path.with_suffix(path.suffix + '.tmp')
        temp.write_text(json.dumps(value, indent=2) + '\n')
        temp.replace(path)

    with (args.output / 'events.jsonl').open('x', buffering=1) as output:
        def record(message, data=None):
            nonlocal binary_number
            with lock:
                payload = message.get('payload', {})
                counts[payload.get('event', message.get('type', 'host'))] += 1
                row = {'host_ns': time.time_ns(), 'phase': phase, 'message': message}
                if data is not None:
                    binary_number += 1
                    name = f'metadata/{binary_number:05d}.parcel'
                    (args.output / name).write_bytes(data)
                    row.update(binary_file=name, binary_bytes=len(data))
                output.write(json.dumps(row) + '\n')
                if message.get('type') == 'error' or payload.get('event') == 'native_error':
                    stop.set()

        try:
            if args.server_pid:
                command = shell('cat', f'/proc/{args.server_pid}/cmdline')
                if '/data/local/tmp/official-a17-probe/frida-server' not in command:
                    raise RuntimeError('Unexpected server owner')
                server_start = shell('cat', f'/proc/{args.server_pid}/stat').rsplit(')', 1)[1].split()[19]
            device = frida.get_device(args.serial, timeout=10)
            executable = 'vendor.qti.camera.provider-service_64'
            raw_pid = shell('pidof', executable).split()
            if len(raw_pid) != 1:
                raise RuntimeError('Expected one provider PID')
            pid = int(raw_pid[0])
            session = device.attach(pid)
            session.on('detached', lambda why, crash=None: (
                record({'type': 'detached', 'reason': why, 'crash': str(crash)}), stop.set()))
            code = Path(__file__).with_name('trace-camera-contract-native.js').read_text()
            script = session.create_script(code)
            script.on('message', record)
            script.load()
            record({'type': 'attached', 'pid': pid})
            client_pid = int(shell('pidof', 'com.android.camera'))
            client_status = shell('cat', f'/proc/{client_pid}/status').splitlines()
            client_uid = int(next(line for line in client_status if line.startswith('Uid:')).split()[1])
            if 'frida' in shell('cat', f'/proc/{client_pid}/maps').lower():
                raise RuntimeError('Camera application still has Frida mappings')
            service_pid = int(shell('pidof', 'cameraserver'))
            service_session = device.attach(service_pid)
            service_session.on('detached', lambda why, crash=None: (
                record({'type': 'service_detached', 'reason': why, 'crash': str(crash)}), stop.set()))
            service_code = Path(__file__).with_name('trace-camera-service-native.js').read_text()
            service_script = service_session.create_script(service_code)
            service_script.on('message', record)
            service_script.load()
            configured = service_script.exports_sync.configure(client_uid)
            record({'type': 'service_attached', 'pid': service_pid, 'target': configured})
            watch_result = shell('cmd', 'media.camera', 'watch', 'start', '-m', tags, '-c', 'com.android.camera')
            watch_started = True
            record({'type': 'watch_start', 'result': watch_result, 'tags': tags.split(',')})
            for name, command in [
                ('live.log', ['logcat', '-b', 'all', '-v', 'threadtime', '-T', '1']),
                ('watch.txt', ['shell', 'cmd', 'media.camera', 'watch', 'live']),
            ]:
                handle = (args.output / name).open('x')
                handles.append(handle)
                child = subprocess.Popen(adb + command, stdin=subprocess.PIPE, stdout=handle, stderr=subprocess.STDOUT)
                children.append(child)
            atomic('owner.json', {'owner_pid': os.getpid(), 'provider_pid': pid,
                                  'child_pids': [c.pid for c in children], 'client_pid': client_pid,
                                  'service_pid': service_pid, 'client_uid': client_uid,
                                  'application_injection': False,
                                  'owned_server_pid': args.server_pid, 'server_start': server_start,
                                  'preflight_seconds': 480, 'operation_seconds': args.seconds})
            while time.monotonic() < deadline and not stop.wait(.2):
                if (args.output / 'stop').exists():
                    reason = 'stop_file'
                    break
                if time.monotonic() - last_pid_check > 5:
                    if shell('pidof', executable) != str(pid):
                        raise RuntimeError('Provider process changed')
                    if shell('pidof', 'cameraserver') != str(service_pid):
                        raise RuntimeError('CameraService process changed')
                    if shell('pidof', 'com.android.camera') != str(client_pid):
                        raise RuntimeError('Camera client process changed')
                    last_pid_check = time.monotonic()
                if any(c.poll() is not None for c in children):
                    raise RuntimeError('Observation child exited')
                with lock:
                    current = dict(counts)
                atomic('status.json', {'phase': phase, 'counts': current,
                                      'remaining_seconds': max(0, deadline-time.monotonic())})
                record({'type': 'watch_snapshot', 'text': shell('cmd', 'media.camera', 'watch', 'dump')})
                if phase == 'preflight' and (args.output / 'arm').exists():
                    if any(v and ('error' in k or 'detached' in k) for k, v in current.items()):
                        raise RuntimeError('Observer errors during preflight')
                    required = ('aidl_stream_configuration', 'service_metadata_read',
                                'service_binder_request', 'service_binder_reply')
                    if any(not current.get(name) for name in required):
                        raise RuntimeError('Missing service metadata/transaction or AIDL configuration')
                    if not (args.output / 'coverage-ready.json').exists():
                        raise RuntimeError('Missing reviewed preflight coverage')
                    phase = 'operation'
                    deadline = time.monotonic() + args.seconds
                    record({'type': 'armed', 'seconds': args.seconds})
                    print('Unified operation window armed.', flush=True)
            if stop.is_set():
                reason = 'signal_detach_or_observer_error'
        except Exception as error:
            reason = 'error'
            record({'type': 'error', 'error': str(error)})
            raise
        finally:
            for child in children:
                if child.poll() is None:
                    child.terminate()
                    try:
                        child.wait(timeout=5)
                    except subprocess.TimeoutExpired:
                        child.kill()
                        child.wait()
                if child.stdin:
                    child.stdin.close()
            for handle in handles:
                handle.close()
            if watch_started:
                try:
                    record({'type': 'watch_stop', 'result': shell('cmd', 'media.camera', 'watch', 'stop')})
                except Exception as error:
                    record({'type': 'cleanup_error', 'error': str(error)})
            if service_session is not None:
                try:
                    service_session.detach()
                except Exception as error:
                    record({'type': 'cleanup_error', 'target': 'cameraserver', 'error': str(error)})
            if session is not None:
                try:
                    session.detach()
                except Exception as error:
                    record({'type': 'cleanup_error', 'target': 'provider', 'error': str(error)})
            if args.server_pid and server_start:
                try:
                    now_start = shell('cat', f'/proc/{args.server_pid}/stat').rsplit(')', 1)[1].split()[19]
                    if now_start == server_start:
                        shell('kill', '-TERM', str(args.server_pid))
                except Exception as error:
                    record({'type': 'cleanup_error', 'error': str(error)})
            if reason == 'error' or any('error' in name for name in counts):
                try:
                    (args.output / 'exit-info.txt').write_text(shell('dumpsys', 'activity', 'exit-info', 'com.android.camera') + '\n')
                    (args.output / 'crash-buffer.txt').write_text(subprocess.check_output(
                        adb + ['logcat', '-d', '-b', 'crash', '-v', 'threadtime'], text=True, timeout=15))
                except Exception as error:
                    record({'type': 'cleanup_error', 'target': 'crash_evidence', 'error': str(error)})
            result = {'reason': reason, 'phase': phase, 'finished': True,
                      'elapsed_seconds': time.monotonic()-started, 'counts': dict(counts)}
            atomic('capture-result.json', result)
            atomic('status.json', result)


if __name__ == '__main__':
    main()
