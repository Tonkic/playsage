# 核对和回滚 OKWW 拖拽修复

本页适用于本机独立安装的 OKWW，不适用于 `third_party/OK-WW` 源码克隆。2026-11-15（本地时间 UTC+08:00）的修复只修改了安装版两个拖拽函数，已通过离线回归，**尚未进行游戏实测**。它不提供验证码处理、随机拟人轨迹或反作弊规避能力。

> **后续补丁：** 本页下文的修改范围和测试计数对应第一轮拖拽修复。其后已应用[第二轮输入可靠性修复及拖拽错误保留补充](okww-input-reliability.md)，扩展点击/短按异常清理，并保留拖拽与释放同时失败时的最初异常。当前文件哈希以[最新清单](../runs/services/okww/backups/swipe-error-priority-20261115-021349/manifest.json)为准；回滚顺序是拖拽错误保留补充 → 第二轮 → 第一轮，不能用旧整文件备份直接覆盖。

## 修复范围

安装目录为 `%LOCALAPPDATA%\ok-ww\data\apps\ok-ww\working`。以下路径均相对此目录：

| 文件与函数 | 修改内容 |
| --- | --- |
| `ok/device/interaction_methods/post_message.py` 的 `PostMessageInteraction.swipe` | 修复时长换算、短时拖拽除零、未到终点，以及异常时未松键；执行 `settle_time` 等待 |
| `ok/device/interaction_methods/pynput.py` 的 `PynputInteraction.swipe` | 修复时长换算和异常时未松键；执行 `settle_time` 等待；初始、按下前、移动前和结束时检查前台焦点 |

任务层 `swipe(duration=0.5)` 仍以秒为单位，并向输入后端传入 `500` 毫秒。两个后端现在按约 10 毫秒的采样间隔，用单调时钟安排每一步的目标时间，不把每次输入调用的耗时累积成额外固定等待。最后一步到达目标坐标，随后按 `settle_time`（秒）停留，再松键。原有起始等待 0.1 秒保持不变。

零时长会在按下后直接移动到终点；负数、NaN 和无穷时长在发送输入前被拒绝。进入按下阶段后，普通异常或 `KeyboardInterrupt` 都会触发 `finally` 中的松键尝试。Pynput 失焦会停止拖拽并尝试释放本次按下的鼠标键，不能保证系统接受释放；PostMessage 仍允许后台操作。

普通点击、战斗按键、鼠标后端选择、坐标换算、活动任务、用户配置和已有本地补丁均未修改。没有引入轨迹库或第二套输入后端，也没有修改源码克隆或安装器的 `repo` 缓存。

## 离线验证

只对已检查、可信的本地安装源码运行此测试。测试提取指定函数的 AST，在替换了时钟、窗口消息和 Pynput 控制器的环境中执行，不导入完整 OKWW 框架、不连接 MCP、不发送真实鼠标输入。它不是执行任意不可信 Python 的沙箱。

在 PlaySage 根目录运行：

```powershell
$env:OKWW_WORKING_DIR = Join-Path $env:LOCALAPPDATA 'ok-ww\data\apps\ok-ww\working'
uv run pytest tests/test_okww_swipe.py -q
uv run pytest -q
uv run ruff check tests/test_okww_swipe.py
```

未设置 `OKWW_WORKING_DIR` 时，安装版专用测试会跳过；显式指定的路径无效或源码结构变化时会失败，而不是静默跳过。检查完成后可用 `Remove-Item Env:OKWW_WORKING_DIR` 清除当前终端中的设置。

本次检查结果：

- 修改前：拖拽专用测试 66 项失败、6 项通过、4 项跳过，复现时长、终点、异常清理和焦点保护问题。
- 修改后：拖拽专用测试 72 项通过、4 项跳过。跳过项是 PostMessage 不适用的前台焦点检查。
- 设置安装目录后，项目完整测试 281 项通过、4 项跳过。
- 新增测试文件通过 Ruff。`uv run ruff check .` 仍报告本轮未改动的工具文件中的 73 条问题，本次未扩展修复范围。
- 临时副本中的三类故意破坏均被新增断言检出：改成单次跳转、遗漏 PostMessage 左键标志、失焦后继续移动。变异检查没有修改实际安装文件。

测试包含零时长、1～3000 毫秒拖拽、反向和零距离移动、终点停留、输入调用开销、按下/移动/等待阶段异常、前台失焦，以及任务层秒到后端毫秒的调用链。模拟时钟的结果不代表 Windows 调度或游戏响应能达到同样的时间精度。

## 生效与后续限制

应用补丁前未发现该安装版的 Python 进程，本次没有启动或重启后端。文件修改供后续正常启动时加载；如果安装器更新或重建 `working`，补丁可能被覆盖，需重新核对源码和运行上述测试，不能对未知版本自动套用旧补丁。

实机效果、焦点检查与系统输入之间的竞态、操作系统是否接受松键，以及强制终止进程时的清理都未由离线测试证明。下次真实操作必须重新确认会话、窗口、尺寸、最新观察和输入所有权，执行单步操作后再观察，不直接无人值守重放。没有证据表明这些正确性修复能降低账户风控或反作弊检测率。

## 备份与回滚

原文件及 SHA-256 清单位于：

- [本次补丁清单](../runs/services/okww/backups/swipe-20261115-013706/manifest.json)
- [原 PostMessage 文件](../runs/services/okww/backups/swipe-20261115-013706/post_message.py)
- [原 Pynput 文件](../runs/services/okww/backups/swipe-20261115-013706/pynput.py)

> **警告：** 回滚会恢复原来的拖拽缺陷。先停止该安装版的后端及任务，不要在运行过程中替换源文件。

1. 读取 `manifest.json`，核对每个 `path` 是本次安装目录，且当前文件 SHA-256 等于对应的 `after_sha256`。
2. 核对每个 `backup` 文件的 SHA-256 等于对应的 `before_sha256`。可用 PowerShell 的 `Get-FileHash -LiteralPath <文件路径> -Algorithm SHA256` 检查。
3. 只有全部路径和哈希一致时，才把两个备份分别复制回清单中的目标路径。任一文件发生后续修改时停止，不覆盖后续补丁或升级内容。
4. 再次核对目标哈希等于 `before_sha256`，然后按正常流程启动后端。离线拖拽回归在回滚后预计重新失败，不能将旧代码标记为已修复。

本次修改不改变项目架构或第三方依赖声明；历史实测报告保持原样。相关入口见 [README](../README.md) 和[鸣潮历史实测](live-ww.md)。
