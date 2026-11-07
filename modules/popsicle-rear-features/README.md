# PixelOS rear display repair

KernelSU v0.5 (`popsicle-rear-boot-fix`) has passed user device testing. It includes
rear boot ordering, the original MiSight SDK, camera presentation, independent
rear AOD, double-tap wake, geometry refresh and gesture window recovery. APK
readiness and Dream session ownership are consolidated in the current runtime.
Official rear settings remain outside this repair.

The complete ROM and module use the same repair sources. These rear changes
are integrated as formal records 107–111. Current release and acceptance status
is maintained in [progress](../../docs/pixelos/progress.md).
The installation instructions below describe the matching historical module baseline.
See [historical delivery and acceptance](../../docs/pixelos/validation.md)
and [runtime structure](../../docs/pixelos/validation.md).

## Active source inputs

The following dependencies reproduce the recorded v0.5 payload.
They are already applied/prepared on the active tree; do not replay them there.

- Rear SDK preparation and initial display transaction repair reside in
  `../popsicle-rear-boot-fix/`.
- `candidate/rear-presentation.patch` applies from `frameworks/base`.
- `candidate/rear-aod.patch`, `rear-aod-touch-wake.patch` and
  `rear-dream-session-structure.patch` apply from the Android root, in that order.
- The private APK preparation chain is
  `subscreencenter-misight.apk` → `prepare-rear-geometry.py` →
  `subscreencenter-aod.apk` → `prepare-rear-gestures.py` →
  `subscreencenter-gestures.apk` → `prepare-rear-structured.py` →
  `subscreencenter-structured.apk`. Each script takes `ANDROID_TREE`.
- `device/xiaomi/popsicle/oem-rear/adaptation/structured-runtime/` contains the
  maintained smali adaptation sources. Module preparation scripts delegate to that
  device adaptation directory, the sole maintained implementation.
- The private vendor input selection patches follow the same APK chain:
  `rear-geometry-input.patch`, `rear-gestures-input.patch`, then
  `rear-structured-input.patch`. The final Android.bp input is
  `subscreencenter-structured.apk`, signed and preoptimized normally by Soong.

## Build and delivery

Build against the matching complete PixelOS Android 17 product in the remote
Linux container. `build-candidate.sh` builds the necessary Android targets with
normal platform checks. Package the existing output with:

```sh
python3 modules/popsicle-rear-features/build.py CANDIDATE_PRODUCT NEW_OUTPUT \
    --sdk-notice SDK_NOTICE --soong-zip SOONG_ZIP
```

`payload-files.txt` owns the product-relative payload list: services/rear APK,
matching preoptimization, fs-verity metadata/manifests and ProtoLog metadata.
The packager copies these files and compresses with 16 workers. Signing remains
part of the Android build.

Historical installation requires the matching v0.5 PixelOS baseline recorded in
the linked delivery topic, Android 17, KernelSU with system-file mounting configured.
The installer preserves permissions and original SELinux labels. The same module
ID upgrades earlier versions. Disabling it and rebooting restores the underlying
ROM and removes all module-provided rear repairs. These tools do not install,
reboot or flash the device.
