# Popsicle NR_CA 注册修复 v0.1

正式 ROM 已集成 [NR_CA 注册补丁](../../scripts/source-patches/nr-registration/0001-popsicle-nr-ca-registration.patch)，发布与验收范围见[交付记录](../../docs/pixelos/validation.md)。安装当前 ROM 前停用或卸载旧覆盖模块。

以下为历史模块说明，仅适用于 PixelOS 七项修复完整 ROM
`PixelOS-popsicle-20261002-seven-fixes_by_Kanoe.tar.gz`，Android 17，
`ro.build.date.utc=1790954511`。通过 KernelSU 安装，系统文件覆盖由用户配置的挂载实现负责。

仅当本设备的 AIDL 注册响应上报私有 RAT=30 时，规范为标准 NR，并保留
载波聚合属性。用于修复“蜂窝数据仍连接，但 5G 字样空白”的已定位原因。
CS/PS 共用转换均覆盖，其他制式、未知值和原检查保持。
vendor PCC 私有 RAF、真实聚合频段/带宽仍待独立适配，5G+ 字样沿用系统现有判定。

完整 ROM 与模块使用同一正式源码补丁。模块包含 telephony-common.jar、
匹配的完整 system boot image 集合及 boot profiles、正常 fs-verity 元数据
和合入本模块条目的签署 BuildManifest。保留该旧基线 ROM 已集成的信号格等修改。
模块文件通过系统启动时的挂载加载。

## 旧基线安装与撤销

仅在上述固定旧基线上，KernelSU管理器安装ZIP后重启生效。首次启动可能因 ART 重新编译变慢。
先停用覆盖 system boot image、telephony-common 或系统 BuildManifest 的旧模块
并重启。使用本模块期间，旧信号格、启动亮度和 VPN 框架模块应保持停用。
安装器会拒绝检测到的载荷路径冲突。其他模块是否可并用以实际覆盖路径为准。

停用本模块并重启恢复原 ROM。若无法进入系统，使用 KernelSU 安全模式，
或在具备 /data 访问能力的恢复环境创建
`/data/adb/modules/popsicle_nr_registration/disable` 后重启。

原模块的观察范围为原先空白场景、自然 NR/NR_CA 切换及普通 NR/LTE 显示和数据连接。
用户反馈按模块或整包记录，实现与既有测试见
[信号专题](../../docs/pixelos/validation.md)。

## 历史载体维护入口

先执行 `bash modules/popsicle-nr-registration/build.sh ANDROID_TREE NEW_LOG_DIRECTORY`，
再使用 `python3 modules/popsicle-nr-registration/package.py package ANDROID_TREE
--baseline-manifest ACCEPTED_ROM_MANIFEST --output NEW_DIRECTORY` 装配历史载体。
复用本项目 manifest_support.py，ZIP 使用16个压缩worker，旁附SHA256。
