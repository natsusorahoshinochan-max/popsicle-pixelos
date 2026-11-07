# popsicle PixelOS fastboot 安装说明

三平台安装包使用本页的操作流程。交付版本与反馈范围见[项目进度](progress.md)。设备操作按具体任务授权执行。

适用设备为 Xiaomi popsicle，Bootloader 必须保持解锁。安装器支持边界为完整官方 A16 OS3.0.318.0 起点，并检查 anti 值为 0 或 1。包内硬件固件来自官方 A17 OS4.0.0.23.XPBCNXM，系统来自同一份 PixelOS `custom_popsicle-cp2a-user` target-files。完整 ROM 的用户反馈不扩大任意起点、跨 ROM 或保留数据的兼容承诺。

## 发布包与电脑

完整解压发布 `.tar.gz`，保留目录结构。包内包含 `images/` 下的 50 个镜像、`metadata/flash-manifest.tsv`、`metadata/SHA256SUMS`、三平台入口和 `tools/` 配套工具，macOS/Linux 入口还使用 `scripts/flash-common.sh`。使用包内当前平台的工具，不需要指定外部 `FASTBOOT`。

在解压目录使用对应入口。

| 平台 | 命令 |
|---|---|
| macOS | `bash ./flash-fastboot_macOS.sh` |
| Linux | `bash ./flash-fastboot_Linux.sh` |
| Windows PowerShell | `powershell.exe -NoProfile -ExecutionPolicy Bypass -File .\flash-fastboot_Windows.ps1` |

Windows 需具备可识别设备的 fastboot 驱动。macOS/Linux 的包内工具须保留可执行权限。README、画作及其他平台附件不作为刷写前提，画作不可用时显示文字。

## 安装元数据

`metadata/flash-manifest.tsv` 无表头，每行固定五列，按刷写顺序排列。

| 列 | 含义 |
|---|---|
| 1 | 刷写目标。B 槽分区名或共享物理分区 `super` |
| 2 | 相对安装包根目录的镜像路径，三平台包使用 `images/` |
| 3 | 包内镜像文件字节数 |
| 4 | 写入后的展开字节数，用于分区容量检查，普通 raw 镜像与第3列相同，sparse super 为 `13421772800` |
| 5 | 来源标识。`a17-payload`、`pixelos-super` 或 `pixelos-target-files` |

安装器固定目标与顺序，清单不能增加分区或改变刷写次序。`metadata/SHA256SUMS` 保存包内文件摘要，安装器读取其中所需镜像、清单及本平台实际工具的条目，发布归档旁的 `.tar.gz.sha256` 则用于识别整个下载文件。

## 获得刷机授权后的操作

1. 先备份数据，确认设备处于上述起点及解锁状态，进入 Bootloader fastboot，不能处于 fastbootd。只连接目标设备。
2. 运行对应入口，按回车继续。脚本检查固定镜像、安装清单及当前平台实际工具的摘要，并检查机型、解锁、模式、槽位、anti、分区容量和数据分区类型。检测详情写入 `logs/flash-*.log`。
3. 明确选择数据处理方式。输入 `1` 擦除并格式化 userdata 和 metadata，包括内部存储、应用及锁屏加密信息，输入 `2` 跳过这两个分区的擦除和格式化，仍重写系统、固件及完整 super。**保留模式的启动与解密兼容性尚未实机验证。**
4. 选择清空模式后，脚本在任何刷写之前检查格式化工具。再输入小写 `yes` 才开始，其他输入或无输入均取消。
5. 脚本固定写入 B 槽固件、完整 super 和匹配启动镜像，按选择处理数据，最后写入正常未注入的 init_boot、选择 B 槽并发送重启命令。刷写过程显示 fastboot 输出并记录日志。

完整 super 会重建两个逻辑槽位，仅 B 槽有系统，A 槽不能当作回滚系统。不要手动混换 recovery/init_boot，不要重新锁定 Bootloader。保留模式不是 OTA 安装流程。

## 失败与恢复

任一命令失败立即停止，保留 `logs/flash-*.log`，先分析失败原因，不继续切槽或重启。保留完整官方恢复输入，需要恢复时使用匹配 popsicle 的完整官方线刷包，继续保持解锁。恢复与再次刷机按当次授权范围执行。

脚本显示完成仅表示刷写及重启命令完成，不代表启动与硬件验收通过。用户实测结果记录在对应发布文档，不继承其他 ROM 的测试结论。
