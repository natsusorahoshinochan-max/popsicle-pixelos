# PixelOS 亮度启动修复模块 v0.7

仅适用于安装器核对的 popsicle PixelOS Android 17 services.jar 基线；同源修复已集成正式ROM，当前发布状态见[进度](../../docs/pixelos/progress.md)。源码补丁见 [brightness-startup](../../scripts/source-patches/brightness-startup/README.md)。

本包沿用 `popsicle-arr` 模块 ID，升级时只有一个 services.jar 所有者。该模块匹配的旧ROM已集成ARR 的原生库、XML 和 framework 修改；本包保留 framework ARR 代码，只投递对应构建的services.jar 和匹配的 profile、oat、verity 伴随产物。旧版 ARR 测试 ROM 不在兼容范围内。

在上述匹配基线上通过KernelSU管理器安装生成的ZIP，重启生效。停用 `popsicle-arr` 后重启恢复 ROM 原有 framework。系统文件覆盖由用户在 KernelSU 中配置的挂载实现负责；不修改 init_boot，不写 brightness 设置，不包含常驻脚本，不改已确认的亮度曲线。

修复处理超过 1 秒的首次缓存样本，启用后 2 秒内的新事件可触发一次重新初始化和正常快速渐变。缺少新事件时继续使用缓存兜底。用户已确认修复有效，各唤醒场景的首帧表现仍待逐项确认。

生成方式：远端先按项目参数构建 services 及配套安装产物，再调用 `build-module.sh ANDROID_TREE OUTPUT_DIR`；输出目录须为新目录。构建脚本只包装，不安装或重启。
