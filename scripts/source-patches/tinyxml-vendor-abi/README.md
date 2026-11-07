# 原厂 tinyxml2 vendor ABI

固定 tinyxml2 的设备选择 defaults 仅为 vendor 变体提供匹配原厂的对象布局和头文件。
其他镜像及宿主使用上游 source provider。补丁保留文件自身的许可材料。

完整装配使用[正式序列](../pixelos-public-user.series)，步骤见
[源码准备](../../build-support/source-release.md)。原厂 ABI 的最终使用条件由实际 ELF
依赖与当前设备配置决定。
