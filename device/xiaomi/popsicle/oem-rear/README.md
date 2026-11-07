# 官方背屏 App 与 PAG 私有输入准备

本目录只有声明和准备工具，不含专有输入。`prepare.py ANDROID_TREE OFFICIAL_FILESYSTEMS --dex-tools DEX2JAR_DIRECTORY`（只读检查使用 `--check`） 使用匹配 OS4.0.0.23.XPBCNXM 的只读输入，在 `vendor/xiaomi/popsicle-private/prebuilt/oem-rear` 准备原版背屏输入、适配后的 APK、PAG DEX JAR、两项 native 库、library XML、最小公开声明及实际 NOTICE。总入口 `scripts/build-support/prepare-source-inputs.py` 已调用此步骤。

`Android.bp.in` 仅在私有目标目录成为 Android.bp，避免设备树与私有树重复定义模块。保留真实 ELF/NOTICE 校验；不替换平台基础库。不覆盖不同的已有输入，`--check` 保持已准备输入不变。

`prepare.py` 同时调用 `resources.py`：准备原 rear media 和 JSON 明确引用的预置主题文件，在私有 `resources/` 下生成带 proprietary 许可声明的资源模块及 `resource-files.txt`。产品选择 `popsicle-rear-resources`，模块打包器使用同一清单；不复制整个预置主题库，也不改写原 JSON/认证文件。已有私有资源内容不同即失败，生成的装配元数据可按维护源更新；`--check` 检查而不更新。

ROM 准备与构建使用 Linux 宿主。产品包列表与设备 overlay 由本项目设备树管理。正式集成和用户验收范围见[当前进度](../../../../docs/pixelos/progress.md)及其发布记录。

背屏模块 `PopsicleSubscreenCenter` 使用平台签名，位于 system_ext/app，不增加 sharedUserId 或 privileged 标记。设备准备链以原 APK 为输入，依次装配原 MiSight SDK、几何与手势修复及结构化运行时，最终选择 `subscreencenter-personalization.apk`。官方界面与业务逻辑保留，适配源码由本目录 `adaptation/` 维护。系统签名权限按 PackageManager 原规则授予；运行时权限和跨 OEM 包授权继续遵循各自消费者的检查。保留原五项可选 Java 库声明，真实 PAG JAR 与两项 native 库均为 required 模块，不关闭 uses-library/ELF 校验。

## 派生产物的复用与更新

背屏 APK 在本 Android 树的私有临时目录中完成全部五个适配步骤，再发布到正式输入路径。生成记录使用原件、转换源码、SDK 与 dex2jar 的内容摘要，并检查已发布 APK 的摘要。移动源码树或原件目录后，内容相同的输入仍可复用。

源码或原件变化后，准备器重新生成适配链，仅更新有匹配输出摘要的既有派生 APK。已有 APK 被其他工具改动时明确失败。旧格式记录首次使用时与当前生成 APK 比较，DEX 的数据项排序差异通过反汇编比较处理；无法确认同源的输入需要在新的私有目录准备。

发布记录在 APK 替换前保存新旧两个摘要，完成替换后收敛到当前摘要。中断后重跑同一准备命令可以继续完成。首次准备、旧记录迁移和源码更新都需要 `--dex-tools`；当前内容匹配的复用及检查可省略该参数。
