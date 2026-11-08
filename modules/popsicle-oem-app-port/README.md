# 官方双 App 的 PixelOS ROM 移植测试模块

本目录保留官方相机、背屏及亮度移植的KernelSU测试载体。同源修复已集成正式ROM；模块的亮度实现与测试见[修复记录](../../docs/pixelos/validation.md)，当前发布状态见[进度](../../docs/pixelos/progress.md)。

v0.18 相机与背屏移植的已确认范围见[移植验收记录](../../docs/pixelos/validation.md)，各版结果只对应各自载荷与测试基线。

历史补丁编号沿用[固定来源](../../docs/pixelos/source-publication.md)的原 128 条维护序列。v0.20 的已验收基线为该序列第 96 条整合 ROM，`ro.system.build.date.utc=1789410271`。
此模块使用本项目同一批 PixelOS 编译产物，覆盖官方 APK、framework/services/SystemUI、原库与配置、类路径及匹配的预编译/fs-verity 配套文件。完整载荷包括基础及扩展 boot ART/OAT/VDEX、APK 预优化和签名配套文件、原背屏资源；模块投递完整运行时移植载荷，适用于安装器核对的指定PixelOS Android 17基线；完整ROM镜像由正式发布链生成。构建在远端 Android 树进行；先用 [payload.py](payload.py) 输出 targets 并完成对应构建，再按目标 ROM 选择 `--native-rom` 或旧版策略输入，package 到新输出目录。原生ROM打包复用已有正式产物；旧策略分支保留下述基线比较。

通过 KernelSU 安装，系统文件覆盖由用户配置的挂载实现负责。v0.20 的 `--native-rom` 包使用正式 ROM 原生策略，诊断默认关闭。以下加载说明仅适用于旧版移植包。模块保持 SELinux Enforcing，前台服务只使用正式 ROM 的精确 type/allow。post-mount 重新加载既有规则以使 servicemanager 重读服务标签。自 v0.16 起从完整 live policy 在打包阶段派生相机专属域，启动时核对同一基线后加载，流程与严格比较门槛见下文。七项相机场景属性的运行时映射仍沿用 init 更早阶段建立的旧标签，文件挂载只覆盖 property_contexts 内容。模块沿用精确属性权限，写入拒绝应记录为模块与 ROM 的验证差异。相机场景 Handler 的失败边界修复保留真实错误，避免终止共享系统线程。

在匹配的旧基线上停用 `popsicle-oem-app-port` 并重启，可恢复底层ROM文件。模块依赖可用的root ADB停用回滚路径，系统分区和启动镜像保持原样。各版App、相机和背屏业务结果见下文及对应专题。

## v0.16 历史实现与观察范围

| 范围 | 同批正式源与模块载荷 | 当时观察范围 |
|---|---|---|
| 显示编号 | `vendor/etc/displayconfig/display_layout_configuration.xml` 按已确认的两块物理屏，在 state0 预留主屏逻辑 0、背屏逻辑 1 | 冷启动物理/逻辑映射、原 Back/Home 输入窗、任务查询与启动都正确落到背屏 |
| 独立电源组 | 同一 layout 为真实背屏指定 `displayGroup="rear"`，原 `goToSleep(display1)` 能交给单独组 | 双击仅使背屏直接 OFF；主屏睡/醒、原明确 wake1 和窗口恢复 |
| 遮挡行为 | `product/etc/displayconfig/display_id_4630946457447247252.xml` 设置 `independentProximitySensor=false`，沿用正式 ROM 文件 | 遮挡沿用正式 ROM 的传感器路由，该版原 NonUI 输入防误触仍待接入 |
| SystemUI/Launcher | [背屏 SystemUI 策略](../../scripts/source-patches/oem-rear-foundation/0004-rear-system-ui-policy.patch)按真实 DisplayInfo/uniqueId 判断背屏，跳过背屏 StatusBar 窗口，限制 shade 目标和默认 EdgeBack。仅对默认 Launcher 的 outgoing 协议增加背屏导航/Home/Overview/Search/Touchpad 禁用资格 | 原应用接收手势、主屏保持可用。Nexus 的 `swipe-up` 监视器可仍存在，以实际消费者和 pilfer 结果核对手势归属 |
| 相机域 | 精确平台签名 privileged `com.android.camera` 切换到 `popsicle_camera_app`，保留 `privapp_data_file` 与 SDK36/Qigsaw 沙箱，再补原 MiSys 客户端、ProcessManager、DSP 和属性权限 | 严格策略构建、模块相对正式策略等价、实际域、原 LUT 写入检查与受影响的拍摄/保存/释放路径 |

默认 Launcher 的额外禁用位只改变该消费者收到的背屏协议，共享 SysUI 状态和原背屏服务协议保持原样，主屏及普通外接显示维持原行为。accessibility、screen-pinned、既有动画续接等特殊分支沿用原处理，仍待专项确认。

稳定显示编号和独立组提供背屏电源路由，后续正式修复已接通独立 AOD 调度、Dream 会话所有权及 Doze 锁清理，见[背屏结构](../../docs/pixelos/rear-system-architecture-plan-20260929.md)。v0.15 的触觉只读测试通过了已加载开关、有效编号、非法编号/strength 拒绝和 HAL 支持查询。其他电源状态组合、主动振动及完整手势仍待专项确认。

## 完整相机策略的派生与加载

正式 ROM 的相机域由[专属域源](../../device/xiaomi/popsicle/sepolicy/system_ext/private/popsicle_camera_app.te)、[精确 seapp 映射](../../device/xiaomi/popsicle/sepolicy/system_ext/private/seapp_contexts)及 [vendor_policy.py](../../scripts/source-patches/firmware-filesystems/vendor_policy.py)共同生成。旧策略模块基于目标内核完整 live policy 派生完整 SDK36 域契约，保留已加载的 KSU、MLS、约束和其他所有者规则。正式 ROM 的二进制策略用于下述比较。

旧策略分支在打包阶段用 [clone-camera-policy.awk](tools/clone-camera-policy.awk) 从完整 live `priv_app_36` 克隆五个类型及相关属性、双向规则、具名 inode/nlmsg 转换，再加入 [camera-extra.cil](tools/camera-extra.cil)，编译并完成下述正式策略比较。未知相关构造、已有目标域或不完整基线均拒绝。

[load-camera-policy.sh](tools/load-camera-policy.sh) 在 post-mount 只读取当次 live，与打包的 `policy-baseline.bin` 逐字节比较。相同才加载已验证的 `camera-policy.bin`，有差异则拒绝并记录日志。编译在宿主打包阶段完成，该次测试的 KernelSU 阶段脚本仅同步等待 10 秒，设备编译实测 130 秒、宿主 142.604 秒。

正式 ROM 直接使用严格构建策略。`popsicle-policy-export` 为独立构建的同树诊断工具，已在手机成功只读导出。旧策略的运行时装载和业务结果见下文各版记录。

## 打包参数与严格门槛

匹配载荷的打包入口为远端本项目维护副本中的 `payload.py`。下例变量指向 Android 树和新的打包输出目录，输出目录必须尚不存在。对已原生集成相机策略的 ROM 使用 `--native-rom`，沿用设备上已集成的正式策略。

```sh
python3 modules/popsicle-oem-app-port/payload.py "$POPSICLE_ANDROID_TREE" targets

python3 modules/popsicle-oem-app-port/payload.py "$POPSICLE_ANDROID_TREE" package \
    --output "$POPSICLE_PACKAGE_OUTPUT" --native-rom
```

`targets` 输出运行时载荷所需的文件目标。当前树使用 `out-pixelos-user`，复用有效输出，窄目标按项目约束 `-j16 -k20`、Java highmem=4。

针对尚未集成相机策略的匹配旧 ROM，省略 `--native-rom` 时，`package` 要求 `--policy-baseline` 和 `--policy-export`，并需已有正式 `precompiled_sepolicy` 作为比较输入。前者必须是匹配 KSU 设备的完整内核策略，后者必须是同树构建的 arm64 工具，打包器检查 ELF64 little-endian/EM_AARCH64 头。此分支在暂存载荷之前使用本树宿主 `checkpolicy`/`secilc` 验证策略。

- 读取真实正式目标 `out-pixelos-user/soong/.intermediates/system/sepolicy/precompiled_sepolicy/android_common/popsicle/precompiled_sepolicy`，以及输入 live baseline。
- 用相同克隆规则与 `camera-extra.cil` 生成 live 候选，实际编译后重新导出，以二进制策略语义作为比较输入，并保留编译/neverallow 检查。
- [check-camera-policy.py](tools/check-camera-policy.py) 比较两份编译策略中“相机相对各自 `priv_app_36`”的完整新增和移除差异，展开属性、合并 AV/xperm，检查正反向边、角色、具名转换与约束的类型投影。相机及基线的五类型命名空间采用交换映射，避免把新→旧权限边折叠掉。
- 只有差异完全匹配且严格解析通过才继续打包，输出 `policy-validation.json`，其 scope 是 `camera-relative-semantic-delta`，用于核对相机域相对各自 `priv_app_36` 的策略增减。

打包器继续检查所有载荷文件存在、对应 `.fsv_meta` 不旧于原文件，并使用完整显式清单生成 ZIP，条目与暂存集合必须完全一致，原隐藏 `.data` 主题也包含在内。输出包含 `staging/payload-files.txt`、`zip-inputs.txt` 及 `popsicle-oem-app-port.zip`，仅旧策略分支额外生成 `policy-validation/` 和 `policy-validation.json`。

<a id="版本演进"></a>

## 各版载荷、故障与测试范围

v0.2 载荷要求四项新增 framework 资源使用本项目固定编号，已有 15,295 项资源编号保持不变。v0.1 首次测试发现默认编号移动导致旧电话组件崩溃，已停用回滚。维护打包时须沿用固定编号的 framework-res。实际测试状态见[记录](../../docs/pixelos/validation.md)。

v0.3 在此基础上加入第 72 条照片请求键补正，保留原 APK；仅向指定官方相机/camera 5 的客户端 metadata 副本呈现真实 imageName 能力。构建和上机状态见[照片修复](../../docs/pixelos/validation.md)。

v0.4 加入 camera 2 的同一请求名语义、QTI HEVC 长度前缀到封装输入的转换，以及精确相机包的 priv_app_36/privapp_data_file 映射。载荷新增 libstagefright.so 和 system_ext_seapp_contexts，使用系统既有特权 App native 加载策略。构建、实际加载及验收结果见[本批记录](../../docs/pixelos/validation.md)。

v0.5 使用原相机的最小派生 APK，将能力构造函数改走原有 vendor descriptor 名称发现分支，保留真实 metadata、会话检查、原 UI 和算法。原始私有 APK 保持不变，构建照常平台签名及预优化。构建与目标系统验收见[执行记录](../../docs/pixelos/validation.md)。

v0.6 载荷加入普通版进程策略配置、锁定/云端/one-push 的 AMS 与 Binder 接线，以及固定编号 0x01110327 的策略开关。资源表已确认保留 v0.5 全部名称和编号，完整构建及上机状态见[策略实施](../../docs/pixelos/validation.md)。v0.6 完成 24:04 构建、安装和 Enforcing 启动，真实锁定/解锁及持久化恢复通过，该版原 CameraOpt Lifecycle 的其余依赖仍待接通。

v0.7 加入第 80 条的 Focus Provider、原权限声明和真实批量通知权限查询。详细验证状态见[背屏 Provider](../../docs/pixelos/validation.md)。

v0.7 构建通过，但启动因缺少 SystemUI 的 OEM 特权授权失败，该次回退恢复 v0.6。v0.8 在设备树与模块清单中增加准确的 system_ext 权限 XML，取代 v0.7 失败包。该次停用后 APK 解析缓存仍可能保留较新载荷声明，实际加载版本需核对 APK 解析状态。当时仅清除了 SystemUI/framework-res 的两份可重建缓存，原 ROM 基线仍出现桌面/网络进程异常，最终重新安装 v0.6 恢复，详见实施记录。

v0.9 补齐基础 boot.art/boot.oat/boot.vdex 及其 fs-verity，和全部扩展镜像共同装配。v0.8 解决特权授权后仍有普通应用 native 崩溃，当时恢复了 v0.6。镜像缺口已证实，补齐后的运行结果见下文。

v0.9 已构建、安装并 Enforcing 启动，五项核心/背屏进程连续检查稳定，真实 NMS/Provider 只读接口及 UID9999 拒绝通过。完整业务仍待验证，详见上述背屏 Provider 记录。

v0.10 增加 installd，接通原背屏主题路径的应用数据生命周期。真实数据位于标准 DE 包目录下的 oem_theme，沿用实际 platform_app 域与完整 app_data_file 标签，原路径仅保留 system-owned 链接及 0711 祖先。正常 DE 清理管理数据，卸载/用户删除同时移除准确链接，拒绝替换错误目标、所有者或已有目录。权限由既有应用沙箱和文件标签管理。第 82 至 85 条的构建与真实目录/界面结果见对应实施记录。

v0.10 已构建并安装，修复安装脚本的 set_perm 默认标签覆盖后，实际 installd_exec、Enforcing 启动及原 App 在 DE 中的配置/日志/助手写入通过。主题子目录被原 App chmod0777，外层 DE 包目录仍保持0700。该版主面板待装配原预置主题，完整主题、Home/显示及相机业务仍待验证。

v0.11 加入 121 个原背屏媒体和精确引用的预置主题文件，从私有准备源的 resource-files.txt 生成构建目标及载荷文件集合，保留原 JSON、主题内容和认证资料。构建/上机状态见背屏实施记录。

v0.11 已修复隐藏主题漏包并实际安装，打包改用 soong_zip 显式清单，ZIP 条目须与全部暂存文件一致。运行资源已挂载，原 MAML 遇到 MiuiDisplayMetrics 缺类崩溃。v0.12 加入第 86 条原密度契约，沿用设备密度和既有属性权限，构建与运行结果分别记录。

v0.12 合并第 87 条原背屏单实例 Home 条件，只对实际物理背屏及配置的准确组件提供原单实例资格，保留其余启动检查。密度先行载荷和合并后的 Home/MAML 分别记录构建与运行结果。


v0.12 安装后，原 Home 自动选择生效，但 MAML 设置缺类及本地 Shell 清理异常导致崩溃。v0.13 加入第88至89条，接通真实本地注销及原设置读取 ABI，运行结果见下文。

v0.13 构建成功并实际安装，原时钟绘制但触摸缺 HapticFeedbackUtil 仍崩溃。v0.14 合入 90 至 91 条 Secure/UserHandle 和独立背屏原方向、全幅及导航策略。后续已构建、安装，实机验证了 rotation0 全幅显示及 Taskbar/inset 隐藏，触觉缺类仍阻断原拖动。

v0.15 合入第 92 条原线性马达接口与效果编号契约，完整载荷构建 27:21/exit0，随后实际安装并 Enforcing 启动。v0.14 已有 15300 项资源编号全部保持，仅新增固定 bool 编号 0x01110328。用户确认左→右教程不再闪退，已加载 boot 类的只读触觉边界/HAL 支持测试 PASS。v0.15 测试仍有背屏显示编号、原返回/Home、SystemUI 下拉、遮挡与相机权限问题，v0.16 的对应实现见上表和[本批记录](../../docs/pixelos/validation.md)。

v0.19 用于亮度诊断，v0.20 修复相机取消临时亮度并获用户验收。原生 ROM 载荷使用正式相机策略，按目标 system build date 校验安装。`--trace-brightness` 是显式诊断开关，普通修复包默认关闭。源码与验收结果见[亮度修复记录](../../docs/pixelos/validation.md)。
