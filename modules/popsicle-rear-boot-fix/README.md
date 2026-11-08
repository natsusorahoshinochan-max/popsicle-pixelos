# PixelOS rear boot repair module

The user confirmed v0.1 passed device testing. The delivery and acceptance record
is [2026-09-29 module record](../../docs/pixelos/validation.md).

This directory maintains the framework patch, original SDK extraction and
packaging tools. Supply proprietary inputs and signing keys from the build environment.
`prepare-rear.py` assembles the original SDK additions. `check-native.py` retains
the Android native ELF check. The complete ROM builds the accepted repairs from
the [rear runtime patches](../../scripts/source-patches/oem-rear-runtime/README.md).
Maintain the repair through incremental changes in an already assembled Android tree.

Package the built product in the remote Linux container.

```sh
python3 modules/popsicle-rear-boot-fix/build.py CANDIDATE_PRODUCT NEW_OUTPUT \
    --sdk-notice SDK_NOTICE --soong-zip SOONG_ZIP
```

`payload-files.txt` explicitly lists product-relative files, including dependent
preoptimization and fs-verity/manifest companions, initialized from v0.1 payload
names. Adjust this list when the intended payload changes. Packaging copies the
listed files and compresses with 16 workers. Android signing and platform checks
run when building the input artifacts.

The accepted v0.1 baseline was popsicle PixelOS Android 17 with
`ro.system.build.date.utc=1790239639`. On that historical baseline, install
through KernelSU with system-file mounting configured and reboot. The installer
sets permissions and preserves SELinux labels. Disable `popsicle-rear-boot-fix`
and reboot to restore the underlying ROM.
