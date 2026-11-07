# Settings 存储容量口径

原容量口径将标称容量与 `/data` 文件系统总容量相减。
`FileUtils.roundStorageSize()` 的二进制档位和十进制返回值可使标称容量小于输入，
从而产生负的系统占用，旧缓存继续保留该值。

## 当前实现

当标称内置容量小于 `/data` 时，共用入口改用 StorageManager/vold 返回的实际物理盘容量。
总量、已用、系统项与临时文件分类共享同一口径，外置卷和容量正常设备保留原返回。
物理盘容量无效时按 `IOException` 失败处理。

[SettingsLib 修改](../../scripts/source-patches/storage-accounting/0001-settingslib-storage-accounting.patch)
接入共用容量消费者，[Settings 修改](../../scripts/source-patches/storage-accounting/0002-settings-storage-accounting.patch)
接入进度条并使用按用户隔离的 `StorageCacheAccountingV1`，旧缓存保留但不再作为新统计来源。

## 完整 ROM 集成与交付

修复已集成 `PixelOS-popsicle-20261106-storage-fix_by_Kanoe.tar.gz`。
用户于 2026-11-06 确认先行模块“已经测试通过”，于 2026-11-07 确认完整 ROM“测试完成”。
该反馈未附容量读数或逐场景清单。

模块只面向固定旧 ROM，正式产品直接编译 SettingsLib 和 Settings。
成品身份见[历史摘要](validation.md)，新源码快照验证见[源码发布说明](source-publication.md)。
