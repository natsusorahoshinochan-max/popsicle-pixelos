# Xiaomi popsicle PixelOS

Xiaomi `popsicle` 的 PixelOS Android 17 设备适配源码，产品为
`custom_popsicle-cp2a-user`。本仓库维护设备树、固定平台补丁、原厂组件适配、
输入准备及三平台交付工具。

| 内容 | 入口 |
|---|---|
| 源码范围、来源与整理状态 | [源码发布说明](docs/pixelos/source-publication.md) |
| 固定上游、输入准备与构建 | [源码准备](scripts/build-support/source-release.md) |
| 原厂固件与私有输入 | [输入清单](scripts/build-support/source-inputs.md) |
| 安装起点与分区契约 | [安装说明](docs/pixelos/fastboot-install.md) |
| 当前源码与既有成品 | [当前状态](docs/pixelos/progress.md) |
| 产品约束和维护规则 | [当前决策](docs/pixelos/current-decisions.md) |
| 设备和功能机制 | [文档索引](docs/pixelos/README.md) |
| 历史 ROM 修复载体 | [模块说明](modules/README.md) |
| 来源与许可 | [源码归属](docs/pixelos/source-ownership.md)、[LICENSE](LICENSE) |

维护仓库放在 Android 源码树之外。设备树通过 `POPSICLE_PROJECT_INPUTS`
引用本仓库 helper，正式装配入口为 `scripts/source-patches/prepare-pixelos-source.py`。
新树按固定序列准备，已有维护树按实际增量更新。

原厂固件、Google 交付包和签名私钥由使用者提供。开发测试、夹具、回放程序和
测试目标已从发布集合排除，生产构建校验保留。LOFIC 移植独立维护。

新机器从[源码准备](scripts/build-support/source-release.md)开始：配置 `.env.example`，
同步固定 Android 源码及 Git LFS，提供 `OS4.0.0.23.XPBCNXM` 完整官方 OTA
与完整 AICore 六分包，然后运行 `prepare-pixelos-inputs.py all`。
该入口提取固件、准备 OEM 组件，并从固定上游读取 TurboAdapter；R8 与 dex2jar
按固定摘要下载。构建、导出和三平台打包继续使用原有入口。

## 工作目录

本机与服务器均使用独立工作根，维护源码位于 `project/`。
`inputs/` 保存原始固件、外部 APK 和签名材料；`tools/`、`env/` 保存工具与配置。
`work/` 保存可重建的固件提取、准备结果和缓存；`releases/` 保存正式交付。
实机采集与人工研究归入 `evidence/`，原始 Git、独有源码和旧版本归入 `history/`。
仅清理已有明确生成步骤、且不再使用的具体构建输出或缓存。固件提取与准备目录须先确认
原件、工具和恢复步骤齐备；正式构建入口不会自动恢复整个 `work/`。
原件、签名、采集和历史不属于构建缓存。
ROM 活动源码位于 `android/`，树内 OUT 和私有准备目录沿用 Android 的布局。
