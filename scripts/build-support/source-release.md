# PixelOS 新机准备、构建与交付

本页面向 Linux x86_64 普通构建用户，产品为 `custom_popsicle-cp2a-user`。
宿主命令按 Ubuntu 22.04、Python 3.10 或更高版本编写。
维护仓库、Android 树、原件和输出都放在同一工作根的不同目录，路径不含空白。
原件为 `OS4.0.0.23.XPBCNXM` 完整官方 OTA ZIP，以及[完整 AICore 六分包](../../device/xiaomi/popsicle/aicore/README.md)。
也可提供从该 OTA 取得的原始 `payload.bin`。原件保持只读。

## 1. 克隆与配置

```sh
mkdir -p /path/to/pixelos
cd /path/to/pixelos
git clone https://github.com/natsusorahoshinochan-max/popsicle-pixelos.git project
cd project
cp .env.example .env
# 编辑 .env 中工作根、维护仓库、官方 OTA 和 AICore 的绝对路径。
source .env
```

`.env` 不入 Git。宿主建议至少 64 GiB RAM；`BUILD_JOBS` 和 `NINJA_HIGHMEM_NUM_JOBS`
按资源设置，默认为 8 和 2。`GOMEMLIMIT=40GiB` 是 Soong 的 Go 堆软限制。
源码、固件和完整 OUT 合计需要数百 GiB 空间。准备、编译和导出使用同一
普通用户拥有的目录。现有服务器的专用 UID 运行器属于该宿主配置，新机器直接运行本文命令。

## 2. 宿主依赖

Ubuntu/Debian 系宿主安装构建与输入准备工具；以下是系统包安装步骤，其余命令由普通用户执行。

```sh
sudo apt-get update
sudo apt-get install git git-lfs gnupg build-essential gcc-multilib g++-multilib \
  python3 python3-venv python3-pip flex bison zip unzip curl rsync bc \
  libncurses-dev lib32z1-dev zlib1g-dev liblz4-dev liblzma-dev libzstd-dev \
  uuid-dev libselinux1-dev libxml2-utils protobuf-compiler pigz \
  autoconf automake libtool pkg-config golang-go xsltproc fontconfig \
  libc6-dev-i386 x11proto-core-dev libx11-dev libgl1-mesa-dev
git lfs install
mkdir -p "$POPSICLE_WORKSPACE/env" "$POPSICLE_WORKSPACE/tools/bin"
python3 -m venv "$POPSICLE_WORKSPACE/env/build-support-venv"
source "$POPSICLE_WORKSPACE/env/build-support-venv/bin/activate"
python3 -m pip install -r "$POPSICLE_PROJECT/scripts/build-support/requirements.txt"
```

使用 [AOSP 官方 Repo launcher](https://source.android.com/docs/setup/start/requirements#install-repo)，
避免发行版旧 launcher 在初始化前拒绝 `--git-lfs`：

```sh
curl -fL https://storage.googleapis.com/git-repo-downloads/repo \
  -o "$POPSICLE_WORKSPACE/tools/bin/repo"
chmod 755 "$POPSICLE_WORKSPACE/tools/bin/repo"
export PATH="$POPSICLE_WORKSPACE/tools/bin:$PATH"
repo --version
```

固件工具使用已核对的固定源码提交。Go 模块保留其依赖校验，EROFS 使用独立工具目录。
以下工具安装命令用于首次配置；已安装同版工具可直接设置 `.env` 中的两个工具路径。

```sh
GOBIN="$POPSICLE_WORKSPACE/tools/bin" \
  GOCACHE="$POPSICLE_WORKSPACE/work/cache/go-build" \
  GOMODCACHE="$POPSICLE_WORKSPACE/work/cache/go-mod" \
  go install github.com/ssut/payload-dumper-go@a51234eaead276ff3d8b8c4c439c51c7f46a96a8
(
  set -eu
  git init "$POPSICLE_WORKSPACE/tools/erofs-utils"
  cd "$POPSICLE_WORKSPACE/tools/erofs-utils"
  git remote add origin https://git.kernel.org/pub/scm/linux/kernel/git/xiang/erofs-utils.git
  git fetch --depth=1 origin f36cadb5c563995ab3aa8572a60ed6b721b9557d
  git checkout --detach FETCH_HEAD
  ./autogen.sh
  ./configure --prefix="$POPSICLE_WORKSPACE/tools/erofs" --disable-fuse
  make -j4
  make install
)
```

EROFS 固定版本为 1.9.4，要求支持 `--extract`、`--no-xattrs`、`--no-preserve-owner`
和 `--preserve-perms`。Android 固定树提供 JDK 21、SDK、smali 和 Apktool。
R8 9.3.19 与 dex2jar 2.4 由后面的准备入口下载并按[依赖清单](../source-patches/turbo-r8/dependencies.json)校验。
若官方下载临时不可用，可把从同一官方地址取得的归档放入
`$POPSICLE_WORKSPACE/tools/downloads/`，文件名保持不变；入口仍核对固定摘要。

## 3. 同步固定 Android 源码

上游 manifest 提交为 `ec8aaaec7855bcfd57db140398f54f11c0d3d2c6`，AOSP 为
`android-17.0.0_r1`。[固定清单](pixelos-manifest.xml)含 1,222 个项目 revision，
SHA-256 为 `7eb71e373e50eac61e2ac3380fbcdc47e9ed51f4f5f599d666bc71a4ab10ad74`。

```sh
mkdir -p "$ANDROID_TREE"
cd "$ANDROID_TREE"
repo init -u https://github.com/PixelOS-AOSP/android_manifest.git \
  -b ec8aaaec7855bcfd57db140398f54f11c0d3d2c6 --depth=1 --git-lfs --repo-rev=v2.66.1
cp "$POPSICLE_PROJECT/scripts/build-support/pixelos-manifest.xml" .repo/manifests/popsicle-resolved.xml
repo init -m popsicle-resolved.xml --git-lfs
repo sync --no-manifest-update -c -j4
```

`fetch=".."` 的 remote 按上述上游 URL 解析。Git LFS 必须取得 Google APK/APEX
的实际内容；LFS 指针文本不是可编译输入。固定提交保持不变，适配通过正式补丁应用。

## 4. 准备输入与设备树

```sh
cd "$POPSICLE_PROJECT"
python3 scripts/build-support/prepare-pixelos-inputs.py all \
  --android "$ANDROID_TREE" --workspace "$POPSICLE_WORKSPACE" \
  --rom "$OFFICIAL_ROM" --aicore "$AICORE_ORIGINALS" \
  --payload-dumper "$PAYLOAD_DUMPER" --fsck-erofs "$FSCK_EROFS"
```

已有原始 payload 时，将 `--rom "$OFFICIAL_ROM"` 换为 `--payload /path/to/payload.bin`。
入口只接受固定版本完整 payload 的长度和 SHA-256。ZIP 中只读取唯一的根目录
`payload.bin`，不执行固件附带脚本。输出为 `work/firmware/OS4.0.0.23.XPBCNXM/`
下的 `payload.bin`、`images/`、`filesystems/` 和 `source.json`。

入口顺序准备固定 R8/dex2jar、从上游读取并核对 TurboAdapter，提取固件，然后调用
现有 OEM、IMS、QCC、相机、背屏及 AICore 准备器。私有结果放在 Android 树的
`vendor/xiaomi/popsicle-private/prebuilt/`。已有带 `source.json` 的固件提取目录
会核对 payload 身份后复用；后续文件完整性继续由各准备器和正式构建/导出校验。
旧布局提取目录不会自动接管。后续步骤失败时保留已成功结果，修正具体输入后重跑。
固定下载、固件副本、模板和 AICore 内容冲突会失败；运营商配置、APN 等派生结果
仍由现有生成器更新。单独步骤仍可使用 `source`、`aicore`、`carrier` 子命令。

新 Android 树安装设备树并应用正式序列：

```sh
(
  set -eu
  test ! -e "$ANDROID_TREE/device/xiaomi/popsicle"
  test ! -L "$ANDROID_TREE/device/xiaomi/popsicle"
  mkdir -p "$ANDROID_TREE/device/xiaomi"
  cp -R "$POPSICLE_PROJECT/device/xiaomi/popsicle" "$ANDROID_TREE/device/xiaomi/popsicle"
  printf 'POPSICLE_PROJECT_INPUTS := %s\n' "$POPSICLE_PROJECT" \
    > "$ANDROID_TREE/device/xiaomi/popsicle/source-config.mk"
  python3 "$POPSICLE_PROJECT/scripts/source-patches/prepare-pixelos-source.py" --apply "$ANDROID_TREE"
)
```

[正式序列](../source-patches/pixelos-public-user.series)为 116 条补丁、27 个仓库。
设备树、helper 和补丁来自同一维护提交。完整装配只用于未应用序列的固定基线；
已有活动树按实际增量维护，不能再次套用完整序列。

## 5. 构建与导出

重新打开 shell 时加载 `.env` 和上述 venv。将 `NEW_VERSION` 替换为尚不存在的版本名。

```sh
export NEW_RELEASE_DIRECTORY="$POPSICLE_WORKSPACE/releases/NEW_VERSION"
ulimit -n 32768
bash "$POPSICLE_PROJECT/scripts/build-support/build-fastboot-release.sh" \
  "$ANDROID_TREE" "$POPSICLE_OUT" "$NEW_RELEASE_DIRECTORY" pixelos
```

入口生成 `target_files.zip` 和 `generated/fastboot/`，继续执行 ABI、VINTF、SELinux、
NOTICE、签名、镜像和 super 校验。导出器按[安装契约](firmware-install-contract.json)
确定 42 个 A17 固件的顺序与目标槽位；该数据从原始 A16 脚本提取并记录其摘要。
仍检查 58 个 payload 分区、完整包身份、长度和摘要。日常构建无需提供 A16 脚本；
`--a16-flash-script` 仅保留为独立交叉核对参数，旧 `--firmware-root` 布局仍可使用。

复用已有 target-files 独立导出时：

```sh
export EXPORT_HOST_BIN="$POPSICLE_OUT/host/linux-x86/bin"
export LD_LIBRARY_PATH="$(dirname "$EXPORT_HOST_BIN")/lib64${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"
python3 "$POPSICLE_PROJECT/scripts/build-support/export-fastboot-release.py" \
  --source-release "$SOURCE_RELEASE_DIRECTORY" --tools-bin "$EXPORT_HOST_BIN" \
  --payload "$OFFICIAL_PAYLOAD" --firmware-images "$OFFICIAL_IMAGES" \
  --output "$NEW_EXPORT_DIRECTORY"
```

若 OUT 已清理，使用对应版本保存的 `export-host/bin` 和相邻 `lib64`。现有服务器
20261109 成品保留了这两者。`READY.txt` 与 `complete=true` 表示生成完成，设备验收
状态由实际发布记录维护。

<a id="package"></a>
## 6. 三平台打包

从 [Android SDK 官方分发](https://developer.android.com/tools/releases/platform-tools)取得
Linux、macOS、Windows Platform-Tools ZIP，设置下列
三个 ZIP 路径与新工具目录。准备器保存各平台 NOTICE 和版本信息。

```sh
python3 "$POPSICLE_PROJECT/scripts/build-support/prepare-platform-tools.py" \
  --linux "$LINUX_PLATFORM_TOOLS_ZIP" --macos "$MACOS_PLATFORM_TOOLS_ZIP" \
  --windows "$WINDOWS_PLATFORM_TOOLS_ZIP" --output "$NEW_TOOLS_DIRECTORY"
python3 "$POPSICLE_PROJECT/scripts/build-support/package-fastboot-release.py" \
  --name PixelOS-popsicle-RELEASE_VERSION \
  --flat-package "$NEW_RELEASE_DIRECTORY/generated/fastboot" \
  --tools-dir "$NEW_TOOLS_DIRECTORY" --output "$NEW_PACKAGE_PARENT"
```

打包器生成三平台安装入口、包内摘要、`.tar.gz` 和归档摘要，拒绝覆盖已有交付。
安装起点与设备分区约束见[安装说明](../../docs/pixelos/fastboot-install.md)。
实际验证范围见[源码发布记录](../../docs/pixelos/source-publication.md)。
