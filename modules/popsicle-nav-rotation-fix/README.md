# PixelOS navigation rotation module

The user confirmed v0.1 and the integrated complete ROM passed device testing.
The implementation is maintained in the
[navigation rotation patches](../../scripts/source-patches/navigation-rotation/README.md).
The current ROM includes the repair directly. Disable or uninstall the archived
module before upgrading. Delivery details are in the
[release record](../../docs/pixelos/validation.md).

Build with the intended PixelOS Android 17 product and its normal platform
signing/checks in the remote Linux container, then package the output.

```sh
python3 modules/popsicle-nav-rotation-fix/build.py CANDIDATE_PRODUCT NEW_OUTPUT \
    --soong-zip SOONG_ZIP
```

`payload-files.txt` explicitly lists product-relative services/SystemUI,
dependent preoptimization, fs-verity/manifest companions and log metadata. It is
initialized from delivered v0.1 payload names. Update the list when changing the
intended payload. The packager copies these files and compresses with 16 workers.

Historical installation applies only to the v0.1 baseline described in the release
record and requires popsicle Android 17, KernelSU with system-file mounting configured.
Permissions and original SELinux labels are retained. Install through KernelSU
and reboot. Disable `popsicle-nav-rotation-fix` and reboot to restore the ROM
files underneath.

Historical acceptance was recorded for the module as a whole. Cross-display
rotation, IME/overlays and PiP await per-case validation.
