# 背屏窗口与电源结构

背屏作为独立内置显示参与 Display、WindowManager、Power 和 Dream 生命周期。
显示配置由设备树输入，Framework 和 Shell 适配由正式补丁序列装配。

## 显示与窗口

专用背屏使用官方方向映射和完整显示区域。原 SSC Home、Presentation 和相机窗口
分别处理其附着、可见性与恢复，正常 SystemUI 的主屏栏和边缘手势路由按显示归属限定。
初始显示事务、模式请求和转场清理保持单一所有权及失败收尾。

## 独立电源

背屏使用独立显示组、AOD 和 Dream 会话所有权。主屏锁定、相机占用、显示变化和
会话取消按对应 owner 恢复，原 proximity 和触摸唤醒条件保留各自消费者。
显示可查询、窗口附着与实际画面分别有自身生命周期。

## 平台接线

正式源码位于[背屏 foundation](../../scripts/source-patches/oem-rear-foundation/)、
[runtime](../../scripts/source-patches/oem-rear-runtime/)、
[Shell](../../scripts/source-patches/oem-rear-shell/)和
[服务](../../scripts/source-patches/oem-rear-service/)。
原厂资源和 APK 由[设备准备链](../../device/xiaomi/popsicle/oem-rear/)提供。

当前美化控制见[背屏美化](rear-personalization-research-20261012.md)。
完整 Settings、ThemeManager 移植的撤回范围见[历史摘要](validation.md#撤回范围)。
