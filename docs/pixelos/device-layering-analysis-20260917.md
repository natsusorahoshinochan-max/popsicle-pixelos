# popsicle 设备树分层

产品为 `custom_popsicle-cp2a-user`，平台为 Android 17 API 37。

| 层次 | 文件与职责 |
|---|---|
| 产品入口 | `custom_popsicle.mk` 选择 PixelOS 产品和上游配置 |
| 硬件启动 | `product/hardware-boot.mk` 在 ROM common 产品前声明 A/B、分区和 4 KiB ABI |
| 设备装配 | `device.mk` 组合硬件、IMS、官方相机和背屏 |
| PixelOS 选择 | `product/pixelos.mk` 选择 Google、AICore、界面和 ROM 资源 |
| 板级生产 | `BoardConfig.mk` 与 `board/managed-images.mk` 声明官方输入、vendor/ODM 派生和 AVB |
| 平台接口 | 正式补丁提供受管镜像生产、DEX、原厂 ABI、窗口和系统服务接线 |

设备源码见[设备树](../../device/xiaomi/popsicle/)。设备树与本仓库 helper 对应同一发布提交，
`POPSICLE_PROJECT_INPUTS` 由宿主 `source-config.mk` 指定。

维护仓库放在 Android 树之外，诊断与模板 `Android.bp` 由所属准备工具选择安装。
正式序列和准备方法见[源码准备](../../scripts/build-support/source-release.md)。
