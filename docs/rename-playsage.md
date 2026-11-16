# 改用 PlaySage 名称

项目已由 QuestWeaver 更名为 **PlaySage**。当前发行包、主命令、实际实现、项目技能和桌面分身均使用新名称。旧命令及导入只作兼容转发；历史证据、活动包摘要和第三方来源保持不变。

## 使用新命令

当前项目目录为 `D:\PlaySage`，由用户在品牌改名后移动。以下步骤使用新位置；若安装在别处，替换为实际路径。产品改名本身不迁移运行数据。

1. 同步锁定依赖并安装新入口。使用 `--inexact` 保留环境中另行安装的开发工具依赖。

   ```powershell
   cd D:\PlaySage
   uv sync --locked --inexact
   ```

2. 检查新入口。以下命令不启动游戏或输入后端。

   ```powershell
   uv run playsage --help
   uv run playsage doctor
   uv run python -m playsage --help
   ```

3. 将日常使用命令中的 `uv run questweaver` 改为 `uv run playsage`。原有参数、退出码和数据格式不变。

   ```powershell
   uv run playsage evidence history --limit 20
   uv run playsage memory show zzz.cyber-healer
   uv run playsage model validate-grid --help
   ```

旧 `questweaver` 命令和 `python -m questweaver` 继续可用，两者调用同一实现，不会生成第二套活动记忆或改变执行权限。不存在必须一次性重写所有脚本的要求。

## 已改名的内容

| 内容 | 新名称或行为 |
| --- | --- |
| 产品名称、README、架构说明 | PlaySage |
| Python 发行包 | `playsage`，版本仍为 `0.1.0` |
| 主 CLI | `playsage` |
| Python 模块启动入口 | `python -m playsage` |
| 实际实现与入口 | `src/playsage/`、`playsage.cli:main`、`playsage.models` 等 |
| 帮助文本和 doctor 建议 | 显示 PlaySage 与 `playsage` 命令 |
| 项目技能目录与 ID | `playsage-event`、`playsage-skill-author` |
| 桌面分身项目、程序和窗口 | `PlaySage.ChildSession.csproj`、`PlaySage.ChildSession.exe`、PlaySage 桌面分身 |
| 临时计划任务 | `PlaySage-ChildSession-` 前缀，作者 PlaySage |
| 会话环境变量 | `PLAYSAGE_CHILD_SESSION_ID`，新值优先；缺少时才读取旧变量 |
| 活跃工具 | 使用 `playsage.*` 导入、新项目路径和 `playsage_` 截图前缀 |
| 第三方依赖与版本 | 本轮不升级、不改上游来源 |

`src/playsage/` 持有唯一实现。`src/questweaver/` 仅保留兼容初始化与模块入口，把旧导入绑定到相同模块对象；不会复制模型类、锁、索引或工作记忆。

## 保留的兼容标识

以下旧名不是遗漏，不应做全仓文本替换。

| 保留项 | 原因 |
| --- | --- |
| `questweaver` 命令及导入 | 兼容旧脚本和活动包，实际执行 `playsage` 模块 |
| 历史记录中的 `D:\QuestWeaver` | 保留采集时的来源；当前工具不再向此目录输出 |
| 旧进程名识别 | 启动脚本仅用它识别并安全替换旧查看器，不再构建旧名称程序 |
| `QUESTWEAVER_CHILD_SESSION_ID` | 读取回退；启动时同时导出旧值供已安装任务过渡，不取消会话身份校验 |
| `data/`、`runs/`、锁目录与锁键 | 不拆分互斥域，不移动记忆、索引或证据 |
| 活动包正文、历史报告和批准方案中的旧名 | 所有包内文件参与摘要；仅为品牌替换会改变摘要并破坏既有证据关联。历史材料按原样保存 |
| 上游名称、地址和许可证 | 第三方框架不是本项目，不能随本项目改名 |

活动包 ID、包文件摘要和 registry 生命周期不因本次改名而变化。旧包中的旧命令仍能使用，也不会因此被提升为 `verified`。

## 更新已有安装与查看器

项目技能目录已改为 `.agents/skills/playsage-event` 与 `.agents/skills/playsage-skill-author`。重新加载项目技能后使用新 ID；当前会话已经载入的技能列表和仓库外安装副本不会随文件改名自动刷新。

不要覆盖正在运行的查看器目录。构建到独立输出目录，再按[桌面分身说明](child-session.md)核对真实进程与会话，用启动脚本显式指定旧 PID：

```powershell
dotnet build tools/child-session/PlaySage.ChildSession.csproj -c Release -o runs/services/child-session/bin-playsage
powershell -NoProfile -File tools/start-child-session.ps1 -BuildDirectory bin-playsage -ReplacePid OLD_PID -RequestElevation
```

`OLD_PID` 必须替换为已核验的本项目查看器 PID。替换只断开并重连查看器，不注销游戏会话；输入必须等待新连接和实时身份核验后恢复。管理员提示由用户处理。

本轮本地工作区快照验证：

- `uv run --no-sync python -m pytest -q`：264 passed、188 skipped，包含文档链接检查；跳过项不是通过项。
- `src`、`tests` 及本轮关键连接/退出工具的 Ruff 检查通过；全仓 Ruff 仍报告 70 项工具问题，未扩大清理范围。
- 两份修改后的 PowerShell 启动脚本语法解析通过。
- 新分身项目构建成功，0 错误；上游 BetterGI 原文件保留一项 CS8604 警告。
- wheel 离线构建成功；核对全部实现位于 `playsage/`，旧包只含两个兼容入口，解包后的新旧 CLI 在隔离导入路径下通过帮助检查，未打包运行数据或第三方源码。
- 新 `PlaySage.ChildSession` 查看器已实际替换旧进程并连接会话 2；OneDragon 后端所属会话与 23002 监听端口已实时核验。安装版退出扩展已更新并校验写入内容。

这些结果不代表游戏活动完成；本轮未重新启动鸣潮、未通过新变量路径执行游戏退出，也未继续绝区零关卡。已载入的技能目录和仓库外技能副本需重新加载或单独更新。

## GitHub 核查结果

以下是目录移动前在 `D:\QuestWeaver` 完成的历史只读核查，不表示再次核查了当前账号的全部仓库：

- 工作区 `D:\QuestWeaver` 没有根 `.git`；Git 命令确认它不是 Git 仓库，因此没有可在此处更新的本地 `origin`。
- GitHub CLI 当前账号为 `Tonkic`。直接查询 `Tonkic/QuestWeaver` 与 `Tonkic/PlaySage` 均未找到仓库。
- 列出该账号下返回的 16 个仓库，名称或描述均未包含 QuestWeaver 或 PlaySage。
- 在项目工具、游戏知识包、活动包及项目技能的检索范围内，未找到项目自己的 GitHub 地址；检出的上游链接保持不变。

**结论：在已核查范围内，没有现有项目仓库需要改名。** 本次没有创建仓库、设置 remote、提交或推送文件，也没有修改第三方仓库。

这不排除项目位于其他账号、组织或使用无关名称的仓库。若另有仓库地址，需要先核对归属及内容，再决定是否改名。未来发布时可以使用 `PlaySage` 作为仓库名，但发布、可见性与上传内容需另行确定；不要把整个本机目录直接上传，其中可能包含运行证据、本地状态和第三方克隆。

## 早期改名验证记录（历史）

改名测试覆盖新旧 console 命令与 `python -m` 入口、帮助品牌、只读 doctor、同一活动记忆的互相读取，以及包摘要不变。完整离线流程分别通过 `playsage` 与 `questweaver` 运行。

以下检查均在目录移动前完成，不能作为移动后环境或新增 workflow 的验收结果：

| 检查 | 实际结果 |
| --- | --- |
| 全量离线测试 | `uv run --locked pytest -q`：158 passed |
| 核心及本轮相关工具 Lint | `uv run --locked ruff check src tests tools/onedragon_step.py`：通过 |
| 全仓 Lint 基线 | 仍有 71 项既有问题；与改名前逐项比较，新增 0 项 |
| 依赖锁 | 39 个第三方包的版本、来源、哈希及元数据完全不变；本地项目仅改名 |
| 环境兼容性 | `uv pip check`：41 个已安装包兼容；PyDirectInput 保持 1.0.4 |
| wheel | 离线构建成功；逐文件核对新旧命名空间及两个 console 入口，不含运行数据或第三方克隆 |
| 改动边界 | 核对 68 个基线文件：11 个预期修改、57 个不变；其中 26 个活动包文件不变 |
| 文档 | 7 份文件、31 个本地链接、3 个 JSON 示例、43 条 CLI 参数检查通过；31 段 PowerShell 仅做语法解析，均通过 |

早期仅增加三个 `src/playsage/` 入口模块、`tests/test_branding.py` 和本说明，当时未迁移内部实现。以下旧范围说明仅记录该阶段，不代表当前实现仍位于旧包。测试只在临时目录运行模拟和离线操作，不采集真实画面、不发送输入。

> **注意：** 首次执行精确的 `uv sync --locked --offline` 时，工具移除了环境中额外安装的 `PyDirectInput 1.0.4`。随后已从缓存恢复同一版本，`uv pip check` 通过。本文使用 `--inexact`，避免后续同步清理这种额外依赖；它不放宽锁定依赖的版本约束。

当前内部实现与 Windows 分身源码已改名；此处保留早期验收结果用于追溯，不能把品牌改名测试当作游戏实机验证。

## 检查目录移动后的环境

以下保留目录移动后的历史修复记录，不代表本轮重新执行了依赖重装。

目录移动后，可编辑安装的 `.pth` 与 Windows 命令启动器可能仍引用旧绝对路径。本轮在 `D:\PlaySage` 重现了 `ModuleNotFoundError: No module named 'playsage'` 和 `uv trampoline failed to canonicalize script path`；第三方包兼容检查仍通过。

本轮只定向重装发生故障的本地包和 pytest，使用现有缓存与锁文件，没有重建虚拟环境或升级第三方版本：

```powershell
cd D:\PlaySage
uv sync --locked --inexact --offline --reinstall-package playsage --reinstall-package pytest
uv run --no-sync playsage --help
uv run --no-sync questweaver --help
uv run --no-sync python -m playsage --help
uv run --no-sync pytest --version
uv pip check
```

新旧 console 入口、模块入口和 pytest 入口已重新检查。41 个已安装包兼容，额外安装的 `PyDirectInput 1.0.4` 保留。`--offline` 要求缓存齐全；若缺包，停止并检查缓存，不使用无锁升级替代。其他工具或服务的旧路径未据此宣称全部修复。

此修复不更改活动包、历史证据、用户配置或运行数据；未启动游戏或会话服务。目录移动后的项目测试及文档工作流检查见[本地验证记录](documentation-workflow.md#本地验证记录)。

## 相关内容

- [项目入门](../README.md)
- [架构与执行边界](design.md)
- [证据、记忆和网格验证](evidence-memory.md)
- [项目开发约定](../AGENTS.md)
