# DNG保存与UltraRAW白平衡修复 v0.3

同源修复已由正式ROM承接，发布与验收范围见[交付记录](../../docs/pixelos/validation.md)。当前ROM无需安装本模块。

本目录保留面向旧七项修复PixelOS Android 17 ROM（`ro.build.date.utc=1790954511`）的KernelSU模块。
仅在上述旧基线上通过KernelSU及用户配置的系统文件挂载实现生效，同ID可更新v0.1/v0.2，重启后生效；禁用并重启恢复该旧ROM的相机。
载荷为平台签名相机APK与对应新odex/vdex，其他相机覆盖模块须先停用。

## 修复范围

- 50M RAW：对原厂明确标记`isQuadRawRemosaic`且尺寸为静态数组两倍的最终RAW16，
  复制逐次拍摄元数据，统一像素数组、有效区域、裁剪/增益图范围和镜头内参坐标。
  最终样本是已重排的2×2 Bayer，沿用真实CFA及动态黑白电平。保留平台尺寸断言；不改HAL全局元数据。
- UltraRAW：恢复本机OS4的format32、8×8分块无损JPEG RAW写入。
  使用`compressedParameters`给出的实际尺寸、有效压缩长度和64块长度；检查JPEG帧与分块边界。
  将平台DngCreator生成的校准、EXIF、方向及预览元数据保留，主图改用DNG Compression7及tile标签。
  不解码后重压、不把外层8192×6144误作本次4096×3072输出，也不将压缩RAW当作RGB。
- UltraRAW偏洋红：读取同次结果的24字节`awbFrameParams`（三个LE double），按原厂1e8精度截断约分写`AnalogBalance`，同时写单位`AsShotNeutral`，避免对算法已处理的像素重复白平衡。
  私有参数不存在时按原厂回退写单位AnalogBalance并保留原neutral；长度/数值非法时报错。
  普通RAW与50M写入路径不作此变换，不把所有RAW统一改成单位白平衡。
- 继承失败收尾、共享写入返回值、预览回退与动态白电平修复；修正诊断Rational序列化。

完整ROM仍通过同一个`device/xiaomi/popsicle/oem-camera/prepare.py`生成相机，无须从模块反向提取。
不支持的压缩协议或没有明确映射的尺寸仍报错，不能以成功空实现替代写入。

## 历史验证范围

v0.2 用户五次实拍已确认 UltraRAW、普通 RAW、50M RAW 及两种 JPG 实际保存并入库，随后发现 UltraRAW 偏洋红。

v0.3 使用此前真实 UltraRAW 压缩 payload、同次捕获的 awbFrameParams 及真实平台 DNG 模板运行生产 tile 写入器。
AnalogBalance 与原厂量化规则一致，AsShotNeutral 为 (1,1,1)。LibRaw 解码像素与 v0.2 逐像素相同，预览可解码，显影跳过原传感器红/蓝白平衡倍数，对照整体洋红消失。
上述结果来自写入器及标签验证。后续同源 v0.3 修复已完成完整 ROM 构建并获用户整包验收，结果见[交付记录](../../docs/pixelos/validation.md)。新 APK 的逐模式实拍和原厂色彩专项对照仍待记录。

## 固定旧基线的诊断与构建

v0.3默认`debug.popsicle.dng.capture=0`，不自动留存额外照片数据。
v0.1已采集的相机私有`files/pixelos-dng-failures/`不会自动删除。

```sh
python3 device/xiaomi/popsicle/oem-camera/prepare.py ANDROID_TREE \
  OFFICIAL_A17_FILESYSTEMS \
  --host-bin ANDROID_TREE/out-pixelos-user/host/linux-x86/bin
bash modules/popsicle-camera-dng/build-candidate.sh ANDROID_TREE BUILD_LOG_DIRECTORY 1790954511
python3 modules/popsicle-camera-dng/build.py ANDROID_TREE NEW_OUTPUT_DIRECTORY
```

本次复用现有ROM宿主工具、boot image与类库，执行Soong相机目标生成的JNI/Dex准备、uses-library校验、
平台签名与dexpreopt命令，保留hard verifier；没有复用旧相机预编译。正式产物为v0.3 ZIP及SHA256。
模块ZIP是KernelSU必需安装格式，16线程压缩；不改变完整ROM的tar.gz约定。
