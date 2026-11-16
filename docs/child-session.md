# 后台桌面分身

按照用户要求复用 BetterGI Child Session 实现，游戏与 OneDragon 一起运行在 Windows 独立会话。主桌面的键鼠不参与操作。普通虚拟桌面不是这个方案。

> **UU 远程兼容提醒：** 本机已复现启动副会话后，UU 服务端运行在副会话而非主桌面的情况。只有 UU 远程访问通道时，不要在无人值守状态下启动或重连分身。临时恢复方法和验证边界见下文“恢复 UU 的主桌面远程”。

## 当前实测

2026-11-01，Windows build 26200：Child Session 已由系统启用，TermService 运行，RDP 主机已开启。未修改远程桌面、安全配置或账户。

独立会话2已建立，1920×1080；OneDragon监听127.0.0.1:23002，进程55888，游戏进程52976，二者都在会话2。进程号只是此次证据，不能用于下次盲目启动或停止。已在隐藏分身中完成绝区零「赛博圣手，出诊！」第二至第四案共12关并逐案领奖，见[实测报告](live-background.md)。第五案时间未到；尚未验证断线恢复或无人值守长期稳定性。

运行状态保存于 runs/services/child-session。status.json 是最近事件，不是存活证明；实际操作前由 tools/child_backend.py 检查进程所属会话、WTS连接状态、TCP端口拥有者。开发输入工具只允许已确认的会话2或其他大于1的独立会话，拒绝旧的23001接口。

## 实现与构建

tools/child-session 链接 third_party/BetterGI 中四个原始 C# 文件，沿用 RDP ActiveX 的 ConnectToChildSession、WTS查询和临时计划任务 RunEx 指定会话。来源提交与 GPL 许可见该目录 NOTICE.md/LICENSE。它只负责会话与启动，截图/OCR/游戏输入仍由 OneDragon 原生 MCP 完成。

```powershell
dotnet build tools/child-session/PlaySage.ChildSession.csproj -c Release -o runs/services/child-session/bin
powershell -NoProfile -File tools/start-child-session.ps1 -RequestElevation
```

不要覆盖正在运行的宿主输出目录；更新时构建到 bin-rN，再通过启动脚本 ReplacePid 明确指定本项目旧宿主。脚本验证路径与名称，只更换查看器，不注销子会话。管理员提示由用户手动处理。

待连接完成，把含 action 和 session_id 的 JSON 原子写入 request.json。action 接受 probe/backend/game/hide/show/switch-ww/ww-backend；先检查 status.json 和现有进程。game 在任何会话已有绝区零进程时拒绝重复启动。switch-ww 在子会话校验并关闭绝区零和 OneDragon，再启动安装的 OKWW 原生 MCP 与鸣潮；ww-backend 只启动 OKWW 后端，用于由原生框架准备游戏。计划任务是短暂启动手段，调用后删除定义，不能代替真实进程及端口校验。

鸣潮接入与当前结果见 [OKWW 实测](live-ww.md)。原绝区零进程号已失效；当前游戏/后端身份以实际 CIM、监听端口和相应 launch.json 为准。OKWW 原生 MCP 端口为23003，独立于 OneDragon23002。

本机 Child Session 无法访问原用户目录的 uv Python；.venv 的重定向器报“No Python at”。已把同一份 CPython 3.11.15 完整复制到 third_party/OneDragon/.runtime/cpython-3.11.15，启动该 python.exe 并显式加载原 .venv/Lib/site-packages。未修改原来的虚拟环境。

## 生命周期

默认保持分身查看器可见，供用户查看副会话；除非用户明确要求，不主动隐藏窗口或发送 `hide`。查看器显隐不改变游戏所在的 Windows 会话，也不授权主桌面输入。

若用户要求隐藏，隐藏查看器仍保持 RDP 连接。关闭查看器只断开连接，不注销会话；连接断开时输入保护会停止。不能把“主桌面无游戏操作”理解为“可以杀掉所有宿主进程”。

关闭 Codex/结束任务后，没有 Agent 继续规划；后端本身不会自动完成活动。后续唤醒必须重新核对会话、进程、截图和关卡，再继续。

参考：https://github.com/babalae/better-genshin-impact/tree/43eecc21bf700d3db58a174c2e66f5c90e7c69f9/BetterGenshinImpact/Service/ChildSession

## 恢复 UU 的主桌面远程

2026-11-15 本机实测：Windows 控制台保持在会话 1，Child Session 在会话 2；UU 的 `GameViewerServer.exe` 由 `GameViewerService` 启动在会话 2。副会话仍连接时，仅重启 UU 服务没有恢复主桌面。正常关闭分身查看器、确认副会话断开后，再重启 UU 服务，服务端回到会话 1。

这是临时恢复方法，不是 UU 与活动副会话并行使用的修复。当前未验证可固定 UU 主桌面目标的配置，也未验证重连副会话后仍能保持主桌面远程。不要据此承诺两者可同时使用。

### 前提条件

- 你在电脑旁，或有经过验证的独立恢复通道，能够处理管理员提示。
- 可以暂停副会话中的自动操作，并接受 UU 远程连接短暂中断。
- 只关闭本项目的分身查看器；不要注销 Windows 会话、结束游戏、停止远程桌面服务或修改系统会话注册表。

### 恢复步骤

1. 在主桌面正常关闭“PlaySage 桌面分身”查看器。此操作断开连接，不注销副会话；不要用隐藏窗口代替断开连接。
2. 在主桌面打开管理员 PowerShell，运行 `query session`。确认 `console` 仍为 `Active`，副会话已为 `Disc`。会话编号可能变化，不要照抄本次的 1 和 2。状态不符时停止，不要强制切换或注销会话。
3. 确认允许中断 UU 连接后，在同一个管理员 PowerShell 中重启已安装的 UU 服务：

   ```powershell
   Get-Service -Name GameViewerService
   Restart-Service -Name GameViewerService -ErrorAction Stop
   ```

4. 等待数秒，检查 UU 服务端所在会话：

   ```powershell
   Get-Process -Name GameViewerServer,GameViewerHealthd -ErrorAction Stop |
       Select-Object ProcessName,Id,SessionId
   ```

5. 将 `SessionId` 与步骤 2 的控制台会话核对，再用 UU 客户端重新连接并确认实际画面。找不到服务或进程、服务端仍在副会话或画面不符时，停止并记录状态，不要连续重启服务。

本次确认恢复后的 UU 服务端位于主会话，绝区零原进程仍留在已断开的副会话；没有进行 UU 客户端画面验收，也没有验证断开后的游戏运行状态。恢复后先保持分身断开。再次连接分身前需接受可能复发的风险，恢复游戏操作前需重新验证会话、后端与最新观察。
