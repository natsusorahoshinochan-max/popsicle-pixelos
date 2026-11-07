# PixelOS 维护契约

## 源码与输入

设备树、平台补丁、安装 helper 和由 `POPSICLE_PROJECT_INPUTS` 读取的转换源共同组成
一次发布源码。固定基线、正式序列和原始输入分别记录身份。

vendor/ODM 在构建中从官方镜像派生，原件保持只读。构建消费本仓库维护源，
输入与输出目录显式分离。完整命令见[源码准备](../../scripts/build-support/source-release.md)。

## 原厂组件

相机、背屏和 IMS 保留原业务载荷，由准备链实现最小适配。调用身份、权限、URI、
Binder 生命周期、显示归属和失败退出条件与实际消费者一起维护。

| 范围 | 机制 |
|---|---|
| 相机 | [原厂接入](rear-camera-porting-technical-guide.md)、[DNG](camera-algorithm-port-20261006.md)、[生命周期](camera-repair-20260915.md) |
| 背屏 | [窗口与电源](rear-system-architecture-plan-20260929.md)、[素材与编辑](rear-personalization-research-20261012.md) |
| 音频与恢复 | [初始化、所有权与失败边界](repair-completeness-analysis-20260930.md) |
| 网络 | [显示等级与注册对象](mobile-signal-analysis-20260915.md) |
| 存储 | [容量和缓存口径](storage-negative-analysis-20261009.md) |

## 产品与交付

产品保持原厂硬件 ABI 和正常平台校验。交付由同一 target-files 生成镜像，
官方硬件固件来源单独标识。fastboot 安装采用指定 A16 起点的 B 槽 packed-super 契约，
完整步骤见[安装说明](fastboot-install.md)。

历史修复模块限定各自旧基线。正式 ROM 已由设备树和平台源码承接对应修改。
