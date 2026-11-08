# 主屏三模式修复（旧模块已撤回）

v0.1和v0.2均已撤回，请勿安装。KernelSU报告已确认实际挂载目录中SurfaceFlinger被截断、文件和目录为unlabeled，旧启动日志捕获基础库加载失败及bpfloader触发重启。故障记录见[颜色专题](../../docs/pixelos/validation.md)。

正式 ROM 已集成[原厂 sRGB 选择](../../scripts/source-patches/display-color/0002-select-oem-expert-srgb.patch)和[主屏色彩意图](../../scripts/source-patches/display-color/0003-main-panel-srgb-intent.patch)补丁，集成与验收范围见[发布记录](../../docs/pixelos/validation.md)。安装 ROM 前停用或卸载对应旧覆盖模块。

## 保留的实现与版本边界

自然及增强向原厂 HAL 发送主屏专家 sRGB 请求 26/3/0，清除前态 vendor LUT。SurfaceFlinger 只对主屏 managed SDR sRGB 输出选择 267，增强保留 AOSP 的 1.1 倍饱和度。鲜艳沿用 AOSP unmanaged/native 与原厂 effect1。模式切换使用现有颜色设置和亮屏重应用入口，沿用正常 SELinux 策略。

旧模块仅面向 2026-10-03 交付的七项修复版（`ro.system.build.date.utc=1790954511`）。载荷为 services.jar 及 ART/verity 配套、签名 BuildManifest 和 surfaceflinger，通过 KernelSU 及用户配置的系统文件挂载实现覆盖文件。v0.2 只修正了暂存源目录的 SurfaceFlinger 标签，后续复制路径仍存在失败问题。

修复范围为主屏三模式 SDR sRGB 切换。P3/HDR 保留框架选择分支，P3/HDR 场景及原厂 HAL 专家状态与其他内容的交互仍待专项验证。
