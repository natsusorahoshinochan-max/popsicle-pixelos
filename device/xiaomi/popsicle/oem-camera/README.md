# Official camera inputs

`prepare.py ANDROID_TREE OFFICIAL_A17_FILESYSTEMS --host-bin HOST_EXECUTABLE_DIRECTORY`
prepares matching OS4.0.0.23.XPBCNXM camera and CameraOpt inputs under
`vendor/xiaomi/popsicle-private/prebuilt/oem-camera`. Original proprietary inputs
remain read-only and are never committed.

The preparation chain derives `MiuiCamera-pixelos.apk` from the original APK:

- `CameraVendorDiscovery.java` selects the original vendor descriptor enumeration.
- `brightness_reset.py` preserves temporary brightness cancellation semantics.
- `default_gallery.py` connects the original gallery entry to the system gallery.
- `dual_screen_lifecycle.py` excludes destroyed activities before cross-display
  cleanup, preventing a stale instance from finishing the relaunched camera.

The same preparation chain also carries the 50M/UltraRAW DNG saving, preview and
failure cleanup repairs, plus the UltraRAW v0.3 same-capture white balance repair.
Their implementation is tracked in the [camera record](../../../../docs/pixelos/camera-algorithm-port-20261006.md).

The original resources, algorithms and embedded native libraries remain intact.
Preparation rejects unexpected input and conflicting output, while allowing known
previous adaptations to upgrade. `--check` checks the prepared inputs without
writing them.

`PopsicleMiuiCamera` is installed in `system_ext/priv-app`, platform-signed and
preoptimized by the normal Android build. The product retains permissions,
uses-library, ELF and NOTICE checks. CameraOpt uses the ordinary edition and shared
process policy, with no Lite branch. `process_policy.py` prepares that policy from
the matching original framework resources.

The full ROM and earlier KernelSU test modules use this preparation chain. The
integrated ROM uses its built-in camera adaptation. Disable or remove the corresponding old override before
installation. See the [handoff implementation](dual_screen_lifecycle.py)
and [current release and acceptance](../../../../docs/pixelos/progress.md).
