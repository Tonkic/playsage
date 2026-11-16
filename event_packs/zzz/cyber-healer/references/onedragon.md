# 原生执行流程（需Agent观察与结果复核）

按工作区 docs/child-session.md 启动隐藏的独立会话，游戏与原生OneDragon后端同在该会话。本次端点为127.0.0.1:23002/mcp；tools/child_backend.py校验会话、进程和监听端口。禁止使用主桌面23001后端或主桌面键鼠。不要复制账户配置。

先运行 `uv run python tools/onedragon_step.py observe`，Agent打开实际PNG，确认当前关卡和棋盘与 boards/ 中的对应文件一致。

在当前棋盘上，运行 `uv run python tools/repair_grid.py --board event_packs/zzz/cyber-healer/boards/caseC-stageN.json --observed OBSERVATION_JSON`，C/N须对应刚观察的案件与关卡。

执行器只使用项目内受审核代码，单次最多48格/240秒，不动态加载活动包Python。每个按键0.12秒；每步调用原生analyze_screen重新检查。需要同一活动窗口锁，且独立外部控制者必须停止。

执行返回 needs_visual_review 后再次 observe，并由Agent确认实际成功；返回码不作为实机成功条件。发生失败则先观察新截图，再根据真实已走路线重建 prefix，不重复发送结果未知的按键。

本流程为开发试验工具，尚未接入通用CLI replay或verified晋升。输入超时后最多等待5秒确认短按完成；若通信仍不可确认，必须停止并接管检查。
