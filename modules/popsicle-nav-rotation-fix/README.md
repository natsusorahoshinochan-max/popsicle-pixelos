# PixelOS navigation rotation module

The user confirmed v0.1 and the integrated complete ROM passed device testing.
The implementation is formal records 105–106; see the
[release record](../../docs/pixelos/validation.md).
The current ROM includes the repair without this archived module. Do not install
the old delivered package over that repaired ROM.

Build with the intended PixelOS Android 17 product and its normal platform
signing/checks in the remote Linux container, then package:

```sh
python3 modules/popsicle-nav-rotation-fix/build.py CANDIDATE_PRODUCT NEW_OUTPUT \
    --soong-zip SOONG_ZIP
```

`payload-files.txt` explicitly lists product-relative services/SystemUI,
dependent preoptimization, fs-verity/manifest companions and log metadata. It is
initialized from delivered v0.1 payload names; update the list when changing the
intended payload. The packager copies these files and compresses with 16 workers.
It does not require a baseline product or produce checksum/readback checks.

Historical installation applies only to the v0.1 baseline described in the release
record and requires popsicle Android 17, KernelSU with system-file mounting configured.
Permissions and original SELinux labels are retained. Install through KernelSU
and reboot. Disable `popsicle-nav-rotation-fix` and reboot to restore the ROM
files underneath. These tools do not install or flash a device.

Cross-display rotation, IME/overlays and PiP have no separate per-case acceptance
results. The historical acceptance scope is recorded in the validation summary.
