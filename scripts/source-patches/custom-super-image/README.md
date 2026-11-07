# 自定义逻辑分区

扩展固定 Soong 文件系统生产规则，使产品声明的自定义逻辑分区参与 super 与安装镜像生产。private-inputs.bp 是私有固件生产声明模板。

完整装配使用[正式序列](../pixelos-public-user.series)，步骤见[源码准备](../../build-support/source-release.md)。各文件的固定上游 revision 由正式序列声明，已装配的活动树按具体增量维护。
