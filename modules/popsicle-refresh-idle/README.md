# 主屏空闲刷新率参数实验

此历史模块将主屏 `4630946457447247251` 的 SurfaceFlinger 空闲计时设置为 1000 ms。它保留原触摸提升和用户刷新率限制，独立于正式 ARR 能力选择及同步实现。

`system.prop` 保存原参数，`skip_mount` 表示此载体通过属性工作。正式 ARR 修复的历史验收已停用该参数模块。当前 ROM 的实现及范围见[进度](../../docs/pixelos/progress.md)和[验证摘要](../../docs/pixelos/validation.md)。
