# 官方相机 DNG 与 UltraRAW 保存

50M RAW、UltraRAW 保存和 UltraRAW 白平衡修复已由正式 ROM 承接。
生产入口位于[相机准备目录](../../device/xiaomi/popsicle/oem-camera/)，由 `prepare.py`、
`raw_save.py`、`PixelosRawSave.java` 和 `DngTiles.java` 共同实现。

## 50M RAW 几何

对原厂显式标记 `isQuadRawRemosaic` 且尺寸符合两倍静态数组关系的最终 RAW16，
逐次复制 CameraCharacteristics 和 CaptureResult，同步调整 pixel、active、crop、
gain map 和镜头内参坐标。保留实际 CFA、动态黑白电平和标准 DngCreator 的校准契约。

最终保存输入与 Quad 中间节点分别解释，其他尺寸沿正常断言失败处理。

## UltraRAW 无损 tiles

当前 OS4 输入使用 format32、8×8 分块无损 JPEG Bayer。`compressedParameters`
给出实际尺寸、有效压缩长度和 64 块长度。写入器验证块边界和 SOF3 帧，
保留平台校准、EXIF、方向和预览元数据，将主图存储改为 DNG Compression7 与 tile 标签。

写入只消费有效压缩数据，保留压缩像素字节，重定位主图及预览引用。
外层请求尺寸和分配 buffer 长度分别按各自契约解释。

<a id="ultraraw白平衡修复v03-2026-10-06"></a>
## UltraRAW 白平衡

同次 CaptureResult 的 `awbFrameParams` 含三个 little-endian double。
写入器按原厂 1e8 精度量化并约分生成 `AnalogBalance`，同时设置单位 `AsShotNeutral`，
使已经处理的像素使用对应白平衡语义。缺少私有参数时沿原厂单位 AnalogBalance 回退，
非法长度、非有限值、非正值和超界值按失败处理。

普通 RAW 和 50M 使用各自标准保存路径。

## 保存生命周期

共享写入失败向调用者返回失败，发布只接受完整写入结果。异常收尾清理本次新建 URI 或路径，
保留原有照片。预览使用平台 DngCreator 的实际解码输入，动态白电平使用独立元数据副本。

失败输入采集由 `debug.popsicle.dng.capture` 控制，生产默认关闭。原厂照片和捕获数据
由外部资料保存。

## 既有交付范围

v0.2 已有普通 RAW、50M RAW、UltraRAW 和两种 JPG 的保存与入库结果。
v0.3 修复 UltraRAW 白平衡，并随 20261007 完整 ROM 交付，用户于 2026-10-08 确认整包通过。
逐镜头和全部场景的反馈范围见[历史摘要](validation.md)。
