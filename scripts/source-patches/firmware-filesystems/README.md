# 原厂 EROFS 文件系统生产

当前产品从匹配 OS4.0.0.23.XPBCNXM 的原始 vendor、ODM 和 DLKM 输入生成所需镜像。
[正式序列](../pixelos-public-user.series) 安装 Make/Soong 生产规则，
prepare-public-source.py 把本目录的维护 helper 安装到 external/erofs-utils/popsicle/。
完整步骤见[源码准备](../../build-support/source-release.md)。

## 文件系统与 staging

erofs_readback.c 通过固定 liberofs 直接读取镜像，保留完整 inode、二进制 xattr 和硬链接信息。
derive_vendor.py 生成 PAX tar 并重建 EROFS，验证原始文件、元数据、UUID、块大小和功能标志。
stage_inputs.py 消费真实产品文件清单、模块 build/install 边、fs_config 和 SELinux contexts。
新增文件的所有者、模式、标签与 capability 取自 Android 的实际生产结果。

ODM 使用 camera_id_buffer.py、camera_device_config.py 和 ../camera-extensions/patch-chi.py
的精确 patch_elf 变换。odm_image.py 保留未修改的字节、元数据及原始策略，只合并声明的
相机变换和来源 NOTICE。完整产品入口要求对应 staging、文件清单和元数据参数。

## 策略、签名与 target-files

vendor_policy.py 消费本目录 policy/ 的维护源，以及原始镜像和当前平台策略生产者。
派生过程保持 neverallow、宏和版本约束，并与正常平台校验连接。
policy-producers/mediacodec.te 和 NOTICE 保存该固定 QSSI 输入的来源。

vendor_avb.py、odm_avb.py 与 target-files helper 负责镜像容量、签名、FEC 及目录和 ZIP
视图的一致性。原始输入保持只读，已有输出冲突会失败。安装起点与分区保护条件见
[安装契约](../../../docs/pixelos/fastboot-install.md)。

## 固定源码

host-tools.patch 面向 manifest 固定的 erofs-utils 1.8.3，提供读取器与 vendor/ODM host
工具，并修正 workers 参数解析、LIBARCHIVE Base64 xattr 解析和 Soong 纳秒时间字段配置。
当前安装的 helper 以本目录维护源为准。相机变换源直接从当前 ROM 维护 checkout 读取。
