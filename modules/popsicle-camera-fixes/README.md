# 相机修复增量模块

本目录保留面向2026-09-16测试基线1789465178的PixelOS Android 17 KernelSU载荷。
同源维护补丁和相机APK适配已集成正式ROM，当前发布状态见[进度](../../docs/pixelos/progress.md)。

## 内容

- `system/bin/cameraserver`：保留 Mock 与普通小米相机的已声明输出尺寸，扩展 JPEG 容量。
- `system_ext/priv-app/PopsicleMiuiCamera/`：正式平台签名 APK 和匹配 odex/vdex；使用系统
  `ACTION_VIEW` / `CATEGORY_APP_GALLERY` 解析，有锁屏时先解锁，启动失败不提交图库状态。

安装器检查 popsicle、SDK 37、构建时间及其他启用模块的同路径覆盖。保留 cameraserver 的
可执行权限和原 SELinux 标签。通过 KernelSU 安装，系统文件覆盖由用户配置的挂载实现负责。
在该匹配基线上停用 `popsicle-camera-fixes` 并重启，可恢复底层ROM。

## 构建

维护匹配旧基线的载荷时，在[项目规定的远端树](../../docs/pixelos/current-decisions.md)完成 `cameraserver`、
`PopsicleMiuiCamera` 的定向构建后，运行：

```sh
python3 modules/popsicle-camera-fixes/build.py ANDROID_TREE OUTPUT_DIRECTORY \
  --baseline-date VERIFIED_DEVICE_RO_SYSTEM_BUILD_DATE_UTC
```

`baseline-date` 来自目标完整 ROM，不能使用当前增量构建临时生成的时间替代。禁止覆盖旧输出目录。

该次实施、编译及设备验证边界见[修复记录](../../docs/pixelos/validation.md)。

模块已在上述基线安装，用户确认图库与50M拍照测试通过；同源完整ROM的用户反馈见[整包总结](../../docs/pixelos/validation.md)。
