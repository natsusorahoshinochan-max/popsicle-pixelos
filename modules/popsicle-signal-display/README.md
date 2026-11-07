# Popsicle 官方蜂窝信号格 v0.1

同源第117条修复由正式ROM承接，集成记录见[七项修复专题](../../docs/pixelos/validation.md)，当前交付见[进度](../../docs/pixelos/progress.md)。当前ROM无需本模块，升级前应停用或卸载旧覆盖模块。

以下为历史模块说明，仅适用于已验收的 PixelOS 20260930 全球运营商版，Android 17，
`ro.build.date.utc=1790747209`。通过 KernelSU 安装，系统文件覆盖由用户配置的挂载实现负责。

使用匹配官方 OS4.0.0.23.XPBCNXM 的 GSM、WCDMA、TD-SCDMA、CDMA/EVDO、
LTE、NR 显示分级，并包含 LTE RSSI 兜底。WCDMA 使用 RSCP；CDMA/EVDO
使用各自 dBm 并保留分量合并。只在 popsicle 地面蜂窝路径启用，保留原始测量、
基带上报配置、主信号选择和 Android 校验。不会强制显示 5G 字样。

模块覆盖 framework.jar、同次构建的 system boot image 集合和 boot profiles、对应 fs-verity
伴随文件及从已验收 ROM 清单合入本载荷后正常签署的 BuildManifest。
未替换 services.jar、SystemUI、CarrierConfig 或任何 APEX。
未包含其他挂起修复；这是当时完整 ROM 同源修改的可停用测试载体。

## 旧基线安装与撤销

仅在上述固定旧基线上，KernelSU管理器安装ZIP后重启。首次启动可能因 ART 重新编译变慢。
与其他替换 framework、boot image 或系统 BuildManifest 的模块冲突；包括此前
启动亮度和 VPN 入口过滤模块。先停用冲突模块并重启，再安装本模块。
安装器会拒绝检测到的相同载荷路径冲突；以后也不要同时重新启用这些模块。

停用本模块并重启即可恢复原 ROM。若无法进入系统，可使用 KernelSU 安全模式
禁用模块，或在具备 /data 访问能力的恢复环境中创建
`/data/adb/modules/popsicle_signal_display/disable` 后重启。
模块不写分区、不刷机，也不清除用户数据。

原模块的观察范围为不同位置的格数变化及 LTE/NR 切换。格数变多不代表接收功率或网速提高。实现覆盖未实测制式不等于
它们已经通过本机验收。构建结果和用户反馈统一记录在
[信号专题](../../docs/pixelos/validation.md)。

## 历史载体维护入口

先执行 `bash modules/popsicle-signal-display/build.sh ANDROID_TREE NEW_LOG_DIRECTORY`，
再使用 `python3 modules/popsicle-signal-display/package.py package ANDROID_TREE
--baseline-manifest BASELINE --output NEW_DIRECTORY` 装配历史载体。
使用本项目现有 `popsicle-repair-parts/manifest_support.py` 生成正常伴随产物。
ZIP 使用 32 worker，旁附 SHA256。无晚启动热替换脚本。
