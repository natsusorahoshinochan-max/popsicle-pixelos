# PixelOS media and shade module

The user confirmed KernelSU v0.2 and the integrated full ROM fixes on 2026-09-24.
The [2026-09-24 full ROM](../../docs/pixelos/validation.md) and its successors build
SystemUI and Bluetooth normally and do not require this module. The patches
are records 103–104 in [the formal repair group](../../scripts/source-patches/media-shade/README.md).
The active tree already contains them; do not reverse or replay them.

Package in the remote Linux container:

```sh
python3 modules/popsicle-media-shade-fixes/build.py CANDIDATE_PRODUCT NEW_OUTPUT \
    --bluetooth-library BUILT_LIBBLUETOOTH_JNI --soong-zip SOONG_ZIP
```

`payload-files.txt` explicitly names SystemUI and its preoptimization, initialized
from delivered v0.2 payload names. The Bluetooth JNI library is supplied
separately. No baseline product or CAPEX input is required. Packaging copies the
files and uses 16 compression workers without checksum or readback checks.
Normal Android build/signing checks remain unchanged.

The accepted v0.2 baseline was popsicle PixelOS Android 17, system build date
1789556771. On that historical baseline, install through KernelSU with system-file mounting configured, then reboot. The installer sets permissions and SELinux labels. `post-mount.sh` binds
the source-built JNI library read-only into init's APEX mount before Bluetooth
starts; mount failures stop the operation. Disable `popsicle-media-shade-fixes`
and reboot to restore the underlying ROM. These tools do not flash a device.

Historical delivery, failures and acceptance scope are in
[the module record](../../docs/pixelos/validation.md).
The retained SystemUI patch includes Android listener regression tests that were
not run during the original delivery.
