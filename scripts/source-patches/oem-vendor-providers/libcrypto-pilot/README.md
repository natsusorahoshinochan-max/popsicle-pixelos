# OEM libcrypto provider

提供原厂 vendor libcrypto ABI。配套补丁导出固定 BoringSSL 的原始头文件。保留原 ELF 的完整性初始化和既有 FIPS/self-test 启动链，输入准备保持原始字节。

prepare-private-input.py 读取显式指定的原厂文件系统与私有输出目录，提取原始库和对应 NOTICE。
已有相同输入可复用，内容冲突、链接输出和缺失映射会失败。完整准备由
[ROM 输入入口](../../../build-support/source-inputs.md)编排。

Android.bp 是私有 provider 模板。实际消费者检查工具使用固定 Android checker 与真实
stage ELF，保持符号和依赖检查。编译和运行结果的范围见
[当前版本](../../../../docs/pixelos/progress.md)。
