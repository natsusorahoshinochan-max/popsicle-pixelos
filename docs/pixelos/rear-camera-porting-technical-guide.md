# 原厂相机与背屏接入

官方相机和背屏 App 从匹配 OS4.0.0.23.XPBCNXM 原件准备，保留原业务载荷，
由平台正常签名、权限和预优化链装配。

## 相机与 CameraOpt

[相机准备目录](../../device/xiaomi/popsicle/oem-camera/)承接能力发现、退出亮度复位、
默认图库、双屏生命周期和 RAW 保存适配。原 CameraOpt 服务装入 system-server 类路径，
平台补丁提供 DEX 引用保留、进程锁、策略名单、真实前台事件、cpuset 与线程亲和性接口。

相机原有 HAL、算法 JNI、资源和配置作为匹配输入提供。图像锁 ABI、扩展尺寸和 HEVC
封装兼容由正式平台修改承接。各补丁的依赖顺序以正式序列为准。

## 背屏

[背屏准备目录](../../device/xiaomi/popsicle/oem-rear/)保存 APK 准备、资源、PAG runtime
和几何、手势、持久化、美化适配。Framework、Shell 和 SystemUI 提供窗口、前台、
通知、媒体及显示契约。素材由 SSC 自己保存，设置入口使用受权限和签名保护的 Provider。

运行结构见[背屏窗口与电源](rear-system-architecture-plan-20260929.md)，
媒体配置见[背屏美化](rear-personalization-research-20261012.md)。

## 准备与恢复

原厂原件保持只读，派生 APK、库和 NOTICE 写入所选 Android 树的私有输入目录。
当前准备、构建及安装入口分别见[源码准备](../../scripts/build-support/source-release.md)和
[安装契约](fastboot-install.md)。
