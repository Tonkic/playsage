# 来源与许可

此独立 Windows 宿主采用 GPL-3.0-or-later；完整许可见 LICENSE。

复用 BetterGI (babalae/better-genshin-impact)，提交
43eecc21bf700d3db58a174c2e66f5c90e7c69f9：

- csproj 链接原始 RdpActiveXHost、ChildSessionNativeMethods、ChildSessionEnvironmentCheck、ChildSessionConnectionFailedEventArgs，未修改这些源文件。
- SessionLauncher 根据 ChildSessionProcessLauncher 缩减，保留临时任务、交互令牌、目标会话和清理机制，限定为本项目的探测、后端及绝区零启动。
- Program 为 PlaySage 宿主，状态写入 runs/services/child-session。没有密码读取/存储、认证操作、系统安全设置修改或注销会话操作。

来源：https://github.com/babalae/better-genshin-impact

构建依赖完整源码克隆；分发编译产物时须同时满足上游 GPL 对源码、许可和通知的要求。此宿主不进入 Python wheel。
