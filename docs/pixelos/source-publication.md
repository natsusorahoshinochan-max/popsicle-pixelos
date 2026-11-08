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

原始 A17 payload 的全部分区提取、六个所需 EROFS 文件系统内容解包和版本检查
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

本次验证目录为 `/root/autodl-tmp/pixelos-publication-build-20261108/`，
产物保存于 `artifacts/`。构建、交付日志与静态内容审查结果分别保存于
`logs/build-success.log`、`logs/finish.log` 和 `logs/central-directory-content-audit.json`。

- `release/target_files.zip` 为 13,276,126,295 字节，SHA256 为
  `912dcef97e37c96f263d8db28f88362cc601569f7398f5ecba775c8a83586b9b`。
- `delivery/PixelOS-popsicle-20261108-source-validation_by_Kanoe.tar.gz` 为
  6,896,506,929 字节，SHA256 为
  `ca50dab07f68aab50ea54366f615887f0a5866938a2ca26f47ac74c44d5cbd2b`。

本次成品的设备验收状态为 `pending-user-test-from-A16`，真机运行验收待完成。

### 2026-11-08 工作区迁移

服务器开发根已切换为 `/root/autodl-tmp/popsicle-rom-dev/`。原计划路径
`/root/autodl-tmp/popsicle-rom/` 保存着 9 月旧仓库，继续保留其源码与历史。
本机日常维护使用独立的 `popsicle-pixelos-rom` 工作区，原混合工作区保留
LOFIC、原始采集、逆向资料和 Git 历史。

迁移验收使用维护提交 `11c6b9c54b9be8b9ebeaa02a6b68d44c1fd19277`。
该提交与完整构建使用的 `be5dfef` 之间均为 Markdown 修改，生产源码、补丁和
helper 内容一致。139 个设备树文件与 32 份安装 helper 核对通过，设备副本仅刷新
三份 README。

目录通过同卷移动完成切换，原路径保留相对兼容链接。

| 原位置 | 新开发根下的位置 |
|---|---|
| `pixelos-publication-build-20261108/` 任务根 | `archive/validation-20261108/` |
| 原任务的 `project/`、`android/`、`cache/`、`tmp/` | 根下同名目录 |
| 原任务的 `artifacts/` | `releases/20261108/` |
| 原 Android 树的 `out-pixelos-user/` | `archive/validation-20261108/out-pixelos-user/` |
| `pixelos-bringup/implementation/storage-rom-20261106/` | `releases/20261106/` |

完整构建任务的脚本、失败与成功日志、状态记录均随目录保存。11 月 6 日与
11 月 8 日成品继续按各自版本归档，来源 JSON 保留生成时的绝对路径。
历史 OUT 的 host 仍指向 `/tmp/pixelos-build-output-20261108/host`，旧 assembly
仍使用 `/tmp/pixelos-publication-assembly-20261108`。
历史 OUT 中的失效缓存链接随原目录保存，target-files 与 release 中的 ZIP 保持
同一 inode，硬链接数为 `2`。

R8 下载、AICore 六份原件和三平台工具已迁入新根的 `inputs/` 与 `tools/`。
33 个输入与工具文件的 inode、属性与内容核对通过。
AICore 原件与已准备 APK-set 内载荷一致，独立 Turbo 原件通过锁定摘要检查。
官方固件库继续使用 `/root/autodl-tmp/popsicle-firmware/`。

宿主环境已在最终路径重建，Python 3.12.3、protobuf 5.29.5 和 `pip check` 通过。
12 份私有来源记录的 SHA256 保持。UID 65534 下的缓存、临时目录和 OUT 可写，
payload、原始镜像目录、A16 脚本及已准备私有输入可读，R8 与 Turbo 检查通过。
独立 UID 运行器的失败退出检查通过，任务结束后 `/root` 恢复 `0700`。

1,172 个 Git 对象库已同卷迁入 `archive/git-objects/.repo/project-objects/`。
归档保存旧对象集合，新树保留可写对象目录并直接引用归档，旧树对象路径通过
兼容链接读取归档。
新旧项目各自保留 refs、reflog、shallow 和配置。两树各 1,222 个 checkout 的引用、
reflog 读取及 `git fsck --connectivity-only` 全部通过，共 2,444 次，退出码为 `0`。
归档内 18,141 个文件与 18,293 个目录的 inode、mtime、UID/GID、mode、xattr 和
链接数核对通过，文件大小一致。XFS 目录的 `st_size` 差异归一化比较，原始清单保留。

16 个共享对象组覆盖的 66 个 checkout 保留原配置，实际访问检查确认构建 UID
对全部 1,172 个归档对象库拥有只读权限。`repo.reference` 指向新归档，
`repo.dissociate` 为 false。repo 工具的 origin 已改为官方来源，提交保持
`b85886fa9f5b4e2189cc5b2f40bd0a80459d4c77`。

后续复核补正了两条 manifest Git hook 的旧相对路径，链接指向新树自带的 repo hook。
修复前的链接与属性已归档，重复执行通过，`.repo` 的 6,006 条符号链接均有效。

原厂输入的正式 `prepare-source-inputs.py --check` 由 root 执行并通过，覆盖
固件与 provider 字节、121 份背屏资源、原 APK 与 PAG 库及相机输入。
UID 65534 已在新 OUT 执行 envsetup 与 `lunch custom_popsicle-cp2a-user`，解析结果为
`TARGET_PRODUCT=custom_popsicle`、`user`、SDK 37，输出路径与 `TMPDIR` 同卷检查通过。
输入检查与 lunch 退出码均为 `0`，运行器退出后 `/root` 恢复 `0700`。
lunch 日志记录宿主 nsjail 不可用及屏幕宽度采用默认值的提示。

迁移清单、对象库日志和验收结果保存在 `archive/validation-20261108/migration/`，
目录移动总账位于 `archive/directory-migration.json`。

本次复核时数据卷可用约 24.1 GiB。三个旧 OUT 的可回收空间约 235.3 GiB，
清理后预计可用约 259.4 GiB。新 OUT 的完整重建、导出与打包复验在满足
250 GiB 可用空间预算后执行。

## 维护入口

准备命令见[源码准备](../../scripts/build-support/source-release.md)，安装起点与分区行为见
[安装契约](fastboot-install.md)。来源和许可归属见[源码归属](source-ownership.md)。
