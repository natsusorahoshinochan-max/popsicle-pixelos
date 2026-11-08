# PixelOS media and shade module

The user confirmed KernelSU v0.2 and the integrated full ROM fixes on 2026-09-24.
The [2026-09-24 full ROM](../../docs/pixelos/validation.md) and its successors build
the SystemUI and Bluetooth repairs directly from the
[media and shade patches](../../scripts/source-patches/media-shade/README.md).
Maintain these repairs through incremental changes in an already assembled Android tree.

Package in the remote Linux container.

```sh
python3 modules/popsicle-media-shade-fixes/build.py CANDIDATE_PRODUCT NEW_OUTPUT \
    --bluetooth-library BUILT_LIBBLUETOOTH_JNI --soong-zip SOONG_ZIP
```

`payload-files.txt` explicitly names SystemUI and its preoptimization, initialized
from delivered v0.2 payload names. The Bluetooth JNI library is supplied
separately. Packaging copies the files and uses 16 compression workers.
The input artifacts go through normal Android build and signing checks.

The accepted v0.2 baseline was popsicle PixelOS Android 17, system build date
1789556771. On that historical baseline, install through KernelSU with system-file
mounting configured, then reboot. The installer sets permissions and SELinux labels. `post-mount.sh` binds
the source-built JNI library read-only into init's APEX mount before Bluetooth
starts. Mount failures stop the operation. Disable `popsicle-media-shade-fixes`
and reboot to restore the underlying ROM.

Historical delivery, failures and acceptance scope are in
[the module record](../../docs/pixelos/validation.md).
