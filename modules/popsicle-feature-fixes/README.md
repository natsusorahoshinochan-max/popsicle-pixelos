# PixelOS feature delta

This historical module's changes are integrated into the [current ROM](../../docs/pixelos/progress.md).
Its color implementation was subsequently repaired by the
[OEM sRGB selection](../../scripts/source-patches/display-color/0002-select-oem-expert-srgb.patch)
and [main-panel color intent](../../scripts/source-patches/display-color/0003-main-panel-srgb-intent.patch)
patches. AICore model inference remains suspended pending acceptance.
The following instructions target the historical ROM with system build date `1789438377`.

Independent KernelSU module for the matching popsicle Android 17 ROM. It contains
only the color service/resources, Settings AppFunctions enablement, main-display
landscape RRO, ASI/PCS association rule, and complete signed AICore APK set.

Build the ROM targets first, including their fs-verity metadata and BuildManifest.
Then run on the project Linux build host.

```sh
python3 modules/popsicle-feature-fixes/build.py ANDROID_TREE \
    NEW_OUTPUT_DIRECTORY \
    --baseline-date 1789438377 \
    --baseline-framework-hashes BASELINE_FRAMEWORK_SHA256
```

Requires KernelSU with system-file mounting configured. Installation checks the
installed ROM date and rejects overlapping active module files. Disable this
module and reboot to restore underlying ROM files. App data and Google Play
updates are preserved, including the AICore app installed from Play during setup.

The hash inventory is captured from the matching device before installation.
The packer includes rebuilt system-server preoptimization dependencies and their
matching verity metadata, and rejects unexpected framework code changes.

Historical execution and limitations are recorded in
[the implementation report](../../docs/pixelos/validation.md).
