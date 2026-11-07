# 相机背屏切换主屏修复模块

模块v0.1及同源完整ROM均已获用户实测确认，测试结果见[任务记录](../../docs/pixelos/validation.md)。修复已原生集成，当前发布状态见[进度](../../docs/pixelos/progress.md)。

适用于2026-09-29背屏修复版PixelOS完整ROM，通过KernelSU及用户配置的系统文件挂载实现生效。
模块ID为`popsicle-camera-handoff`。安装后重启；禁用模块并重启恢复底层ROM相机。
如仍启用了旧的相机APK覆盖模块，先禁用它，避免同路径覆盖。

维护实现是`device/xiaomi/popsicle/oem-camera/dual_screen_lifecycle.py`，已接入
`prepare.py`。从匹配原固件的私有`MiuiCamera.apk`派生，继承现有discovery、亮度和
图库适配，仅在双屏清理方法中排除已销毁Activity。完整ROM和模块使用同一准备链；
模块不作为ROM输入，不修改全局任务管理策略。

匹配旧基线的载荷由远端私有`MiuiCamera-pixelos.apk`及对应定向构建生成：

```sh
bash modules/popsicle-camera-handoff/build-candidate.sh ANDROID_TREE EVIDENCE 1790669366
python3 modules/popsicle-camera-handoff/build.py ANDROID_TREE NEW_OUTPUT_DIRECTORY
```

载荷为正常Soong平台签名的`PopsicleMiuiCamera.apk`和对应arm64 odex/vdex，
采用16线程ZIP压缩。保留原权限和SELinux文件标签。

修复针对背屏打开相机后，在主屏滑动切换提示上操作导致主屏相机退出的故障。
独立的逐项拍照与背屏重新启动结果未提供，验收范围以任务记录为准。
