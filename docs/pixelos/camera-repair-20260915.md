# 原厂相机生命周期适配

当前生产实现位于[相机准备目录](../../device/xiaomi/popsicle/oem-camera/)。

能力发现适配选择原 APK 实际存在的分支。默认图库入口沿平台正常 Intent 和 URI 权限
处理，退出临时亮度使用 NaN 撤销语义。

双屏生命周期适配在原有弱引用 Activity 集合的消费者中排除已销毁或结束的旧对象，
避免跨屏重建实例共用 token 时受到旧 Activity 清理影响。相机返回、停止、图库和背屏
事件保留原有调用顺序与异常退出责任。

50M RAW 与 UltraRAW 的保存、入库和白平衡机制见[DNG 保存](camera-algorithm-port-20261006.md)。
CameraOpt 与平台接口见[原厂组件接入](rear-camera-porting-technical-guide.md)。

既有完整 ROM 反馈按[版本摘要](validation.md)记录，全部镜头和生命周期组合的边界见
[后续备忘](pre-image-plan.md)。
