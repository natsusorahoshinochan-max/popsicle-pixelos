# Popsicle PixelOS ARR 调试模块

v0.6已通过用户实机验证，同源XML配置及源码修复已集成正式ROM。当前发布状态见[进度](../../docs/pixelos/progress.md)。模块载荷覆盖主屏 product 显示 XML、services.jar 及配套 profile/预编译/verity 文件、libandroid_servers.so、libgui.so 和 surfaceflinger。

XML 新增 `preferArrByDefault=true`，与已有 `supportsVrr` 能力声明分离。SurfaceFlinger 通过受权限保护的查询返回真正带 VRR 配置的模式 ID；framework 在同分辨率、同默认峰值帧率的候选中选择 ARR。没有合适候选时保持原默认模式。模式选择使用实际VRR能力与原生事件路径；实现没有固定模式编号、专用debug属性、开机调试事务或常驻强制锁。

空闲超时使用已有 `idleScreenRefreshRateTimeout` XML，测试值为全光照范围 1000ms。该次验证停用了原 `popsicle-refresh-idle`，排除旧参数介入。

运行中能力同步使用有界重试：仅未完成模式切换每 50ms 重读原生状态，最多 20 次；完成、断开或新模式替换旧请求。支持帧率列表沿用原事件路径。

本目录不提交编译 payload，不能直接压缩安装。安装器核对设备及原生/framework 基线哈希，设置正确的可执行权限和 SELinux 标签。必须使用同次构建的全部匹配组件。在安装器匹配的旧基线上停用ARR模块并重启，可恢复底层ROM文件。此前普通模式idle模块同属旧调试基线。

补丁入口见 [ARR 序列](../../scripts/source-patches/display-arr/series)。实测状态见 [ARR 验证](../../docs/pixelos/validation.md)。
