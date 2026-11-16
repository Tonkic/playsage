# 鸣潮 / OK-WW

计划来源：[ok-wuthering-waves](https://github.com/ok-oldking/ok-wuthering-waves)。
当前状态：2026-11-01 已连接本机安装的 OKWW v3.7.12 原生 OkScript MCP，在隐藏的独立 Windows 会话 2 中取得 1920×1080 截图并启动注册的 DailyTask。每日最终结果与活动发现见 `docs/live-ww.md`；不能仅凭任务已启动宣称每日完成。

计划复用截图、识别素材和任务接口；活动策略独立保存。
接入前检查 upstream README、实际 MCP tools/list、游戏窗口身份、坐标单位和任务停止语义。
公共玩法算法可以共享，但截图识别与输入不能从其他游戏直接复用。

本机开发入口：`uv run python tools/okww_mcp.py inventory`、`screenshot`、`get_run_status --run-id ID`。
原生任务通过 `run_task --file D:\PlaySage\tools\okww\daily.py` 提交；此文件只委派已注册 DailyTask 并检查活跃度，不复制每日流程。
调用前校验固定项目、后端进程会话与端口所有者；新任务还检查 WTS 连接。原生 MCP 独占执行器；取消必须等到 cancelled/failed/succeeded，不能把 stopping 当作停止。
程序允许无游戏时由原生框架在会话 2 启动游戏；若发现其他会话游戏或多个游戏进程则拒绝连接。
每次原生截图返回路径后必须实际查看图像，并检查 cached/captured_at。后台每日执行不等于 GUI 任务卡 Start 按钮已验证。
