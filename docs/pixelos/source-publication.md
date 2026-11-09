# ROM 源码发布范围

本仓库维护 popsicle 的 PixelOS Android 17 设备适配、平台补丁、helper、
原厂组件准备和交付工具。产品为 `custom_popsicle-cp2a-user`。

## 固定来源

整理来源提交为 `a8813e5f9b7de4bb44e5aac4cfe9015cea65a61b`。
发布快照保留文件原有版权与来源说明，原维护工作区及完整 Git 历史单独保存。
本仓库从 ROM 源码集合建立独立历史。

固定 PixelOS manifest 提交为 `ec8aaaec7855bcfd57db140398f54f11c0d3d2c6`，
AOSP 基线为 `android-17.0.0_r1`。[解析清单](../../scripts/build-support/pixelos-manifest.xml)
保存 1,222 个项目 revision，SHA256 为
`7eb71e373e50eac61e2ac3380fbcdc47e9ed51f4f5f599d666bc71a4ab10ad74`。

生产修改按[正式序列](../../scripts/source-patches/pixelos-public-user.series)应用，
共 116 条补丁、27 个仓库路径和 32 份安装维护源。背屏美化的 Settings
页面及注册由正式补丁统一装配。来源提交中的 128 条序列包含开发测试，
当前发布序列已按生产用途裁剪。
设备树、补丁、安装 helper 和实时读取的转换源应来自同一发布提交。

## 发布集合

| 集合 | 内容 |
|---|---|
| `device/xiaomi/popsicle/` | 产品、分区、VINTF、策略、资源覆盖、原厂 App 和服务适配 |
| `scripts/source-patches/` | 正式平台补丁、生产 helper、模板和必要声明 |
| `scripts/build-support/` | 输入准备、构建、导出、打包和三平台安装器 |
| 原厂输入工具 | 正式准备调用的 QCC 工具及保留的固件处理步骤 |
| ROM 历史模块与诊断 | 原基线修复载体和有实际维护用途的工具 |
| `docs/pixelos/` | 当前接口、输入、机制、安装、状态与验收摘要 |

开发测试源码、夹具、回放程序、测试目标、测试运行器及补丁内开发测试代码已从
发布集合排除。原厂相机的 `PixelosRawSave` 和 `DngTiles` 是生产实现，继续纳入。
LOFIC 移植独立维护。

生产输入、ABI、VINTF、SELinux、NOTICE、签名和分区校验保留。
`sepolicy_tests.py` 中约束实际 DSP 权限的生产校验适配继续使用。
`ProcessManager` 使用上游 `EXCEPTION_NO_FUZZER` 登记，当前发布集合未提供该服务的
fuzzer 覆盖，服务权限和正常策略校验保持。

## 外部输入

原厂固件、APK、ELF、资源、Google 完整交付包和签名私钥由使用者自备。
原厂输入保持只读，准备产物写入选定 Android 树的私有 vendor 目录。
版本、路径结构、NOTICE 与转换步骤见[输入清单](../../scripts/build-support/source-inputs.md)。
三平台宿主工具从对应 SDK ZIP 准备，并携带其 NOTICE 和版本属性。

## 当前验证范围

已有成品和反馈见[历史验收摘要](validation.md)，其范围对应原成品版本。

固定 Git 基线的受影响文件已在独立目录完成 116 条补丁的预检与应用，
27 个仓库和 32 份维护源安装通过。该目录使用原始固件镜像和固定 Turbo
输入，Git objects 只读复用，源码和私有输出分别独立保存。

真实原厂输入的固件与 provider 准备已通过，覆盖 QCC、IMS、运营商配置、APN、
121 份背屏资源、完整背屏适配链及官方相机适配。背屏内容复用检查与 Android
目录迁移后的复用检查通过。

AICore 使用固定树自带 SDK 工具、JDK 和宿主 `protoc` 完成准备，六份原始 APK
的 Google 签名、包名、split 身份及统一版本已检查，原 APK 字节保持。准备产物
先在私有临时目录生成，再原子发布。

原始 A17 payload 的全部分区提取、所需 EROFS 文件系统内容解包和版本检查
已由本仓库提取入口完成。原始镜像保留 Android 元数据，解包目录用于读取原件内容。

Python、Shell 和补丁语法检查、本地文档链接检查及迁移差异审查已完成。

### 2026-11-08 完整构建与交付验证

本次验证使用发布提交 `be5dfefbae692f635c31b3c8773797db0799a6ec` 与固定清单的
1,222 个项目。139 个设备树文件及 32 份安装 helper 均与该发布副本逐字节一致。
源码树及输出目录独立保存，编译进程使用独立 UID 65534。

首轮产物的静态内容审查发现 60 个 APK/APEX 携带宿主路径符号链接，该轮产物已废弃。
复用输入调整为 4,706 份只读硬链接和 144 份独立普通文件，共 4,850 份文件逐一核对
SHA256，原件内容、权限、UID/GID 和修改时间核对通过。

清空 `OUT_DIR` 后，于 2026-11-08 12:49:58 开始全新完整构建，
`m -j16 -k20 target-files-package lpmake simg2img img2simg` 一次完整执行通过，
退出码为 `0`。构建于 19:15:20 完成，耗时 6 小时 25 分 22 秒，时间均为 Asia/Taipei。
生产构建的 ABI、VINTF、SELinux、NOTICE 和签名检查通过。vendor / ODM 校验覆盖
派生文件系统元数据、硬链接组、完整文件字节及 FEC 独立重编码比较。

target-files 全成员 CRC 和内容审查通过。生产安装包共 286 份普通文件，包括
242 个 APK、17 个 APEX 和 27 个 CAPEX，载荷合计 3,616,211,337 字节。
867 条设备内有效符号链接通过检查，宿主路径链接数为 `0`。
此前受影响的 60 个包均为普通文件，大小及 CRC 与历史成品对应项一致。
全部 286 个共同安装包的大小核对一致，其中 281 个 CRC 相同，5 个 CRC 随本次构建变化。
生产模块清单与原维护树的构建输出核对一致，SHA256 为
`1ecc21e7f0cdc812d5a91736fbbc2d000c5aeef1993f7b7e96e9ad9fa435b8e4`。

保存 target-files 和本次宿主工具的独立动态库闭包并完成校验后，清理本次构建的
Soong 中间产物以供导出使用。导出结果为 `complete=true`、`image_count=50`，
安装 super 的 `full_device_write_bytes` 为 `13421772800`。
交付包包含 Windows、macOS、Linux 安装入口，包内 SHA256、归档摘要和完整归档
读取检查通过，于 2026-11-08 19:27:21 完成（Asia/Taipei）。

该旧版成品和临时验证目录已清理，服务器只保留下文的 20261109 成品。
以下摘要用于标识这次历史验证：

- `target_files.zip` 为 13,276,126,295 字节，SHA256 为
  `912dcef97e37c96f263d8db28f88362cc601569f7398f5ecba775c8a83586b9b`。
- `PixelOS-popsicle-20261108-source-validation_by_Kanoe.tar.gz` 为
  6,896,506,929 字节，SHA256 为
  `ca50dab07f68aab50ea54366f615887f0a5866938a2ca26f47ac74c44d5cbd2b`。

本次成品的设备验收状态为 `pending-user-test-from-A16`，真机运行验收待完成。

### 2026-11-09 三项目迁移完成

PixelOS 的维护入口为本机 `popsicle-pixelos-rom/` 和服务器
`/root/autodl-tmp/pixelos-popsicle/`。服务器内 `project/` 保存维护源码，
`android/` 保存活动 Android 树，`inputs/`、`tools/`、`env/` 分别保存本项目输入、
工具与环境。日常输出为 `android/out-pixelos-user/`。

迁移时 LineageOS 和 LOFIC 分别使用 `/root/autodl-tmp/lineageos-popsicle/` 与
`/root/autodl-tmp/17ultra-lofic/`。随后按用户要求删除了远端 LineageOS 工作区；
当前 PixelOS 工作不再准备或验证 LineageOS。
LOFIC 原厂固件归入 `inputs/firmware/`，提取资料归入 `work/firmware/`，拥有独立 A17 payload 与镜像副本。

旧 `pixelos-17/`、`pixelos-bringup/`、`popsicle-source/` 与公共
`popsicle-firmware/` 入口已退出。原始 Git 历史、独有源码、签名和研究资料保留在
各自项目中。PixelOS 的 `android/.repo/reference/` 仍是活动树使用的只读对象库。

一次性迁移、清退、恢复测试及隔离验收工具，连同其脚本副本、临时目录、重复验证
材料和运行状态文件已删除。正常源码准备、构建和交付使用本仓库的正式入口。

迁移期间的 Git 查询刷新了 1,409 份远端索引及 1 份本机索引的原缓存字节。
原任务已核对提交、引用、暂存条目和未提交文件；原缓存字节缺口保留此记录。

### 最终路径构建结果

维护源码以 `f10bed34c0c79d52d8915893def28d6d0442b317` 为基线，使用项目内输入，
在其他项目和旧公共路径不可访问时完成全新构建。构建耗时 6 小时 17 分 38 秒，
退出码为 `0`，50 镜像导出和三平台打包通过。构建与交付于
2026-11-09 06:49:22（Asia/Taipei）完成。

成品位于 `/root/autodl-tmp/pixelos-popsicle/releases/20261109/`，
其中 `target_files.zip`、交付包、`export-host/` 和 `logs/` 直接位于版本目录。
交付包为 `PixelOS-popsicle-20261109-isolated_by_Kanoe.tar.gz`，
大小 6,896,506,642 字节，摘要见同目录 `.sha256`。
目录迁移收尾沿用这次成功结果，没有重新启动完整构建。真机验收待完成。

### 2026-11-09 新机输入准备

新机入口接受固定官方 OTA ZIP 或其原始 payload，加完整 AICore 六分包。
固定 R8/dex2jar 下载、上游 TurboAdapter 读取、固件提取和现有私有输入准备已串联；
工具源码版本、安装步骤和 `.env.example` 见[新机准备](../../scripts/build-support/source-release.md)。
构建和导出使用仓库内 42 项安装契约，无需另备 A16 脚本。

本轮使用真实原始 payload，从空私有目录重新生成输入并完成重复执行。
已核对全部 58 个分区及七个所需文件系统，补齐 `mi_ext` 后运营商配置与原完整结果
逐字节相同。243 个准备文件的对比中，原厂副本保持一致；AICore 归档成员字节一致；
相机 9,288 个类和背屏 5,347 个类的反汇编内容分别完全一致，DEX 字节排列可随组装变化。
背屏 Apktool 框架缓存已限定在现有临时目录，不依赖宿主账户缓存。

payload-dumper-go 与 EROFS 已按固定上游源码编译；六份 R8 和 dex2jar 已重新从官方
地址下载并通过固定摘要校验。新安装契约与原 A16 脚本在真实 payload 上得到相同的
42 个固件顺序、长度、内容摘要和目标槽位。Python/Shell、异常输入和文档链接检查通过。
从上游全新同步的 1,222 个仓库 HEAD 全部匹配固定清单，8 个 LFS 文件的长度和
SHA256 全部匹配指针；没有引用旧对象库。维护源码从 GitHub 新克隆的
`e7da7992865de62b945db1f3daf804d154ef0cb5` 取得，在新树和 Python 3.10 下完成
输入准备、116 条补丁应用及 32 份维护源安装。
该新树的完整构建、导出与打包正在验收，尚不能以此前成品代替这项结果。

## 维护入口

准备命令见[源码准备](../../scripts/build-support/source-release.md)，安装起点与分区行为见
[安装契约](fastboot-install.md)。来源和许可归属见[源码归属](source-ownership.md)。
