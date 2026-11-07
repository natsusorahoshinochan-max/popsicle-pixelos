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

本发布快照的整理、装配与构建结果集中记录于本节。已有成品和反馈见
[历史验收摘要](validation.md)，其范围对应原成品版本。

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
完整新树 ROM 构建、镜像导出和三平台打包仍待验证。验证开始时构建宿主的可用存储
约 115 GiB，既有 ROM 输出约 161 GiB，本次独立目录验证覆盖源码装配与输入
准备。已有成品验收仅对应原成品版本。

## 维护入口

准备命令见[源码准备](../../scripts/build-support/source-release.md)，安装起点与分区行为见
[安装契约](fastboot-install.md)。来源和许可归属见[源码归属](source-ownership.md)。
