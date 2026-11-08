# Xiaomi popsicle: PixelOS Android 17

Device configuration for Xiaomi `popsicle` (2509FPN0BC), using the
fixed PixelOS `seventeen` source and OS4.0.0.23.XPBCNXM official hardware inputs.
The sole product is `custom_popsicle-cp2a-user`.

This project independently owns this device tree and its companion tools.
It uses the official prebuilt kernel, boot/vendor_boot/DTBO and selected firmware
filesystems. Vendor and ODM are derived with this project's maintained tools;
another ROM's derived images are not inputs.

## Source and build environment

Use the [PixelOS source preparation guide](../../../scripts/build-support/source-release.md)
and [official input inventory](../../../scripts/build-support/source-inputs.md).
The companion belongs outside the Android tree so its diagnostic and template
Android.bp files are not discovered as product modules.

The ignored `source-config.mk` resolves tools to the independently maintained
project checkout. Set its absolute path for the current host.

```make
POPSICLE_PROJECT_INPUTS := /path/to/popsicle-pixelos
```

This local override is not a source-release file. Both device and helper sources
must come from the independent PixelOS maintenance project.
Proprietary inputs stay below `vendor/xiaomi/popsicle-private/prebuilt/`.

## Product behavior and validation

The user product builds normal uninjected init_boot. A/B, dynamic partitions,
recovery and update_engine remain enabled. OEM Face is selected; PixelOS owns the
WebView provider configuration, so the old device WebView RRO is not installed.
The public AVB key named `popsicle-userdebug.avbpubkey` remains a required input;
the filename does not select a userdebug product. Keep the Bootloader unlocked.

Build and delivery results and device acceptance records are maintained in
[progress](../../../docs/pixelos/progress.md).
Installation and recovery requirements are in the
[PixelOS installation contract](../../../docs/pixelos/fastboot-install.md).

## Source ownership and license

Original project source is Apache-2.0; see [LICENSE](LICENSE). Retain existing
upstream notices for their respective material. File comments and evidence
record the provenance of OEM extracts.
Maintain the generated AIDL API through the normal update-api target.
APK, ELF, partition images and signing secrets do not belong in this device Git
repository. The AVB public key is an intentional source input.

Legacy HAL/effects probes are retained in the companion `scripts/device-debug/`.
Verify each probe's actual PixelOS consumer before source reuse.
