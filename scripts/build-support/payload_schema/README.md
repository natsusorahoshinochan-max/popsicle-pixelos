# Payload protobuf

`update_metadata.proto` 来自固定 AOSP `system/update_engine` 提交
`1938420295a90e0bfef3ce9ed867b87da2e63a6f`，保留原 Apache-2.0 声明。
[上游源码](https://android.googlesource.com/platform/system/update_engine/+/1938420295a90e0bfef3ce9ed867b87da2e63a6f/update_metadata.proto)。

生成模块随工具源码保存。宿主运行依赖由上级 `requirements.txt` 固定为
`protobuf==5.29.5`。重新生成使用 Python 3.12、`grpcio-tools==1.71.2`
内附的 protobuf Python 5.29.0 生成器。

```sh
python3 -m venv /path/to/proto-venv
/path/to/proto-venv/bin/pip install protobuf==5.29.5 grpcio-tools==1.71.2
/path/to/proto-venv/bin/python -m grpc_tools.protoc \
  -I scripts/build-support/payload_schema \
  --python_out=scripts/build-support/payload_schema \
  scripts/build-support/payload_schema/update_metadata.proto
```

导出器只从本目录导入解析模块，固件输入目录提供原始数据文件。
