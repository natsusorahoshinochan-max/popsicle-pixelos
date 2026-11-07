# popsicle PixelOS 文档

产品为 PixelOS Android 17 `custom_popsicle-cp2a-user`，硬件输入固定为
Xiaomi popsicle OS4.0.0.23.XPBCNXM。

## 源码与交付

| 内容 | 入口 |
|---|---|
| 发布范围、固定来源和当前整理状态 | [源码发布说明](source-publication.md) |
| 原厂输入、固定上游和装配 | [源码准备](../../scripts/build-support/source-release.md)、[输入清单](../../scripts/build-support/source-inputs.md) |
| 版本与反馈范围 | [当前状态](progress.md)、[历史验收摘要](validation.md) |
| 产品与维护规则 | [当前决策](current-decisions.md) |
| 来源和许可 | [源码归属](source-ownership.md) |
| 安装 | [三平台 fastboot 契约](fastboot-install.md) |
| 已知限制 | [问题索引](issues.md)、[后续备忘](pre-image-plan.md) |

## 当前机制

| 范围 | 入口 |
|---|---|
| 设备层与 PixelOS 产品层 | [设备树分层](device-layering-analysis-20260917.md) |
| 相机、CameraOpt 与背屏接口 | [原厂组件接入](rear-camera-porting-technical-guide.md) |
| 官方相机 RAW 与 UltraRAW 保存 | [DNG 保存](camera-algorithm-port-20261006.md) |
| 相机跨屏与资源生命周期 | [相机适配](camera-repair-20260915.md) |
| 背屏电源、窗口与 Dream | [背屏结构](rear-system-architecture-plan-20260929.md) |
| 背屏媒体和编辑控制 | [背屏美化](rear-personalization-research-20261012.md) |
| 导航显示和应用占位 | [导航隐藏](navigation-black-analysis-20261013.md) |
| 蜂窝显示与 NR 注册 | [移动网络](mobile-signal-analysis-20260915.md) |
| 主屏颜色模式 | [颜色模式](features-color-shade-analysis-20260915.md) |
| 音频、IMS 与恢复责任 | [运行恢复](repair-completeness-analysis-20260930.md) |
| 存储容量 | [存储口径](storage-negative-analysis-20261009.md) |
| 充电差异 | [充电范围](charging-analysis-20261009.md) |
| 历史模块挂载职责 | [元模块解耦](kernelsu-metamodule-decoupling-20261011.md) |
| 其他维护契约 | [知识索引](knowledge.md) |

历史模块的基线与安装要求在各自 README 中维护，当前产品以正式序列和设备树为准。
