# 蜂窝信号显示与 NR 注册

## 信号显示

设备限定的 Framework 显示分级采用匹配官方门槛，覆盖 GSM、WCDMA、TD-SCDMA、
CDMA、EVDO、LTE 和 NR。保持实际测量值、有效性校验、主信号选择和 NTN 原路径。
WCDMA 使用 RSCP，LTE 保留有效 RSRP boost 与 RSSI 回退，NR 使用直接 SS-RSRP。

显示分级与基带上报条件分别维护。正式实现见[信号补丁](../../scripts/source-patches/signal-display/)。

## NR 注册

在 `CellularNetworkService.getNetworkRegistrationInfoAidl()` 中，设备为 popsicle
且原始 RAT 为 30 时生成标准 NR 注册对象，并在最终 CS/PS 对象上保留 CA。
其他 RAT、HIDL 和 PCC 消费路径保留各自协议。

实现见[注册补丁](../../scripts/source-patches/nr-registration/)。
PCC 的原始零 RAT、带宽、频段、信道和 5G+ 仍属于独立未决范围。

## 运营商输入

CarrierConfig 从官方资源按当前 Framework 键转换，APN 按受支持条件和 schema 合并。
正式准备源码分别位于[CarrierConfig](../../device/xiaomi/popsicle/carrier-config/)和
[APN](../../device/xiaomi/popsicle/carrier-apns/)。

信号显示和注册修复均已随既有 ROM 交付，反馈范围见[历史摘要](validation.md)。
