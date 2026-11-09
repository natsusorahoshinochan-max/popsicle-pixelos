# popsicle PixelOS 当前状态

## 源码

当前独立 ROM 发布快照已于 2026-11-08 通过全新完整构建、静态内容审查、
50 镜像导出和三平台打包。本次成品的真机运行验收待完成。
范围、固定来源和验证结果集中记录于
[源码发布说明](source-publication.md)。新树准备使用裁剪后的生产补丁序列。

日常维护使用服务器 `/root/autodl-tmp/pixelos-popsicle/`。三项目目录迁移已完成，
旧混合入口和一次性迁移、测试工具已清理。最终路径于 2026-11-09 完成全新构建、
50 镜像导出和三平台打包，成品保存在 `releases/20261109/`。

## 已有成品

最近一次已交付成品为 `PixelOS-popsicle-20261106-storage-fix_by_Kanoe.tar.gz`，
包含 50 镜像及 Windows、macOS、Linux 安装入口。它集成存储容量修复，继承导航隐藏、
背屏美化及此前修复。用户于 2026-11-07 确认“测试完成”，反馈未附逐场景明细。

该成品使用原维护序列的 124 条状态。当前发布快照的源码身份和验证范围单独维护。
版本与已知撤回记录见[历史验收摘要](validation.md)。

## 挂起事项

充电差异、PCC 与 5G+、VPN UID 路由失败恢复、Bluetooth provider 会话恢复及
AICore 模型清单仍有未决范围，见[后续备忘](pre-image-plan.md)。

构建从[源码准备](../../scripts/build-support/source-release.md)进入，设备安装遵循
[安装契约](fastboot-install.md)。
