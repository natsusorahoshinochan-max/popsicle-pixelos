# Complete AICore input

The required signed APK set was delivered by Google Play to popsicle on
2026-09-15 as `0.release.prod_aicore_20260723.00_RC11.964081323`.
It includes the framework-facing intelligence and isolated inference services.
Model inference has no accepted device result. Current integration scope is
maintained in [progress](../../../../docs/pixelos/progress.md).

`INPUT_DIRECTORY` must contain `base.apk`, `split_config.arm64_v8a.apk`,
`split_config.en.apk`, `split_config.es.apk`, `split_config.zh.apk` and
`split_config.xxhdpi.apk` from the same signed delivery. Every APK is checked
against the observed Google signing certificate, and the base APK must expose the
complete intelligence and isolated services.

## First preparation

The fixed Android tree provides JDK 21, the Linux SDK signer JAR and `aapt2`, and
the official APK-set protobuf definitions. The preparation tool invokes
`tools/linux/lib/apksigner.jar` with that JDK when the selected host directory is
`tools/linux/bin`, avoiding the SDK launcher's different JAR search layout.
A standard protobuf compiler can be
installed using the Linux distribution's `protobuf-compiler` package.

```sh
python3 device/xiaomi/popsicle/aicore/prepare.py \
  "$ANDROID_TREE" "$INPUT_DIRECTORY" \
  --host-bin "$ANDROID_TREE/prebuilts/sdk/tools/linux/bin" \
  --protoc "$(command -v protoc)"
```

`--host-bin` may instead select an existing Android host output. Direct
`apksigner` executables remain supported when the SDK JAR layout is absent.
When `--protoc`
is omitted, the tool uses `aprotoc` from that directory. The convenience
`prepare-pixelos-inputs.py aicore` entry accepts the same two options.

The tool wraps the unchanged APKs in an `android_app_set` archive under
`vendor/xiaomi/popsicle-private/prebuilt/aicore/`. Original APK signatures remain
intact. Prepare this input before building the product that selects
`PopsicleAICore`; an already prepared input is not overwritten.

Installed service availability is separate from Google model delivery and
successful inference. The original permissions, signature policy and hardware
capability checks remain active.
