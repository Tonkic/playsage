# 绝区零 / OneDragon

计划来源：[ZenlessZoneZero-OneDragon](https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon)。
当前状态：源码已克隆到 third_party/OneDragon，独立环境已安装，原生 MCP 已实机连接。开发脚本支持观察、受限点击和按键；通用CLI适配器/自动重放仍未接入。

当前启动：tools/start-child-session.ps1 建立后台分身，分身内启动游戏与后端，端点23002/mcp；详见 docs/child-session.md。工具检查真实进程所属会话和端口拥有者，拒绝旧的主会话23001接口。游戏为管理员进程时，后端也需要管理员权限。

已用原生 check_game_window、analyze_screen(save_image=True)、click_game、key_tap、get_run_status 验证真实菜单/活动操作。analyze_screen 返回截图文件路径；工具实际打开PNG后才能作为视觉证据。截图1920×1080；最初主桌面窗口2560×1440，当前独立会话窗口1920×1080。

单动作工具：tools/onedragon_step.py。网格活动工具：tools/repair_grid.py。均在输入前校验窗口与观察，使用本地窗口锁；该锁不能拦截独立外部MCP或人工输入。

key_tap 的同步上游实现按 press_time 后释放；本项目只发0.12秒短按。客户端取消不证明服务端取消，取消时额外等待输入完成，无法确认则停止。原生 stop_run 只停止原生任务，不能当作任意键盘释放接口。

本次探索：event_packs/zzz/cyber-healer。来源固定提交见 third_party/repositories.json；本机旧版 D:/zzz-one-dragon 没有该 MCP 接口，不能混用。
