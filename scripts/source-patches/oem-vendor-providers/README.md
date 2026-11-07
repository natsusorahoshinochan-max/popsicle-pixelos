# 原厂 vendor ABI provider

设备使用匹配 OS4.0.0.23.XPBCNXM 的 libbase、libcrypto 和 libaudioutils。
本目录的 Soong 补丁提供 vendor 变体输入选择，三个子目录保存 Blueprint 模板和原始输入准备器。
正式入口 prepare-source-inputs.py 从同版原厂文件系统读取完整 ELF 与 NOTICE，并准备到
当前 Android 树 vendor/xiaomi/popsicle-private/prebuilt/oem-abi/。

源码、宿主、其他镜像及静态变体继续由原生产者提供。原厂 provider 保留 ELF 依赖、符号、
目标 ABI 与 NOTICE 检查。源码准备步骤见[输入清单](../../build-support/source-inputs.md)和
[装配流程](../../build-support/source-release.md)。
