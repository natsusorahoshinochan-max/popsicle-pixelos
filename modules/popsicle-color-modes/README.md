# 主屏三模式修复（旧模块已撤回）

v0.1和v0.2均已撤回，请勿安装。KernelSU报告已确认实际挂载目录中SurfaceFlinger被截断、文件和目录为unlabeled，旧启动日志捕获基础库加载失败及bpfloader触发重启。故障记录见[颜色专题](../../docs/pixelos/validation.md)。

同源修复对应正式第119至120条，正式集成与验收范围见[发布记录](../../docs/pixelos/validation.md)。当前ROM不依赖本模块；安装ROM前停用或卸载对应旧覆盖模块。ROM通过不撤销旧模块的撤回状态。

## 保留的实现与版本边界

自然及增强向原厂HAL发送主屏专家sRGB请求26/3/0，清除前态vendor LUT；SurfaceFlinger只对主屏managed SDR sRGB输出选择267，增强保留AOSP的1.1倍饱和度。鲜艳沿用AOSP unmanaged/native与原厂effect1。使用现有颜色设置和亮屏重应用入口，没有轮询脚本、Frida、开机调试命令或SELinux放宽。

旧模块仅面向2026-10-03交付的七项修复版（`ro.system.build.date.utc=1790954511`）。载荷为services.jar及ART/verity配套、签名BuildManifest和surfaceflinger，通过KernelSU及用户配置的系统文件挂载实现覆盖文件。v0.2仅修正暂存源目录的SurfaceFlinger标签，未覆盖后续复制失败路径，不能继续安装或推荐。

修复范围为主屏三模式SDR sRGB切换。P3/HDR保留框架选择分支；整包验收不补写这些场景及原厂HAL专家状态与其他内容交互的专项结果。
