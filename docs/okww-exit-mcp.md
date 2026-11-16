# 通过 OKWW 原生 MCP 退出鸣潮

## 适用范围

此扩展在 OKWW 原生 MCP 服务中注册 `exit_game`，用于结束独立 Windows 副会话中的鸣潮游戏进程。它调用 OKWW 自带的 `DeviceManager.stop_hwnd()`；底层按游戏可执行文件路径终止进程，**不是游戏菜单中的正常登出**。未保存的游戏内状态可能丢失。

接口不退出 Windows 会话、不关闭分身查看器，也不关闭 OKWW MCP 服务。没有游戏进程时返回 `not_running`，不会启动游戏。

## 安装和更新

在项目根目录执行：

```powershell
uv run python tools/install_okww_exit_mcp.py
uv run python tools/install_okww_exit_mcp.py --apply
```

第一条命令仅检查安装计划。第二条命令在核对原生工厂函数和注册位置后，备份文件并安装扩展。备份保存在 `runs/services/okww/backups/`，包括原文件和清单。安装后必须先通过原生 `exit_process` 停止旧 MCP 服务，再通过可见副会话的现有启动流程重启服务。

扩展位于 OKWW 安装目录内的 `src/playsage_exit_game_mcp.py`，原生 `ok/core/mcp_server.py` 仅增加注册调用。不创建第二套 MCP 服务或输入后端。OKWW 更新可能覆盖注册位置；更新后先运行检查，再决定是否重新安装。遇到不兼容签名时停止，不强行修改。

## 退出游戏

确认副会话在线且没有正在执行的 OKWW 任务，然后执行：

```powershell
uv run python tools/okww_mcp.py exit_game --reason "切换到绝区零" --expected-session-id 2
uv run python tools/okww_mcp.py get_run_status --run-id <返回的运行ID>
```

`reason` 必须是 1–500 字符的非空原因。`expected_session_id` 必须与已核验的活动副会话一致，不能是主会话。原生 MCP 调用参数名为 `reason` 和 `expected_session_id`。

提交后返回运行 ID，必须轮询至终态。只有原游戏进程退出才返回 `exited`；原本没有游戏时返回 `not_running`。提交成功不等于退出成功。退出操作沿用原生运行队列和状态记录，最长等待原进程退出 15 秒。

## 安全检查

- 校验后端实际 Windows 会话、启动环境中的副会话 ID 和会话连接状态。
- 后端忙碌时拒绝退出；不打断正在运行的原生任务。
- 检查所有同名游戏进程。出现多个实例、其他会话实例、路径不符或身份无法读取时拒绝操作。
- 调用原生方法前再次核对 PID、创建时间和原生窗口附着路径。
- 不自行实现进程终止，不通过通用任务入口触发游戏自动启动。

这些检查不能约束用户或其他独立程序在检查后并发启动游戏。切换游戏期间不要同时运行其他输入后端。

## 回滚

先停止原生 MCP 服务，再依据对应备份清单恢复 `ok/core/mcp_server.py`。若清单显示扩展安装前不存在，删除本次安装的 `src/playsage_exit_game_mcp.py`；若原本存在，则恢复其备份。重新启动原生服务后核对工具列表。不要将其他版本的备份覆盖到升级后的安装中。

## 验证边界

实机运行 `b4bc20004219474dbf8090a62de1a66a` 已调用原生 `DeviceManager.stop_hwnd()`，确认副会话 2 的游戏 PID 42792 退出。该证据验证原生退出方法，不替代新增 MCP 注册和调用链的单独验证。

新增扩展、安装器和客户端参数的离线测试覆盖会话身份、忙碌拒绝、多实例拒绝、路径与进程身份变化、无进程幂等和注册行为。离线测试不代表游戏每日或活动已完成。

2026-11-15 重启 OKWW 后，原生 `tools/list` 已列出 `exit_game(reason, expected_session_id)`。MCP 运行 `7cf553fff13348458e6beac24c4b9f05` 在副会话 2 返回 `succeeded`，结果为 `not_running`，未重新启动游戏；服务随后仍可响应 `get_run_status`。新增 MCP 包装层的有进程退出路径尚未单独实机验证，不能与前述原生方法实测混为一谈。

本轮针对性测试 33 项通过；全套 pytest 为 237 通过、172 跳过。新增和修改的 Python 文件 Ruff 检查通过；全仓 Ruff 仍有 71 项既有范围外问题。以上结果不代表鸣潮每日或绝区零活动已完成。
