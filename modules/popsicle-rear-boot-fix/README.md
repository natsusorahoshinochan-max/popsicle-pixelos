# PixelOS rear boot repair module

The user confirmed v0.1 passed device testing. The delivery and acceptance record
is [2026-09-29 module record](../../docs/pixelos/validation.md).

This directory maintains the framework patch, original SDK extraction and
packaging tools. Proprietary inputs and signing keys are not stored here.
`prepare-rear.py` assembles the original SDK additions; `check-native.py` retains
the Android native ELF check. The accepted rear repairs are integrated as records
107–111 of the formal source sequence. The complete ROM passed user device
testing and needs no rear override module. Do not replay the active tree.

Package the built product in the remote Linux container:

```sh
python3 modules/popsicle-rear-boot-fix/build.py CANDIDATE_PRODUCT NEW_OUTPUT \
    --sdk-notice SDK_NOTICE --soong-zip SOONG_ZIP
```

`payload-files.txt` explicitly lists product-relative files, including dependent
preoptimization and fs-verity/manifest companions, initialized from v0.1 payload
names. Adjust this list when the intended payload changes. Packaging copies the
listed files and compresses with 16 workers. No baseline product or checksum
manifest is required. Android signing and platform checks remain in the build.

The accepted v0.1 baseline was popsicle PixelOS Android 17 with
`ro.system.build.date.utc=1790239639`. On that historical baseline, install
through KernelSU with system-file mounting configured and reboot. The installer sets permissions and preserves SELinux labels. Disable
`popsicle-rear-boot-fix` and reboot to restore the underlying ROM. These tools do
not install or flash a device.
