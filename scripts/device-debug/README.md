# ROM 诊断工具

本目录保存显示、原厂相机和分区读回诊断源码。工具通过调用者提供的目标、持续时间与输出目录采集实际设备状态。设备身份以本机 USB `adb devices -l` 为准，调用 ADB 的宿主工具需要显式 `--adb` 和 `--serial`。

| 工具 | 用途 |
|---|---|
| `arr/ArrInfo.java` | 按物理显示 ID 读取 SurfaceControl 的当前模式和 ARR 能力 |
| `capture-brightness-ramp.sh` | 有界采集 DisplayPowerController 的亮度、环境光及渐变状态 |
| `capture-camera-passive-device.sh` | 采集原厂相机 CameraService metadata 与日志，结束后释放本次 observer |
| `capture-camera-contract.py` | 按显式 metadata 名称采集 CameraService/provider 调用数据 |
| `capture-algorithm-raw.sh` | 采集原厂算法节点缓冲区，并恢复本次修改的相机属性 |
| `observe-frida.py`、`trace-camera-*.js` | 有界观察原厂相机客户端、服务和逻辑到物理映射 |
| `verify-partition-readback.py` | 从显式设备分区读回全部字节，与调用者提供的镜像比较 |

宿主 Python 相机观察工具使用 Frida，需由调用者在单独宿主环境安装。Java 显示工具使用匹配 Android 平台类编译后由 `app_process` 执行。宿主 Python 工具的 `--help` 和设备脚本开头描述实际参数及输出。

`capture-algorithm-raw.sh` 使用 Root 设置原厂 dump 属性并重启相机 provider，保留 capture/restore 两个入口和独占锁。异常结束后使用同一输出目录的 restore 入口恢复已保存属性。原始照片、RAW、metadata、日志与分区读回输出由调用者私下保存。

当前源码和设备结果的范围见[发布说明](../../docs/pixelos/source-publication.md)与[验证摘要](../../docs/pixelos/validation.md)。
