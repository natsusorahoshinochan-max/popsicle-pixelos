# 原厂前台事件接口

从 PixelOS 的真实 WM 活动、任务焦点和显示变化生成原厂前台回调，保留 Binder 调用者身份与包签名检查。ProcessManager 使用上游 EXCEPTION_NO_FUZZER 登记，该服务当前未提供 fuzz harness。

完整装配使用[正式序列](../pixelos-public-user.series)，步骤见[源码准备](../../build-support/source-release.md)。各文件的固定上游 revision 由正式序列声明，已装配的活动树按具体增量维护。
