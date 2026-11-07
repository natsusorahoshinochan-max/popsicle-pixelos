# Android 17 TurboAdapter / R8

固定工具和输入身份保存在 `dependencies.json`。原始 APK 和 converter 输入准备到
当前 Android 树的 `vendor/xiaomi/popsicle-private/prebuilt/turbo-r8/inputs/`。
生成 JAR 由 Soong 管理，产物位于所选 `OUT_DIR`。

## 准备输入

R8 使用 `https://storage.googleapis.com/r8-releases/raw/9.3.19/` 的固定文件，
dex2jar 使用 `https://github.com/pxb1988/dex2jar/releases/download/v2.4/dex-tools-v2.4.zip`。
下载目录中的身份由现有锁文件核对。

```sh
python3 install-r8.py --apply ANDROID_TREE DOWNLOAD_DIRECTORY
python3 prepare-inputs.py ANDROID_TREE \
  --apk /path/to/original/TurboAdapter.apk \
  --dex-tools DOWNLOAD_DIRECTORY/dex-tools-v2.4.zip
```

输入准备读取原始归档并暂存完整 converter JAR。已有相同输入可复用，冲突会失败。
正式源码装配入口检查原始输入和六份 R8 文件，复制当前工具源码与 Blueprint。
完整命令见[源码准备](../../build-support/source-release.md)。

## 构建依赖

当前生成规则位于 Android 树的 `frameworks/base/tools/popsicle-turbo/`。
它声明原始 APK、修复后的 dex2jar host tool、normalizer，以及真实 Android 类头的依赖。
Framework 和 ConfigInfrastructure 使用显式导出的 pre-jarjar 输出标签，core-all
使用其 Java JAR 输出。三个平台模块新增的可见性条目均指向该工具目录。

```sh
export OUT_DIR=out-pixelos-user
source build/envsetup.sh
lunch custom_popsicle-cp2a-user
m -j16 TurboAdapter_NoBatt
```

converter 在其原始库之前使用维护的寄存器分配修复。normalizer 从真实 Android
类层级恢复 DEX 类型名并重算、验证 frames。原始 200 个定义完整验证后，过滤五个由
维护源替换的 GoogleBatteryService 实现类。其余 195 类的生成 JAR 必须匹配现有固定摘要。
生成失败正常终止规则，重试使用新的临时目录。

`Ir2JRegAssignTransformer.java` 来自 dex2jar 提交
`b5bda4fb4935ae8b3869b422454ae3b3896c7bc1`，应用了本目录的确定性寄存器分配补丁。
`NormalizeTurbo.java` 通过 class headers 解析层级。独立使用 `normalize.sh` 时显式传入
JDK、ASM classpath、工作目录及三份真实 Android JAR。

正式顺序为 `pixelos-public-user.series`，活动树按实际增量维护。
API 37、NoBatt Binder version 7、原有权限检查和 R8 检查由当前构建链执行。
当前构建范围见[源码发布说明](../../../docs/pixelos/source-publication.md)。
