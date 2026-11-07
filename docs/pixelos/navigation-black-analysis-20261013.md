# 导航隐藏与应用占位

导航隐藏提供可恢复的系统设置，同时隐藏手势横条和应用导航占位。
手势输入区域、侧边返回、输入法辅助按钮和三键导航恢复保留各自契约。

Framework 处理导航可见性与 inset，Settings 提供开关，设备资源提供默认导航颜色。
覆盖注册和失败重试由实际状态驱动，避免设置写入后界面来源失配。

正式实现见[导航补丁](../../scripts/source-patches/navigation-hide/)和设备产品资源。
旧 ROM 的 v0.2 模块于 2026-10-14 获用户安装通过反馈，当前完整 ROM 已内置同源修改。

跨显示、PiP、IME 与全部 overlay 组合的专项结论按实际设备反馈确定。
历史载体见[模块说明](../../modules/popsicle-hidden-navigation/README.md)，
版本范围见[验收摘要](validation.md)。
