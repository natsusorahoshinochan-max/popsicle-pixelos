# PixelOS popsicle 存储统计修复

面向原始 `PixelOS-popsicle-20261014-navigation_by_Kanoe.tar.gz`。覆盖这版 ROM 的 Settings APK，保留其中已有的导航隐藏、背屏美化和其它设置。安装器同时核对设备、Android 版本、ROM 构建时间、活动 Settings 路径和 APK 摘要。

当系统提供的标称内置容量小于 `/data` 文件系统时，Settings 的共用统计入口改用 StorageManager/vold 提供的实际物理盘容量。系统占用、总量、已用容量及临时文件分类使用同一总量，外置卷和容量正常的设备沿用原返回值。实际总容量可能显示约 527 GB，具体数值以该 API 的设备返回值及文件系统预留空间为准。

修复使用新的、按用户隔离的存储统计缓存名称，避免沿用旧负值。原 Settings 数据和旧缓存保留。

## 安装与恢复

1. 停用其它覆盖 Settings 的模块并重启。
2. 在 KernelSU 中安装 `popsicle-storage-accounting-v0.1.zip`，完成后重启。
3. 打开设置 → 存储空间，等待统计完成，检查总容量、系统 → Android 17 及临时文件。

KernelSU 需已配置系统文件挂载。载荷包含完整 DEX，并以本 ROM 的平台证书签名。安装使用 KernelSU 标准 `REPLACE` 隐藏原 APK 的 `oat` 目录，由 ART 在 `/data` 正常编译新 APK，首次启动可能较慢。

停用或卸载本模块并重启，恢复 ROM 原 Settings 和原预优化文件。无法进入系统时，可使用 KernelSU 安全模式，或在能够访问 `/data` 的恢复环境创建 `/data/adb/modules/popsicle-storage-accounting/disable` 后重启。

用户于 2026-11-06 确认 v0.1“已经测试通过”，反馈按模块整体记录。模块的本机回归、构建和交付记录，以及随后完整 ROM 的用户反馈，统一见[存储专题](../../docs/pixelos/validation.md)。

## 本机构建

`build.py` 消费 20261014 原始 target-files 中的 Settings、同项目 Android 框架 header JAR、本项目平台签名密钥，以及已应用本项目两条存储补丁的源码子集。先从原始 APK 精确替换三个现存容量调用入口和缓存名称，再加入以 Java 编译的共用 helper，资源、清单和其它 ZIP 条目保留原始内容。

```sh
python3 modules/popsicle-storage-accounting/build.py \
  --baseline-apk INPUT/Settings.apk \
  --framework-header INPUT/framework.jar \
  --source PATCHED_ANDROID_SOURCE \
  --java-home /opt/homebrew/opt/openjdk@21/libexec/openjdk.jdk/Contents/Home \
  --build-tools "$HOME/Library/Android/sdk/build-tools/37.0.0" \
  --cert PROJECT_PLATFORM_CERT --key PROJECT_PLATFORM_PK8 \
  --output NEW_OUTPUT_DIRECTORY
```

正式实现由[存储统计补丁](../../scripts/source-patches/storage-accounting/README.md)维护。当前完整 ROM 已内置此修复，安装前应停用或卸载本模块，避免旧 APK 覆盖 ROM 文件。

挂载/目录替换契约参考 [KernelSU 模块文档](https://kernelsu.org/guide/module.html#system-directory)。
