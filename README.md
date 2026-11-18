# PlaySage

PlaySage 帮助 Agent 查找游戏活动知识、回看操作证据、保存工作进度，并验证明确的网格规则。它使用现有 MCP 后端提供截图、原生识别和输入，不重新实现游戏自动化底层。

当前版本为 **0.1.0 开发原型**。已提供活动包管理、SQLite 索引、离线分析、受控模拟执行、SRA 只读连接，以及独立的 OneDragon 实机开发工具。

项目原名 QuestWeaver。主命令与内部实现均为 `playsage`，桌面分身为 `PlaySage.ChildSession`。旧 `questweaver` 命令及导入仅作兼容转发。当前工作区为 `D:\PlaySage`；历史证据中的旧路径不重写。升级和目录移动说明见[改名与兼容说明](docs/rename-playsage.md)。

> **重要：** 通用 CLI 尚未开放真实活动包重放。历史截图、模拟成功和离线规则匹配都不能授予 `verified` 或无人值守执行权限。

## 选择你的任务

| 你要完成的任务 | 阅读内容 |
| --- | --- |
| 安装项目并运行模拟示例 | 本页“运行离线示例” |
| 理解组件、数据流和执行限制 | [架构与执行边界](docs/design.md) |
| 导入截图、恢复记忆或检查网格规则 | [证据、记忆与离线验证](docs/evidence-memory.md) |
| 记录 GameScaling-S3 RSI 离线轨迹或评估 | [GameScaling-S3 RSI 离线原型](docs/gamescaling-rsi.md) |
| 查看历史实机结果 | [后台实测报告](docs/live-background.md)、[第一案报告](docs/live-case1.md)、[鸣潮报告](docs/live-ww.md) |
| 配置独立 Windows 会话 | [后台桌面分身](docs/child-session.md) |
| 核对第三方源码和环境 | [第三方项目说明](third_party/README.md) |
| 核对 OKWW 补丁、离线测试或回滚 | [拖拽修复](docs/okww-input-repair.md)、[输入失败与断联排查](docs/okww-input-reliability.md)、[重复寻敌与计时修复](docs/okww-timeout-repair.md) |
| 收到反作弊踢出或封禁提示 | [暂停自动任务与人工核查](docs/okww-safety-stop.md) |
| 通过原生 MCP 退出鸣潮 | [OKWW 退出接口](docs/okww-exit-mcp.md) |
| 维护文档或准备 GitHub 文档同步 | [文档规范](docs/documentation-standard.md)、[工作流准备与验证](docs/documentation-workflow.md) |

## 运行离线示例

此流程只运行内置模拟策略，不启动游戏或连接真实输入后端。

### 前提条件

- 使用 PowerShell，安装 Python 3.11 或更高版本及 `uv`。
- 将项目放在 `D:\PlaySage`，或把示例路径替换为实际位置。
- 首次同步依赖时允许访问依赖源。

### 操作步骤

1. 进入项目目录并同步锁定的依赖。

   ```powershell
   cd D:\PlaySage
   uv sync --locked --inexact
   ```

2. 检查项目状态并建立活动索引。

   ```powershell
   uv run playsage doctor
   uv run playsage index
   ```

3. 查找与模拟环境匹配的活动。

   ```powershell
   uv run playsage search "示例" --game hsr --backend mock --game-version simulated --resolution 1920 1080
   ```

4. 运行两次示例，查看重新进入场景后的复用记录。

   ```powershell
   uv run playsage demo
   uv run playsage demo
   uv run playsage history hsr.example-event
   ```

### 预期结果

每次 `demo` 都从模拟菜单重新开始，执行内置的 `playsage.demo.start_challenge`，完成一次模拟点击，再独立检查目标。程序保存 JSONL 日志和 SQLite 运行记录，活动索引仍为 `candidate`，不会动态加载活动包 Python。

命令输出 JSON。一般失败返回退出码 1，Ctrl+C 返回 130；命令参数错误由解析器报告。若在其他目录调用，将 `--root D:\PlaySage` 放在子命令之前。

## 查看已有证据和记忆

以下命令只访问本地数据，不连接游戏后端。活动记忆命令要求对应活动包已存在。

```powershell
uv run playsage evidence history --limit 20
uv run playsage evidence stats
uv run playsage memory show zzz.cyber-healer
uv run playsage model validate-grid --help
```

完整流程见[证据、记忆与离线验证](docs/evidence-memory.md)。`inspect` 返回原图或裁剪文件路径，调用方仍需打开图像查看；文件已保存不等于 Agent 已看到画面。

## 创建活动包

新包包含规则记录、`SKILL.md` 和不执行动作的 Python 草稿。创建包不会使它获得执行权限。

1. 创建草稿并校验包结构。

   ```powershell
   uv run playsage new hsr my-event --name "我的活动"
   uv run playsage validate event_packs/hsr/my-event
   ```

2. 建立索引并查看活动信息。

   ```powershell
   uv run playsage index
   uv run playsage show hsr.my-event
   ```

3. 需要主动使包失效时，运行以下命令。

   ```powershell
   uv run playsage stale hsr.my-event
   ```

新包为 `draft`。已索引包的文件发生变化后，再次索引会标记为 `stale`；重新索引不会清除已有失效状态。未知版本禁止自动重放，YAML 中声明 `verified` 也不能授予权限。详见[活动包生命周期](docs/design.md#活动包生命周期)。

## 当前能力

| 能力 | 已实现范围 | 主要限制 |
| --- | --- | --- |
| 活动包 | 严格 YAML 契约、入口一致性、路径边界和文件哈希 | 通用活动包执行尚未开放 |
| 索引与选择 | SQLite、中文搜索、运行历史、删除清理、兼容性和失效状态 | 不提供 `verified` 晋升 |
| 受控执行 | 窗口锁、观察时效、动作预算、超时停止、独立结果验证 | 通用流程只运行内置模拟策略 |
| 证据回看 | 原图字节与哈希、前后关联、裁剪、像素、差异、容量与清理预览 | 不自动删除，不推断目标完成 |
| 活动工作记忆 | 包外 JSON、证据引用、版本隔离、修订冲突检测和导出 | 不自动合并，不授权真实重放 |
| 网格离线回测 | 规则单步预测与历史标注比较 | 不自动提取棋盘，不等于视觉验真 |
| GameScaling-S3 RSI | JSONL 轨迹、难例筛选、人工接管和 Champion/Challenger 离线评估 | 不采集画面、不发送输入、不训练或修改权重 |
| SRA | 工具探测、内联 PNG/JPEG 读取与保存 | 只读，尚未接入输入 |
| OneDragon | 原生截图/OCR、受保护单步操作、网格开发工具 | 独立开发入口，非通用适配器 |
| 知识与技能 | 四游戏知识包、活动探索和活动包编写技能 | 未验证的后端不能视为可运行 |

## HSR 遗器离线筛选

崩铁模块现在包含从 March7thAssistant RelicForge 开发分支迁移的遗器评分库与 pinned 数据。`playsage.hsr_relics` 可以读取 Reliquary JSON 导出，按角色构筑配置计算遗器当前分数和强化后的预期分数。

- 代码位于 `src/playsage/hsr_relics/`。
- 遗器数据库和来源清单位于 `data/hsr/relic_database/`。
- 角色评分配置和本地覆盖位于 `game_packs/hsr/relic_scoring/`，本地策略写入 `relic_scoring.overrides.yaml`。
- 这项能力只做离线分析，不采集游戏数据、不发送输入、不强化、锁定或弃置遗器，也不授予无人值守执行权限。

运行迁移回归测试：

```powershell
uv run pytest tests/test_hsr_relics.py
```

## 连接 SRA 只读服务

此流程会连接本机服务并获取真实截图，但不会发送按键或点击。

### 前提条件

按 [SRA 官方文档](https://starrailassistant.top/server/mcp/) 独立安装并启动 SRA-server 与游戏。确认服务端口，不要把客户端默认值当作服务端实际配置。

### 操作步骤

1. 探测服务提供的工具。以下示例使用 SRA 2.25.x 默认服务端口 5073。

   ```powershell
   uv run playsage sra probe --url http://127.0.0.1:5073/mcp
   ```

2. 获取并保存观察。

   ```powershell
   uv run playsage sra observe --url http://127.0.0.1:5073/mcp
   ```

3. 打开返回的图片路径，确认截图内容和游戏窗口。

客户端默认端点为 `http://127.0.0.1:5000/mcp`，只允许本机回环地址；使用 `--url` 匹配实际服务，也可设置 `--timeout 30`。`probe` 返回真实的 `tools/list` 和输入 schema。`observe` 校验内联 PNG/JPEG，按实际格式保存原始字节及 `observation.json`；仅有路径而没有图像数据的结果不会作为图片证据。

SRA 的 OCR 返回结构、窗口身份、按键释放和停止行为仍需实机核验。[MaaMCP](https://github.com/MAA-AI/MaaMCP) 是后续可选执行器，当前未执行其 Pipeline。

## 使用独立实机开发工具

> **警告：** 本节涉及服务启动、权限提升和真实游戏观察，不属于离线入门流程。实际操作前需另行确认，并按[后台桌面分身说明](docs/child-session.md)核对会话、进程、端口与窗口。权限提示由用户手动处理，服务已运行时不要重复启动。

> **UU 远程用户：** 本机已复现活动副会话使 UU 服务端运行在副桌面的情况。只有 UU 访问通道时不要无人值守启动或重连分身；临时恢复步骤及未解决的并行使用限制见[后台桌面分身](docs/child-session.md#恢复-uu-的主桌面远程)。

第三方源码位于 `third_party/OneDragon`、`third_party/OK-WW`、`third_party/OK-EF` 和 `third_party/SRA`，各自为独立 Git 克隆。运行环境和当前版本以[第三方项目说明](third_party/README.md)为准；源码存在不代表后端已经验证可运行。

1. 按桌面分身说明构建并启动会话服务。

   ```powershell
   dotnet build tools/child-session/PlaySage.ChildSession.csproj -c Release -o runs/services/child-session/bin
   powershell -NoProfile -File tools/start-child-session.ps1 -RequestElevation
   ```

2. 在已连接的分身内启动后端和游戏，再检查连接并采集观察。

   ```powershell
   uv run python tools/inspect_onedragon.py
   uv run python tools/onedragon_step.py observe
   ```

3. 打开实际 PNG，检查窗口和目标。后续单步操作必须引用对应的最新 `observation.json`，不能使用历史归档帧替代。

当前 OneDragon 开发连接使用经过进程、会话和端口校验的 23002 端点。工具检查分身内前台、窗口几何、观察时效、场景和点击区域变化。窗口锁只约束遵守锁协议的调用方，不能阻止独立 MCP 或用户输入。

`tools/repair_grid.py` 使用人工确认的棋盘、现有求解器和原生 MCP。每步保存截图与日志，结束返回 `needs_visual_review`，必须独立查看游戏结果。

`onedragon_step.py` 支持可选的 `--run-id`、`--event-id`、`--package-digest`、`--game-version`、`--expected` 和 `--capacity-bytes`。输入意图先落盘；派发前重新检查时效和预算；后置故障明确报告“输入可能已发生”，不自动重试。新增记录链路尚未重新实机验收。

## 查看历史实测结果

以下是已有实测记录，不表示当前版本已经完成回放验收，也不代表本次文档更新执行过游戏操作。

- **绝区零：**「赛博圣手，出诊！」前四案完成 16/20 关，奖励全部领取，累计 240 菲林。第二至第四案在隐藏的独立 Windows 会话 2 中完成。第五案在当时尚未开放，用户选择手动继续，未设置自动唤醒。尚无完整回放验证。
- **鸣潮：** 使用本机安装的 OKWW 原生 MCP 完成每日，活跃度 110，五档奖励全部领取；无音清剿消耗 240 波片。操作使用隐藏会话 2，梦魇附加项加载超时后跳过。详见[鸣潮实测](docs/live-ww.md)。

相关证据见[后台实测报告](docs/live-background.md)、[第一案报告](docs/live-case1.md)和[活动规则](event_packs/zzz/cyber-healer/SKILL.md)。SRA 与 OK-EF 尚未完成输入接入。

## 验证项目

在项目根目录运行以下命令。

```powershell
uv run pytest
uv run ruff check src tests
uv run ruff check tools/onedragon_step.py
uv run ruff check .
```

测试覆盖包校验、索引事务、兼容性拒绝、资源变化、跨进程锁、观察过期、动作预算、超时停止、伪成功、图像处理、证据故障、记忆隔离和网格离线回测。全仓 Ruff 的历史工具问题与本次新增问题应分别报告，不把旧问题误报为已修复。

OKWW 安装版的输入回归需显式设置 `OKWW_WORKING_DIR`，默认跳过，不发送真实输入。测试入口、补丁范围与分层回滚方法见[拖拽修复](docs/okww-input-repair.md)和[输入失败与断联排查](docs/okww-input-reliability.md)；离线通过不等于游戏实测通过或反作弊误判率降低。

收到反作弊告警后，本工作区已启用 OKWW [持久安全暂停](docs/okww-safety-stop.md)：`tools/okww_mcp.py` 在暂停标记存在时拒绝新的 `run_task`，不会按 24 小时计时恢复。该保护不能停止已运行的原生任务或控制其他客户端；旧的自动关闭踢出弹窗工具已改为留证后报错，不再自动继续。

## 维护项目文档

每轮改动都按[文档规范](docs/documentation-standard.md)检查影响；无需修改时记录理由，证据不足时明确标记未验证。

文档同步工作流位于 `.github/workflows/docs-sync-tonkic.yml`，由普通 GitHub Actions 调用 TonKic 的 OpenAI 兼容接口 `https://tonkicapi.xyz/v1/chat/completions`。模型审阅只返回白名单文档的完整文本，独立发布 job 经过静态守卫后创建草稿 PR，由人审阅合并；不直接写目标分支。配置方式、权限边界和验证记录见[工作流准备与验证](docs/documentation-workflow.md)。

项目不打包上游框架，不修改用户全局 Codex 配置，不绕过反作弊。第三方依赖按各自的安装和许可要求独立管理。
