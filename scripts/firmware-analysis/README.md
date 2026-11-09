# 原厂 ROM 输入提取

本目录保留当前 ROM 输入准备所需的工具。原始 OS4.0.0.23.XPBCNXM `payload.bin` 保持只读，生成的分区镜像和解包文件系统放在独立输入工作区。

## A17 payload 与文件系统

Linux 宿主需要 Python 3、`payload-dumper-go`，以及支持 `--extract`、`--no-xattrs`、`--no-preserve-owner` 和 `--preserve-perms` 的 `fsck.erofs`。调用者显式提供这两个可执行工具的路径。输出目录必须尚不存在。

```sh
python3 scripts/firmware-analysis/extract-firmware-inputs.py \
  --rom "$OFFICIAL_ROM" \
  --payload-dumper /path/to/payload-dumper-go \
  --fsck-erofs /path/to/fsck.erofs \
  --output "$NEW_OFFICIAL_INPUT_DIRECTORY"
```

入口只读取官方完整 OTA ZIP 根目录下唯一的 `payload.bin`；也可用 `--payload`
直接提供原始 payload。它核对固定的 9,121,308,331 字节长度和 SHA-256，拒绝其他
版本、增量包及重复 payload 成员。只提取指定成员，不展开 ZIP 中的任意路径。

工具将已核对的 `payload.bin` 保存到输出根，从中提取全部分区镜像到 `images/`，并解包 `product`、`system_ext`、`vendor`、`odm`、`vendor_dlkm`、`system_dlkm` 和 `mi_ext` 到 `filesystems/`。`mi_ext` 用于原厂运营商扩展配置。版本检查完成后写入 `source.json` 并发布输出目录。失败时删除本次临时目录，修正工具或输入后可重跑。宿主工具的固定版本和安装步骤见[新机准备](../build-support/source-release.md)。

`filesystems/` 用于读取 APK、ELF、属性和资源等原件内容。解包时保留文件权限，使用宿主所有者，并明确关闭宿主扩展属性写入，因而可以在无法写入 `security.selinux` 的宿主文件系统中准备内容输入。完整 Android UID、GID 和扩展属性仍保存在 `images/` 的原始 EROFS 镜像内。vendor/ODM 生产工具通过 `erofs_readback` 直接读取这些镜像中的元数据，权限、SELinux 和镜像生产校验继续按原规则执行。

将 `images/` 作为 `OFFICIAL_IMAGES`，将 `filesystems/` 作为 `OFFICIAL_FILESYSTEMS`，继续执行[源码准备](../build-support/source-release.md)。已有同版原始镜像和解包文件系统也可以按[输入清单](../build-support/source-inputs.md)直接提供。

## QCC 私有输入

`prepare_qcc_hal.py` 由正式 `prepare-source-inputs.py` 调用。它从原厂 `system_ext` 准备四个 QCC ELF、服务 rc 和设备树模板，输出限定为本 Android 树的 `vendor/xiaomi/popsicle-private/prebuilt/qcc-hal`。同内容的既有结果可复用，冲突或重定向输出明确失败。
