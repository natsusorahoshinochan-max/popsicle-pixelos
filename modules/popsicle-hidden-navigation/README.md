# popsicle 隐藏手势导航栏

v0.2 使用合法覆盖优先级，修正旧失败任务覆盖新请求及回滚广播反复重试的问题，并保持 ROM 默认导航颜色。构建、交付与实测状态见[导航专题](../../docs/pixelos/validation.md)。

适用于已交付的 PixelOS Android 17 20261007 四项修复 ROM，需 KernelSU 已配置系统文件挂载。模块不检查元模块名称、ID或版本。

从旧导航模块更换时，在 KernelSU 中删除旧模块并重启，再安装 v0.2 并重启。删除标记不会立即移除当前启动中的挂载，必须完成中间这次重启才能通过 ROM 基线检查。

安装前停用会覆盖 services、SystemUI、Settings、系统服务预优化或 BuildManifest 的其它模块并重启。原背屏美化模块 v0.2 应停用，本模块包含其已验收的 Settings 页面和 SSC 适配。

进入 **设置 → 系统 → 手势 → 系统导航 → 手势导航旁的设置 → 隐藏手势导航栏**。默认关闭。开启后取消主屏应用导航占位，隐藏 Pixel Launcher 和 SystemUI 回退横条及回退导航背景；保留原始输入窗口、上滑、最近任务、左右返回、长按搜索的几何与输入法辅助按钮。关闭开关或切回三键恢复导航占位，手势隐藏偏好按用户保留。

模块使用 ROM 的原始 Pixel Launcher。安装器拒绝 APK 基线或活动 Launcher 不符、载荷冲突、权限/SELinux 设置失败。应用自己写死的底部留白无法由系统导航修复消除。编译和交付状态见[导航专题](../../docs/pixelos/validation.md)，不以定向编译代替手机实测。

停用本模块并重启恢复 ROM 文件；如需保留背屏美化，恢复启用原 v0.2 模块。无法进入系统时，可用 KernelSU 安全模式，或在能够访问 `/data` 的恢复环境创建 `/data/adb/modules/popsicle-hidden-navigation/disable` 后重启。

完整 ROM 接线由 `device/xiaomi/popsicle/navigation/` 和 `scripts/source-patches/navigation-hide/` 维护，不依赖 KernelSU 脚本实现运行功能。模块打包使用正常源码编译的 services/SystemUI/Settings、匹配预优化、原基线仅合并本模块条目的 fs-verity/签名 BuildManifest，以及两个资源覆盖 APK。

```sh
python3 modules/popsicle-hidden-navigation/build.py \
  --android ANDROID_TREE --baseline-target-files ORIGINAL_TARGET_FILES \
  --rear-v02 VALIDATED_REAR_V02_ZIP --output NEW_OUTPUT
```
