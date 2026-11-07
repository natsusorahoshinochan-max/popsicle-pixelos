# 原厂相机平台接口

提供算法 GraphicBuffer 锁定 ABI、CameraOpt cpuset 与线程亲和性、真实前台事件和进程策略、拍照命名键及 HEVC 封装兼容。原厂 APK、JNI、权限和 RAW/DNG 保存适配由设备树的 oem-camera 准备链维护。

完整装配使用[正式序列](../pixelos-public-user.series)，步骤见[源码准备](../../build-support/source-release.md)。各文件的固定上游 revision 由正式序列声明，已装配的活动树按具体增量维护。
