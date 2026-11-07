# PixelOS 源码归属

## 上游与原厂输入

| 来源 | 本项目使用内容 |
|---|---|
| PixelOS、AOSP | Android 17 产品、Framework、SystemUI、Settings、构建系统和平台服务 |
| LineageOS 等 manifest 来源 | Aperture、Qualcomm CAF bootctrl 等固定上游组件 |
| Android 第三方开源项目 | EROFS、SELinux、BoringSSL、tinyxml2、Perfetto 及其他固定依赖 |
| Xiaomi OS4.0.0.23.XPBCNXM | 原厂预编译内核、boot/vendor_boot/DTBO、vendor/ODM、HAL、IMS、QCC、相机、CameraOpt 和背屏载荷 |
| Google 交付包 | GMS、Pixel 组件、TurboAdapter 原件和完整 AICore APK 集合 |

固定来源、manifest 身份和公开集合见[源码发布说明](source-publication.md)。
原厂与 Google 载荷由使用者提供，准备链保留输入身份、NOTICE、签名和 ABI 契约。

## 本项目维护内容

- popsicle 产品、分区、启动与 recovery 配置，VINTF、SELinux、资源覆盖和包选择。
- 原厂相机、CameraOpt、背屏、IMS/QCC 与 Android 平台之间的适配。
- 显示、亮度、导航、音频、网络、信号、存储等实际消费者修复。
- vendor/ODM 派生、私有输入准备、固定补丁装配、构建、导出及三平台安装工具。
- ROM 历史修复载体、当前机制说明和验收范围摘要。

生产变更同时分布在[设备树](../../device/xiaomi/popsicle/)、
[正式补丁](../../scripts/source-patches/pixelos-public-user.series)和输入准备工具中。
原厂相机 DNG、白平衡、图库与双屏适配由设备 APK 准备链承接。

## 许可材料

本项目自有源码沿用 Apache-2.0，正文见[LICENSE](../../LICENSE)。
各文件、补丁目标及第三方源码保留自身许可声明和版权，新增顶层许可的适用范围为本项目自有内容。
原厂协议适配与原厂载荷分别标识来源。

原厂内核使用匹配的预编译输入，组件算法、HAL、Google 应用和原厂 APK 保留其各自来源。
