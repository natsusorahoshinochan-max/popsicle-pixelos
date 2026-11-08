# PixelOS 历史修复模块

本目录保存 24 个 ROM 修复载体和旧参数实验的维护源码。各子目录保留原适用基线、载荷、安装器和打包方式。已集成修复的正式实现由设备树和[生产补丁序列](../scripts/source-patches/pixelos-public-user.series)维护，当前交付与验收范围见[进度](../docs/pixelos/progress.md)和[验证摘要](../docs/pixelos/validation.md)。

历史模块按原基线冻结。安装器中的构建时间、APK 摘要、载荷冲突、权限和 SELinux 检查继续执行。升级包含同源修复的 ROM 前，停用或卸载覆盖相同文件的旧模块。

| 范围 | 目录 |
|---|---|
| 显示、亮度与状态栏 | `popsicle-arr`、`popsicle-brightness-curve`、`popsicle-brightness-startup`、`popsicle-statusbar-alignment` |
| 原厂相机 | `popsicle-camera-dng`、`popsicle-camera-fixes`、`popsicle-camera-handoff` |
| 原厂 App 与背屏 | `popsicle-oem-app-port`、`popsicle-rear-boot-fix`、`popsicle-rear-features`、`popsicle-rear-personalization` |
| 系统修复 | `popsicle-audio-fixes`、`popsicle-feature-fixes`、`popsicle-fingerprint-icon`、`popsicle-hidden-navigation`、`popsicle-media-shade-fixes`、`popsicle-nav-rotation-fix`、`popsicle-storage-accounting` |
| 运营商与信号 | `popsicle-global-telephony`、`popsicle-nr-registration`、`popsicle-signal-display` |
| 共用历史打包 | `popsicle-repair-parts`、`build-resource-overlay.sh`、`resource-overlay-customize.sh` |
| 已撤回的颜色覆盖 | `popsicle-color-modes`，保留撤回状态 |
| 旧刷新率参数实验 | `popsicle-refresh-idle`，独立于正式 ARR 修复 |

历史版本记录中的补丁序号沿用来源提交的原 128 条维护序列。当前实现通过各模块链接的补丁路径定位，装配顺序由生产序列确定。历史构建命令要求匹配的 Android 树、私有输入、签名和构建产物，宿主目录由调用者提供。源码准备及当前工具环境见[构建说明](../scripts/build-support/source-release.md)。

源码发布范围和固定来源见[发布说明](../docs/pixelos/source-publication.md)。
