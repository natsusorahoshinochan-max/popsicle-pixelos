# PixelOS 原始输入清单

使用 Xiaomi popsicle 原始 OS4.0.0.23.XPBCNXM 固件。镜像输入目录包含 payload 提取的原始镜像，文件系统输入目录包含其解包后的 `product`、`system_ext`、`vendor`、`odm`、`vendor_dlkm` 和 `system_dlkm` 子目录。原始输入保持只读，不使用其他 ROM 的派生镜像。原始 payload 的分区提取和所需 EROFS 解包使用[输入提取工具](../firmware-analysis/README.md)，输入准备在提取完成后执行。

解包文件系统用于读取原件内容，保留文件权限并使用宿主所有者，宿主目录无需承载 Android 的 SELinux 扩展属性。原始镜像保留完整 UID、GID 和扩展属性，vendor/ODM 生产链通过 `erofs_readback` 直接从镜像读取这些元数据。

准备后的私有输入放在本项目 Android 树的 `vendor/xiaomi/popsicle-private/prebuilt/`，不提交设备 Git 仓库。准备命令及顺序见[源码准备](source-release.md)；下表的目标路径均相对该私有目录。

| 私有目标 | 原始输入及转换 |
|---|---|
| `firmware-a17/{boot,dtbo,vendor_boot,vbmeta,vendor,odm,mi_product,vendor_dlkm,system_dlkm}.img` | 同名原始 payload 镜像，逐字节复制；vendor/ODM派生在构建中执行 |
| `firmware-a17/vbmeta-witness.img` | 原始vbmeta的独立副本，用于既有witness检查 |
| `firmware-a17/vendor-build.prop` | `vendor/build.prop` |
| `firmware-a17/odm-build.prop` | `odm/etc/build.prop` |
| `firmware-a17/odm-dlkm-build.prop` | `vendor/odm_dlkm/etc/build.prop` |
| `firmware-a17/{vendor,system}-dlkm-build.prop` | 对应DLKM文件系统的 `etc/build.prop` |
| `oem-abi/libbase`, `libcrypto`, `libaudioutils` | 完整 `vendor/lib64/<name>.so`、原始NOTICE映射文本及维护模板 |
| `qcc-hal` | 四个完整system_ext ELF及rc，适配唯一AIDL接口声明；[QCC源](../../device/xiaomi/popsicle/qcc/) |
| `ims` | IMS APK及四处受检查的非MIUI DEX适配、两个JNI库、QtiTelephony类路径APK、两个DEX库、权限、原厂纯资源电话overlay及NOTICE；[IMS源](../../device/xiaomi/popsicle/ims/) |
| `carrier-config` | 原始 `CarrierConfigResCommon_Sys.apk` 和 `CarrierStudioCarrierConfig.apk` 数据，按当前Framework键转换为设备RRO；[转换源](../../device/xiaomi/popsicle/carrier-config/) |
| `carrier-apns` | 原始 `product/etc/apns-conf.xml` 与PixelOS公开APN基线合并，保留受支持的选择条件及schema验证；[转换源](../../device/xiaomi/popsicle/carrier-apns/) |
| `oem-rear` | 原始 `subscreencenter.apk`、PAG JAR及native库、权限和NOTICE；适配链输出 `subscreencenter-personalization.apk`；[准备源](../../device/xiaomi/popsicle/oem-rear/) |
| `oem-camera` | 原始 `MiuiCamera.apk`、CameraOpt/算法JNI库、配置、权限和NOTICE；APK准备链接入DNG及白平衡适配；[准备源](../../device/xiaomi/popsicle/oem-camera/) |

表中输入由 `prepare-source-inputs.py` 准备。AICore单独准备到 `aicore/`，输入为本机Google Play交付的完整APK集合，见[AICore准备](../../device/xiaomi/popsicle/aicore/README.md)。TurboAdapter原始APK、dex2jar与R8输入另按[Turbo/R8契约](../source-patches/turbo-r8/README.md)准备。

背屏适配 APK 的复用记录包含原件、转换源码、工具和输出摘要。相同输入可在其他路径继续使用，源码或输入变化时重新生成；旧格式记录先与当前生成结果比对，来源冲突时需要在新的私有目录准备。

准备程序拒绝不匹配的产品版本、缺失输入、重定向的私有输出路径及内容不同的既有固件/模板。OEM库保留ELF/NOTICE检查，QCC保留精确rc和ELF检查，IMS保留指令及纯资源APK检查。内容一致的既有结果可复用。后续组件失败时，此前成功的输入可能已写入；修正具体错误后重试，保留原始固件。构建中的镜像元数据、策略、签名和target-files检查继续执行。

输入准备命令增加 `--check` 后，检查固件、属性、模板和原始OEM库字节，并调用背屏和相机的准备检查。IMS转换及完整QCC bundle由各自准备过程检查，CarrierConfig/APN转换在常规准备模式执行。当前user产品不要求SukiSU输入。
