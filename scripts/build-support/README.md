# PixelOS build support

入口为[源码准备](source-release.md)，原始输入见[输入清单](source-inputs.md)。仅使用本项目源和输出。

## 工具职责

| 工具 | 范围 |
|---|---|
| `prepare-source-inputs.py` | 准备匹配原始固件、属性、OEM provider、IMS/QCC、相机、背屏和运营商输入 |
| `prepare-pixelos-inputs.py` | source/aicore 入口使用显式宿主工具或固定树内 SDK；carrier 入口更新运营商输入 |
| `build-fastboot-release.sh` | 构建PixelOS target-files并调用导出器，产物写入generated目录 |
| `export-fastboot-release.py` | 从已有同一份target-files导出镜像、平铺fastboot目录和清单 |
| `package-fastboot-release.py` | 将本次导出镜像、已有宿主工具和当前安装器组装为三平台 `.tar.gz` |
| `prepare-platform-tools.py` | 从三平台 SDK ZIP 准备独立宿主工具目录，保留 NOTICE 和版本属性 |
| `repackage-installer.py` | 复用已有三平台包的镜像和工具，更新安装器并生成新 `.tar.gz` |
| `build-install-super.py` | 组装动态分区并生成明确零填充的full-device-write sparse super |
| `flash-fastboot.sh` | 按交互确认执行安装，校验设备与分区，失败时退出 |

目录、构建环境及输入准备、导出和打包命令统一见[源码准备](source-release.md)。当前发布与验收见[项目进度](../../docs/pixelos/progress.md)。

## 产物生成

使用同一PixelOS user target-files的最终IMAGES，保持正常未注入init_boot、A/B、动态分区、recovery及update_engine。Android自身的依赖、策略、NOTICE、签名生成等机制保持。

导出完成镜像组装和复制，并生成安装器使用的SHA256SUMS及flash-manifest.tsv。READY.txt与release-result.json表示产物生成完成。具体流程和验收记录见[装配与导出说明](../../docs/pixelos/source-publication.md)。

标准交付采用A16 OS3.0.318.0起点的B槽packed-super全新安装包，配套同版官方A17固件。安装流程见[安装说明](../../docs/pixelos/fastboot-install.md)。

