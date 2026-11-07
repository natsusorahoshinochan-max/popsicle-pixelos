# PixelOS feature delta

This historical module's changes are integrated into the [current ROM](../../docs/pixelos/progress.md),
which requires no feature override module. Its original color implementation was
subsequently repaired by formal records 119–120; AICore model inference remains
unaccepted and suspended. The following instructions apply only to the old matching
baseline and do not establish compatibility with the current ROM.

Independent KernelSU module for the matching popsicle Android 17 ROM. It contains
only the color service/resources, Settings AppFunctions enablement, main-display
landscape RRO, ASI/PCS association rule, and complete signed AICore APK set.
The existing OEM camera/rear/brightness module is not edited or repackaged.

Build the ROM targets first, including their fs-verity metadata and BuildManifest.
Then run on the project Linux build host:

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
No partition flashing or SELinux mode changes are involved.

The hash inventory is captured from the matching device before installation.
The packer includes rebuilt system-server preoptimization dependencies and their
matching verity metadata, and rejects unexpected framework code changes.

Historical execution and limitations are recorded in
[the implementation report](../../docs/pixelos/validation.md).
