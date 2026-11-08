# PixelOS 固定源码与准备流程

本页服务于 `custom_popsicle-cp2a-user`。当前版本和设备验收见[项目进度](../../docs/pixelos/progress.md)，来源与许可材料见[源码发布范围](../../docs/pixelos/source-publication.md)。

## 固定源码

上游 manifest 为 `PixelOS-AOSP/android_manifest` 的 `ec8aaaec7855bcfd57db140398f54f11c0d3d2c6`，AOSP 基线为 `android-17.0.0_r1`。
[pixelos-manifest.xml](pixelos-manifest.xml)保存 1,222 个项目的固定 revision，SHA-256 为 `7eb71e373e50eac61e2ac3380fbcdc47e9ed51f4f5f599d666bc71a4ab10ad74`。正式[补丁序列](../source-patches/pixelos-public-user.series)包含 116 条记录和 27 个仓库路径，其基线与该 manifest 一致。

在 Linux 宿主安装 Android 构建所需工具及 `repo`，将维护仓库和 Android 树放在两个独立目录。以下路径变量均替换为本项目的实际位置。

```sh
export POPSICLE_PROJECT=/path/to/popsicle-pixelos
export ANDROID_TREE=/path/to/pixelos-17
mkdir -p "$ANDROID_TREE"
cd "$ANDROID_TREE"
repo init -u https://github.com/PixelOS-AOSP/android_manifest.git \
  -b ec8aaaec7855bcfd57db140398f54f11c0d3d2c6
cp "$POPSICLE_PROJECT/scripts/build-support/pixelos-manifest.xml" \
  .repo/manifests/popsicle-resolved.xml
repo init -m popsicle-resolved.xml
repo sync --no-manifest-update -c -j4
```

manifest 中 `fetch=".."` 的 GitHub remote 按上游 manifest URL 解析。同步时保留上述来源和固定自定义 manifest。

## 设备树与项目路径

新树安装本仓库设备源码。下列复制要求目标目录尚不存在，已有维护树继续使用自己的设备树副本。

```sh
(
  set -eu
  test ! -e "$ANDROID_TREE/device/xiaomi/popsicle"
  mkdir -p "$ANDROID_TREE/device/xiaomi"
  cp -R "$POPSICLE_PROJECT/device/xiaomi/popsicle" "$ANDROID_TREE/device/xiaomi/popsicle"
  printf 'POPSICLE_PROJECT_INPUTS := %s\n' "$POPSICLE_PROJECT" \
    > "$ANDROID_TREE/device/xiaomi/popsicle/source-config.mk"
)
```

`source-config.mk` 是忽略跟踪的宿主配置。`POPSICLE_PROJECT_INPUTS` 使用无空白字符的绝对路径，指向当前维护副本。BoardConfig 要求 API 37，vendor / ODM 生产规则从该副本读取 helper。维护仓库保持在 Android 树外，模板 `Android.bp` 由所属准备工具选择安装。发布时固定本维护仓库提交，再从该提交复制设备树并安装 helper。

## 原始输入与装配

准备匹配[输入清单](source-inputs.md)的原始镜像、解包文件系统、NOTICE，以及 dex2jar。`HOST_BIN` 指向包含可执行 `aapt2` 的宿主工具目录。固定源码树自带 Linux SDK 工具，首次准备可使用 `$ANDROID_TREE/prebuilts/sdk/tools/linux/bin`，无需已有 ROM 构建输出。

```sh
cd "$POPSICLE_PROJECT"
export HOST_BIN="$ANDROID_TREE/prebuilts/sdk/tools/linux/bin"
python3 scripts/build-support/prepare-source-inputs.py \
  --android "$ANDROID_TREE" \
  --images "$OFFICIAL_IMAGES" \
  --filesystems "$OFFICIAL_FILESYSTEMS" \
  --host-bin "$HOST_BIN" \
  --dex-tools "$DEX_TOOLS"
```

原厂输入保持只读，准备结果写入 Android 树的 `vendor/xiaomi/popsicle-private/prebuilt/`。内容一致的既有固件与模板可复用，内容冲突、缺失输入和重定向输出会失败。

AICore 使用本机持有的 Google Play 完整签名 APK 集合和标准 protobuf 编译器。Linux 宿主可通过发行版的 `protobuf-compiler` 包取得 `protoc`。固定 Android 树提供 JDK 21、SDK 工具和 APK-set schema。

```sh
python3 "$POPSICLE_PROJECT/device/xiaomi/popsicle/aicore/prepare.py" \
  "$ANDROID_TREE" "$AICORE_APK_DIRECTORY" --host-bin "$HOST_BIN" \
  --protoc "$(command -v protoc)"
```

完整 APK 集合、签名及服务要求见[AICore 输入](../../device/xiaomi/popsicle/aicore/README.md)。TurboAdapter 原始 APK、R8 和 dex2jar 按[Turbo / R8 契约](../source-patches/turbo-r8/README.md)准备。正式装配后，Soong 从原始 APK、转换工具和本树真实类头生成私有 JAR。

对尚未应用正式序列的固定基线执行完整装配。

```sh
python3 scripts/source-patches/prepare-pixelos-source.py --apply "$ANDROID_TREE"
```

入口先核对全部仓库 revision、累计补丁、私有输入和维护源，再顺序应用并复制 helper。重复、部分应用和冲突会被拒绝。应用与复制跨仓库发生 I/O 失败时，按输出检查已完成范围。已有活动树已包含正式序列，只对其实际增量执行相应维护步骤。

完整新树的实际验证范围见[源码发布记录](../../docs/pixelos/source-publication.md)。便捷入口 `prepare-pixelos-inputs.py source` 默认选择固定树内的 Linux SDK 工具，也接受 `--host-bin` 显式指定工具目录。

## ROM 构建与导出

完整构建入口消费固定源码、私有输入及显式固件文件，生成 target-files 和 `generated/fastboot/`。

导出依赖安装到专用宿主环境。

```sh
python3 -m venv /path/to/build-support-venv
/path/to/build-support-venv/bin/pip install -r "$POPSICLE_PROJECT/scripts/build-support/requirements.txt"
source /path/to/build-support-venv/bin/activate
```

```sh
export OFFICIAL_PAYLOAD=/path/to/official-a17/payload.bin
export OFFICIAL_IMAGES=/path/to/extracted-a17-images
export A16_FLASH_SCRIPT=/path/to/official-a16/flash_all_macos.sh
export GOMEMLIMIT=40GiB
bash "$POPSICLE_PROJECT/scripts/build-support/build-fastboot-release.sh" \
  "$ANDROID_TREE" "$ANDROID_TREE/out-pixelos-user" "$NEW_RELEASE_DIRECTORY" pixelos
```

构建入口设置产品 `custom_popsicle-cp2a-user`、Java highmem 4 和 `-j16 -k20`，继承 `GOMEMLIMIT`。Android 的 ELF、VINTF、SELinux、NOTICE 和签名检查由原构建链执行。现有维护宿主的路径及环境见[当前决策](../../docs/pixelos/current-decisions.md#路径与执行)。

导出器消费上述三个明确输入，并核对 A17 payload 的分区清单、镜像长度和摘要，以及
A16 原始脚本声明的固件顺序。payload 的解析源码由当前仓库提供。

构建与导出命令使用已安装该依赖的 Python。构建包装器在编译开始前检查输入路径。
已显式设置的 `FIRMWARE_ROOT` 继续按 `inputs/popsicle_official_OTA_A17/payload.bin`、
`extracted/a17-payload/` 和 `inputs/popsicle_official_images_A16/flash_all_macos.sh`
解析三个数据路径。该形式与三个显式环境变量互斥。

复用同一份完整 target-files 时，直接导出到不存在的新目录。

```sh
python3 "$POPSICLE_PROJECT/scripts/build-support/export-fastboot-release.py" \
  --rom pixelos \
  --source-release "$SOURCE_RELEASE_DIRECTORY" \
  --tools-bin "$ANDROID_TREE/out-pixelos-user/host/linux-x86/bin" \
  --payload "$OFFICIAL_PAYLOAD" --firmware-images "$OFFICIAL_IMAGES" \
  --a16-flash-script "$A16_FLASH_SCRIPT" \
  --output "$NEW_EXPORT_DIRECTORY"
```

<a id="package"></a>
## 三平台打包

使用本机持有的 Linux、macOS 和 Windows SDK Platform-Tools ZIP 准备宿主工具目录。准备程序只读取所需成员，保留各平台 NOTICE 和版本属性。

```sh
python3 "$POPSICLE_PROJECT/scripts/build-support/prepare-platform-tools.py" \
  --linux "$LINUX_PLATFORM_TOOLS_ZIP" \
  --macos "$MACOS_PLATFORM_TOOLS_ZIP" \
  --windows "$WINDOWS_PLATFORM_TOOLS_ZIP" \
  --output "$NEW_TOOLS_DIRECTORY"

python3 "$POPSICLE_PROJECT/scripts/build-support/package-fastboot-release.py" \
  --name PixelOS-popsicle-RELEASE_VERSION \
  --flat-package "$NEW_EXPORT_DIRECTORY/fastboot" \
  --tools-dir "$NEW_TOOLS_DIRECTORY" \
  --output "$NEW_PACKAGE_PARENT"
```

工具目录按 `Linux/`、`macOS/` 和 `Windows/` 保存 fastboot、F2FS 格式化程序、对应动态库和许可证。已有相同布局的工具目录也可显式提供。兼容参数 `--tools-template` 与 `--tools-dir` 等价。

`--name` 选择版本目录和同名归档，支持 ASCII 字母、数字、点、下划线和连字符。省略时沿用历史名称 `PixelOS-popsicle-20260930-global-telephony-fix_by_Kanoe`。`--output` 选择父目录。打包器拒绝覆盖已有包和归档，使用 GNU tar 与 `pigz -p 16` 生成 `.tar.gz` 和 `.tar.gz.sha256`。

完整构建生成的平铺输入为 `$NEW_RELEASE_DIRECTORY/generated/fastboot`。镜像从本次导出取得，安装器从当前 `scripts/build-support/installer/` 复制，宿主工具按提供的目录打包。

仅更新已有交付包的安装器时，使用 `repackage-installer.py --source EXISTING_PACKAGE_DIRECTORY --output NEW_PACKAGE_DIRECTORY`。它复用源包镜像、工具和摘要，源包需要有效的 50 镜像清单。硬链接复制要求输入与输出位于同一文件系统。

## 导出元数据与验收

`release-result.json` 的 `complete=true` 表示导出完成，`image_count` 表示安装清单条目数，`package` 指向平铺 `fastboot/`。三平台归档另由打包步骤产生。完整构建退出码位于发布根目录的 `exit-code`，导出结果 JSON 位于 `generated/`，`READY.txt` 同时复制到发布根目录。

导出器的默认 `device_acceptance=pending-user-test-from-A16` 和 READY 文本描述生成时状态。当前设备验收由实际发布记录维护。`target_files_firmware_included=false` 表示包内官方固件单独来自原始 A17 payload。

安装行为、起点和分区保护条件见[安装说明](../../docs/pixelos/fastboot-install.md)。
