# Popsicle PixelOS fingerprint icon trial

The repair is part of the formal ROM. Implementation and acceptance limits are
maintained in the [fingerprint topic](../../docs/pixelos/validation.md).
Current delivery status is maintained in [progress](../../docs/pixelos/progress.md).
Disable or uninstall this historical module and reboot before upgrading, or to
restore the underlying ROM resources.

This KernelSU module carries the ROM-built, platform-signed
`PopsicleFingerprintIcon` resource overlay. The sole resource override is
`com.android.systemui:dimen/pixel_pitch=60.5833` microns per physical pixel.
The source is `device/xiaomi/popsicle/rro/FingerprintIcon`, selected by the
PixelOS product and included in the delivered ROM.

The following historical module instructions require popsicle PixelOS Android 17, the accepted 20260930 global-telephony ROM
(build date 1790747209), KernelSU with system-file mounting configured. Install the ZIP in
KernelSU and reboot. It adds a product resource overlay and can coexist with the
official signal-threshold module.

The overlay repairs the cropped dark shape above the lockscreen fingerprint
circle. The topic record contains the build result and user feedback for this
visual repair. AOD and rotation scenarios await separate validation.

## Historical carrier packaging

For maintenance of the fixed-baseline carrier, build `PopsicleFingerprintIcon`
in `out-pixelos-user`, then run the following command.

```sh
bash modules/popsicle-fingerprint-icon/build.sh ANDROID_SOURCE_ROOT NEW_OUTPUT_DIRECTORY
```

The packager copies the existing ROM output, uses 16 ZIP workers and generates
a SHA256 companion. ZIP is the KernelSU installation format.
