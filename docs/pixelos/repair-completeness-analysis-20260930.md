# 音频与运行恢复契约

## 音频与 IMS

音频转换删除误选 FM 输入路由，并对匹配原厂 HAL 的局部 GSI 初始化指令进行精确适配，
保留输入身份和指令检查。转换源为[音频 helper](../../scripts/source-patches/firmware-filesystems/audio_repair.py)。

IMS 音频桥监听 locked boot 与完整 boot，初始化按系统用户和幂等条件排入唯一工作线程。
原厂 AudioControllerAgent 的等待与回调使用该线程，HAL 迟到、Binder 死亡和 audioserver
变化由原组件契约承接。实现见[IMS](../../device/xiaomi/popsicle/ims/)和
[native 音频 adapter](../../device/xiaomi/popsicle/ims-audio-adapter/)。

## 网络所有权

VPN 入口过滤按网络实例维护来源和完整过滤快照，保留 BPF tuple、dirty UID 和重试机制。
新连接先取得来源所有权，退出时由中央销毁撤销相应来源，见[入口所有权](../../scripts/source-patches/vpn-owner/)。

UID 路由增删是 delta 接口，部分失败后的完整恢复仍属未决范围。
Bluetooth 编码器偏好和会话生命周期同样分别维护，provider 首次启动失败和会话恢复范围保留。

## 显示与客户端生命周期

启动自动亮度校正和临时亮度撤销沿原始事件顺序执行。
背屏通知资格、颜色恢复和相机跨屏清理按实际对象和显示归属处理。
条件性风险与既有反馈见[后续备忘](pre-image-plan.md)及[验收摘要](validation.md)。
