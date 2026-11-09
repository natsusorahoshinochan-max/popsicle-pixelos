# popsicle PixelOS 产品与维护规则

## 产品

产品为 PixelOS Android 17 `custom_popsicle-cp2a-user`，使用原始
OS4.0.0.23.XPBCNXM 硬件输入。保留正常未注入 init_boot、A/B、动态分区、
recovery、update_engine 和原厂 64 位、4 KiB ABI。

- CameraOpt 使用普通版及其原名单、运行时更新和权限检查。
- 背屏保留官方方向映射、独立电源与窗口生命周期。
- 导航隐藏同时处理横条显示和应用占位，手势输入、输入法辅助按钮及三键恢复继续使用。
- OEM Face、PixelOS WebView、Google 电话 UI 和 OEM IMS 按各自消费者装配。
- AppFunctions 保持原 schema、keep 和权限契约。
- 背屏配置页提供单图、单段视频、常亮和长按编辑控制。
- 当前产品沿用 HAL 局部音频适配。全局 `ro.vendor.qti.va_aosp.support=1` 方案处于撤回状态。

产品范围与限制见[后续备忘](pre-image-plan.md)。

## 原厂组件

相机和背屏保留原 APK 业务载荷，通过设备准备链生成适配输入，再由正常平台签名和
预优化链装配。CameraOpt、HAL、算法资源、图库入口、双屏生命周期和权限按真实消费者接入。

原厂文件以固件版本、分区和完整相对路径标识，保持只读。输入规范见
[输入清单](../../scripts/build-support/source-inputs.md)。

## 路径与执行

维护仓库放在 Android 树之外，设备 `source-config.mk` 中的 `POPSICLE_PROJECT_INPUTS`
指向当前维护副本。设备源码和 helper 对应同一发布提交。

本机 ROM 维护使用独立的 `popsicle-pixelos-rom` 工作区。服务器开发根为
`/root/autodl-tmp/pixelos-popsicle/`。

| 根目录下的路径 | 用途 |
|---|---|
| `project/` | ROM 维护仓库 |
| `android/` | 已装配的 Android 源码及树内私有 vendor |
| `inputs/`、`tools/` | ROM 专用原件及固定工具 |
| `env/` | 宿主环境和路径配置 |
| `cache/`、`tmp/` | 宿主缓存和临时文件 |
| `android/out-pixelos-user/` | 日常构建输出 |
| `releases/` | 按版本保存的成品与交付目录 |
| `archive/git-objects/` | 只读 Git 对象归档 |
| `archive/history/` | 原始 Git 历史与独有源码 |

原厂输入使用项目内的 `inputs/firmware/OS4.0.0.23.XPBCNXM/`，包含 payload、
分区镜像、内容解包目录及 A16 安装脚本。私有准备产物使用 Android 树内的真实 vendor 目录。

宿主使用 `env/build-support-venv/`，Python 为 3.12.3，protobuf 固定为 5.29.5。
通过 `source /root/autodl-tmp/pixelos-popsicle/env/build.env` 载入环境。
`POPSICLE_OUT` 保存输出绝对路径，`OUT_DIR` 为相对 Android 根的 `out-pixelos-user`。
构建中间文件与 Soong 临时文件放在同一文件系统。

当前宿主的原厂 `product/etc/build.prop` 保留 root 所有权及 `0600` 权限，输入准备和
校验、平台补丁装配和增量维护由 root 执行。装配器将 Git 信任范围限定为每条命令
实际使用的已核验工作树。编译与导出使用 UID 65534，通过 `env/run-as-builder.py` 执行
工作区内的任务脚本。运行器临时授予该 UID 对 `/root` 的穿越权限，任务退出后恢复 `0700`。

Git 对象归档对构建 UID 只读，新对象写入 Android 树内各对象库的可写目录。
对象维护沿用 repo 的共享规则，手工 repack 使用 `--local`，`repo.dissociate`
保持关闭。旧树保留历史引用与 reflog，冻结其 Git 维护。

ROM 构建使用 Linux 环境。工具链、输入、输出和发布目录由构建入口显式指定，命令见
[源码准备](../../scripts/build-support/source-release.md)。完整正式序列用于尚未装配的固定基线，
已装配树按实际增量维护。

保留 Android 正常依赖、ELF、ABI、VINTF、SELinux、NOTICE、签名和失败退出检查。
发布快照排除开发测试，生产构建校验保留。ProcessManager 的 fuzzer 登记范围见
[源码发布说明](source-publication.md)。

ROM 交付使用 `.tar.gz`、`pigz -p 16` 和 SHA256 伴随文件，Android target-files
继续使用原 ZIP 格式。

## 设备与历史模块

ADB 使用本机 USB，先取得设备列表并显式选择目标。刷机、安装和设备状态修改按具体任务授权执行。
Bootloader 保持解锁，安装起点、数据选择和分区行为见[安装契约](fastboot-install.md)。

历史模块保留其固定 ROM 基线、冲突与载荷检查。系统文件挂载由用户配置的实现负责，
当前正式 ROM 已由内置源码承接对应修复。

## 文档

当前机制、来源、状态和已知限制统一在 `docs/pixelos/` 维护。源码发布状态集中于
`source-publication.md`，进度页保持简短。已有成品反馈按对应版本和用户原话保存。
