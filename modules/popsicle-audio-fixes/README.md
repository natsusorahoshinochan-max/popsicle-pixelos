# KernelSU audio repair module

The user accepted v0.3 on the device. Its payload is integrated into the formal
ROM, which also passed user testing and needs no audio override module.
USB/Bluetooth microphone and insertion/removal fallback tests remain uncovered.

`build.py` consumes the hash-pinned original OS4.0.0.23.XPBCNXM vendor XML.
For v0.3 it also requires the matching original core HAL through `--hal`.
Version 0.1 removes the phantom FM input and its route reference. Other input and
output ports are preserved. Version 0.2 (global platform property) was withdrawn after audio policy conversion
failed. `--platform-property` now fails explicitly. Version 0.3 uses `--hal` with
the matching original core HAL. One hash-guarded instruction initializes the
HAL-local GSI flag to false. Framework-facing properties and CTS stream flags
retain their stock values.

Build the v0.3 carrier on the remote Linux host, using its existing `soong_zip`.
`MATCHING_STOCK_CORE_HAL` is the unmodified `libaudiocorehal.qti.so` from that
same official firmware:

```sh
python3 modules/popsicle-audio-fixes/build.py STOCK_PRIMARY_XML NEW_OUTPUT_DIR \
  --hal MATCHING_STOCK_CORE_HAL \
  --soong-zip ANDROID_TREE/out-pixelos-user/host/linux-x86/bin/soong_zip
```

Omitting `--hal` produces the v0.1 FM-input-only carrier.

The installer requires the tested popsicle Android 17 baseline 1789465178,
KernelSU with system-file mounting configured. It checks XML hashes, conflicting module
payloads and the original file label.
Disable `popsicle-audio-fixes` and reboot to restore the ROM baseline. To roll back
to FM-only behavior, install the saved v0.1 archive and reboot. After the reboot,
verify the platform property is absent and the core HAL hash matches stock.

AudioPolicyConfig treats an empty AIDL connection as attached even when the XML
sets `attached=false`. The vendor FM directories and permission declarations are
present. Functional FM use still requires an identified input application or
service and device validation.

See [execution record](../../docs/pixelos/validation.md).
