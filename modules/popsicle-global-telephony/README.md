# 全球运营商配置修复 v0.1（历史验证模块）

适用于 PixelOS popsicle Android 17 的 2026-09-29 相机跨屏修复完整 ROM。
以下安装及撤销说明只适用于该固定旧基线，通过 KernelSU 及用户配置的系统文件挂载实现生效。在 KernelSU 安装 ZIP 后重启。

模块以同源 ROM 构建产物替换 CarrierConfig 服务、全球运营商资源和 APN，
完全替换旧 46001 单条覆盖。保留现有 OEM IMS provider、基带与正常开通检查。
安装前先停用旧 IMS／运营商强开模块并重启。

已在官方配置中明确开启的网络沿用对应策略。仅由全球兜底提供能力的网络
默认保持关闭，可在 SIM 设置中开启 VoLTE／4G 通话。IMS 注册由现有 OEM
provider、基带及正常开通检查决定。全球 VoWiFi／视频通话仍待专项验收。

正式 ROM 已内置同源修复，独立于 KernelSU 运行。升级前应停用或卸载本模块，避免覆盖新系统文件。
实现与用户反馈见[运营商专题](../../docs/pixelos/validation.md)，
当前交付见[进度](../../docs/pixelos/progress.md)。
若有问题，停用本模块并重启，系统将恢复原 ROM 文件并正常重新加载配置。
安装与停用过程保留用户数据、用户 APN、基带 NV 和 init_boot。

设备侧维护入口为 [carrier-config](../../device/xiaomi/popsicle/carrier-config/)
与 [carrier-apns](../../device/xiaomi/popsicle/carrier-apns/)，平台实现见
[运营商补丁](../../scripts/source-patches/carrier-config/README.md)。
