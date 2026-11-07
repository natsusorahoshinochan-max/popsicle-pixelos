# PixelOS 生产补丁与维护源

完整装配入口为 [prepare-pixelos-source.py](prepare-pixelos-source.py)，顺序由
[pixelos-public-user.series](pixelos-public-user.series) 声明。每条记录固定 Android
仓库路径、上游提交和补丁文件。完整步骤见[源码准备](../build-support/source-release.md)。

装配器先读取全部补丁并预检各仓库的累计修改，再按序写入并安装维护源。
补丁目标与安装目标均限定在所选 Android 树，既有修改、部分应用、错误基线和冲突会明确失败。
应用过程保留真实 Git index。多仓库写入发生 I/O 错误时，依据命令输出处理已完成范围。

设备树、平台补丁、私有输入模板和 helper 属于同一维护提交。已有活动树按具体增量维护。
各目录的 group series 使用相同固定版本，可用于明确范围的单组维护。涉及额外源码安装时使用
对应 apply 入口。完整产品准备统一使用正式装配入口。

生产 helper 由 prepare-public-source.py 的 copies() 清单安装。
三份 ODM 转换源由设备树通过 POPSICLE_PROJECT_INPUTS 直接引用，并登记为镜像构建依赖。
原厂固件和私有输入保持只读，准备结果与镜像输出使用各自独立目录。

普通开发测试、夹具、回放和测试目标已从发布集合移出。正常编译中的 SELinux、ABI、
VINTF、ELF、NOTICE、签名和镜像校验继续由 Android 生产规则执行。
