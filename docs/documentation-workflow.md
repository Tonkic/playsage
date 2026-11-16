# 准备文档同步工作流

本页供 PlaySage 维护者在本地编译、检查并准备 GitHub 文档同步。工作流按每次分支 push 检查文档影响，有必要时提出草稿 PR，由人审阅合并。一次 push 可以包含多个提交；检查不等于必须修改文档。

> **当前状态：** 仅在 `D:\PlaySage` 准备和验证文件，尚未部署到 GitHub。未初始化项目 Git、创建远端、提交、推送或配置线上凭据。默认启用变量未设置时，工作流不激活。

## 找到维护入口

| 文件 | 用途 |
| --- | --- |
| [文档规范](documentation-standard.md) | 面向人类任务的 Microsoft 风格与证据要求 |
| [工作流源文件](../.github/workflows/docs-sync.md) | 触发器、权限、白名单、检查步骤和 Agent 指令 |
| [生成的工作流](../.github/workflows/docs-sync.lock.yml) | GitHub Actions 执行文件，只能由官方工具生成 |
| [Action 固定版本缓存](../.github/aw/actions-lock.json) | 官方编译器保存的 Action SHA 映射 |
| [检查程序](../tools/docs_sync.py) | push 范围、文档改动、报告及本地链接检查 |
| [离线回归测试](../tests/test_docs_sync.py) | 临时 Git 仓库内的范围和越界拒绝测试 |

改变工作流源文件后必须重新编译并检查生成差异。不要手工编辑 `.lock.yml`；不要用 `--fix`、关闭 strict 或忽略校验来掩盖无效配置。

## 理解运行边界

启用后的路径如下；本次没有远端运行记录。

1. GitHub 接收分支 push；排除 `gh-aw/**` Agent 分支，不排除人工文档修改。
2. 使用完整 `before` 与 `after` SHA。新分支以空树为基准检查当前树；基准对象缺失时停止，不猜成 `HEAD^`。单次原始差异超过 1 MB 时报告受阻，不截断后假装已读全。
3. 新 Agent 实例静态阅读差异、当前实现、规范和相关文档；它不需要长期会话记忆。
4. 需要修改时仅修改白名单页面。无影响时写明原因；必要事实缺失时报告受阻。
5. 后置检查程序从触发提交提取，以 `python3 -I` 运行，不导入 Agent 可修改的项目模块。检查相对触发 SHA 的已提交、暂存、未暂存和未跟踪改动、文件类型、文档大小、本地链接与报告字段。
6. 独立 safe-output job 仅在 Agent job 成功且官方威胁检查通过后运行。发布前再次核对远端源分支 SHA；发生变化或无法查询时拒绝本次发布。
7. 官方处理器对实际发布补丁再次实施逐文件白名单和保护策略，最多创建一个草稿 PR；不自动合并，不直接写目标分支。

同一分支使用 `cancel-in-progress: false` 和 `queue: max` 排队，不让新 push 取消正在运行的检查。排队期间已过时的结果仍只能描述其原始 SHA，不能验收新的提交。

Agent 生成分支不触发自身。人工合并文档 PR 后，目标分支的 push 仍可检查；已同步且无新影响时应报告无需修改。不要使用忽略全部 `docs/**` 的办法防循环。

## 核对权限与写入范围

Agent job 只授予 `contents: read`，不提供仓库写 token。PR 发布由独立 safe-output job 执行。自动创建诊断 issue、无变化 issue、失败报告 issue 和激活评论均已关闭。

**编译器边界：** v1.2.2 仍为官方 `conclusion` 收尾 job 生成 `contents/issues/pull-requests: write`；源配置中的同名 job 权限覆盖不会缩减它，因此本项目不保留这种无效配置，也不声称整个 workflow 只有一个写权限 job。已检查生成的收尾步骤为官方报告与用量处理，不包含本项目的 PR 发布步骤；这些权限并未交给 AI Agent。部署前仍需审阅固定版本的官方运行代码和组织策略，不能仅凭本地编译确认远端安全。

实际可发布文件是固定白名单：

```text
README.md
docs/design.md
docs/evidence-memory.md
docs/rename-playsage.md
```

其他文件即使是 Markdown 也不允许。`protected-files` 使用 `blocked`，只为根 README 添加明确例外；白名单仍独立生效。发布补丁最多 4 个文件、100 KB；本地检查使用更保守的 100,000 字节补丁上限，每篇文档不超过 120,000 字节，并拒绝删除、符号链接及可执行文件。

以下内容不在白名单：源码、测试、依赖锁、`AGENTS.md`、文档规范、本页、workflow、检查程序、活动包、游戏知识包、历史实测报告、批准方案、配置和运行数据。需要修改这些内容时，Agent 必须交给维护者，不得自己放宽规则。

白名单限制的是**发布内容**，不是操作系统级的临时工作区写保护。后置链接检查检查的是 Agent 结束时的工作区，不能独立证明每个已暂存 safe-output 候选的全文完全一致。官方发布层仍会检查候选补丁的路径；人工必须核对实际 PR diff、报告与源码。当前不把这些机制宣称为对文档语义或全部运行路径的实机安全验收。

## 查看运行结果

报告包含四项：

```text
检查范围：完整 before → 完整 head
文档结果：已更新 / 无需修改 / 受阻
修改说明：页面与行为的对应关系，或不修改的理由
验证与限制：实际检查、未验证内容和人工确认事项
```

Agent 将结构化报告保存为 `/tmp/gh-aw/docs-sync-report.json`；可信检查把摘要写入 GitHub Actions step summary。无需修改时使用只记录日志的 `noop`，不创建空 PR。受阻时保留报告并使检查失败，不发布文档。

工作流**不执行项目测试，也不查询测试 CI 结果**。`test_evidence` 固定为 `unavailable`，限制中必须出现“未验证”。测试源码只用于理解覆盖意图，不能证明通过；历史 158 passed 等结果不能作为本次 SHA 的证据。若文档结论必须依赖缺失的验证，选择受阻而不是猜测。未来接入 CI 证据需要单独审阅 SHA 匹配、来源及权限。

## 在本地编译

### 前提条件

- 已安装 GitHub CLI、Git，以及项目锁定的 Python 开发环境。
- 允许读取 GitHub 官方发布和 Action 元数据；编译不需要创建项目远端。
- 使用官方 **gh-aw v1.2.2**。本轮从官方 release 下载 Windows amd64 二进制到会话 scratch，校验 SHA-256 后使用，没有安装全局扩展。

官方 Windows amd64 二进制 SHA-256：

```text
5ed67185ce18c9b4c2bc6ea16f5ec914773fae12ac18782b59028c7c8605ae91
```

### 操作步骤

1. 若尚未安装扩展，可在确认后安装固定版本。本轮未执行此安装命令。

   ```powershell
   gh extension install github/gh-aw --pin v1.2.2
   gh aw version
   ```

   已安装其他版本时先核对版本，不盲目执行 upgrade。也可以使用已校验的独立 `gh-aw.exe`，把后续命令的 `gh aw` 替换为其调用路径。

2. 在项目根目录编译并检查官方 schema 与 Action 引用。

   ```powershell
   cd D:\PlaySage
   gh aw compile docs-sync --strict --validate --no-check-update
   ```

3. 执行离线检查。若目录刚移动，先按[移动后的环境检查](rename-playsage.md#检查目录移动后的环境)修复实际失效的入口。不要重建整个环境或升级依赖。

   ```powershell
   uv run --no-sync pytest tests/test_docs_sync.py -q
   uv run --no-sync pytest -q
   uv run --no-sync ruff check src tests tools/onedragon_step.py tools/docs_sync.py
   uv run --no-sync python tools/docs_sync.py links
   uv run --no-sync ruff check .
   ```

   测试只在临时目录建立 Git fixture，不初始化项目 Git、不访问远端、不启动游戏。全仓 lint 的历史问题应与新增问题分别报告。

### 预期结果

官方编译返回成功，产生 `.github/workflows/docs-sync.lock.yml` 和 Action 固定版本缓存。回归测试及相关 lint 通过，本地链接检查返回 `status: ok`。修改源文件后重新编译；生成文件不是手写替代品。

`--validate` 不等于 GitHub 实际运行。Docker 不可用时容器镜像验证可能被官方工具跳过；本轮不把编译成功写成 Docker、AI 推理、PR 发布或游戏验收成功。

## 处理检查失败

| 情况 | 处理方式 |
| --- | --- |
| 找不到 `before` 提交 | 检查强推后的历史可达性；保留受阻报告，不改用父提交猜测范围 |
| 差异超过预算 | 人工拆分检查范围；不要截断差异或提高权限绕过 |
| 白名单以外的文档需要更新 | 由维护者审阅并另行修改；Agent 不改自己的白名单 |
| 报告缺少 SHA、理由或未验证说明 | 补充真实事实后重新运行，不填虚假测试通过记录 |
| 目标分支已更新 | 旧报告仅保留为历史；由新 push 重新检查 |
| 权限或模型凭据不可用 | 检查 GitHub 设置与授权，停止发布；不把个人高权限 token 注入 Agent |
| PR 没有自动触发 CI | 不推空提交；核对 token 触发限制，人工审阅并执行获授权的验证 |

## 将来部署前确认

本节是部署条件清单，不是本轮已执行的操作。

- 先确认项目远端、上传范围、可见性和发布授权。不要直接上传整个本机目录；其中包含第三方克隆、运行证据和本地状态。
- 审阅并发布源 workflow、官方生成 lock、Action 固定缓存、规范及检查程序。固定 gh-aw 版本，升级后重新编译和检查。
- 当前使用 Copilot 引擎的个人凭据路径，需要符合官方要求的 `COPILOT_GITHUB_TOKEN` 及有效的模型使用权限。凭据仅放入 GitHub Secrets，不写入文件或日志；不要给引擎凭据附加不必要的仓库写权限。
- 仓库需允许 GitHub Actions 创建 PR，且官方 Actions、运行器和所需网络可用。组织策略可能进一步限制这些权限。
- 仅在完成部署审阅后设置仓库变量 `PLAYSAGE_DOCS_SYNC_ENABLED=true`。本轮未设置该变量，也未创建 Secrets。
- 配置分支保护与人工审阅要求，不启用自动合并。使用默认 `GITHUB_TOKEN` 创建的 PR 通常不会自动触发其他 CI；不要假设已有 required checks 会运行。
- 在授权的测试仓库验证普通/多提交 push、新分支、强推缺历史、无影响、缺证据、越界拒绝、Agent 分支防循环和并发队列。本地 fixture 不能替代此端到端验证。

## 本地验证记录

以下结果对应本轮 `D:\PlaySage` 的本地工作区快照，不是远端提交验收。已修复本地可编辑安装与 pytest 启动器的旧路径引用，未重建环境。

| 检查 | 实际结果 |
| --- | --- |
| 官方编译器 | v1.2.2 Windows amd64，与官方 release 的 SHA-256 一致 |
| Workflow 编译 | `compile docs-sync --strict --validate --no-check-update` 成功，0 warnings；重复编译的 lock 文件逐字节一致 |
| 全量离线测试 | 209 passed；包含 51 个新增文档同步用例，Git fixture 位于会话 scratch |
| 核心与新增代码 lint | `ruff check src tests tools/onedragon_step.py tools/docs_sync.py` 通过 |
| 全仓 lint | 71 项既有问题，新增 0 项；这些问题所在的历史工具文件哈希未变 |
| 文档链接 | 6 份页面中的 46 个本地链接与标题锚点通过 |
| PowerShell 示例 | 7 份本轮文档中的 35 个代码块语法解析通过；未执行示例中的游戏或服务操作 |
| 依赖与环境 | `pyproject.toml` 和 `uv.lock` 哈希不变；41 个已安装包兼容，`PyDirectInput 1.0.4` 保留 |
| 改动范围 | 165 个既有文件中只改动 5 份预期文档，160 个不变；26 个活动包文件全部不变。另新增 7 个本任务文件 |
| 项目发布状态 | 根目录仍无 `.git`；没有创建远端、提交、推送、配置 Secrets 或启用变量 |

新增回归覆盖多提交 push、新分支、强推、缺失基准、人工文档修改、防循环、越界文件、删除及可执行模式、暂存区改动被工作区恢复掩盖、无文档影响、缺测试证据、过期 SHA、发布查询失败及生成文件中的失败关卡。

尚未验证：GitHub 端到端运行、模型推理、网络沙箱、Docker 镜像运行和实际 PR 创建。官方收尾 job 的额外权限、实际候选内容与报告的一致性及 PR 的语义正确性仍需部署前和合并前审阅。本轮没有启动游戏、发送真实输入或动态执行活动包 Python。

## 官方依据

本轮读取了官方 **v1.2.2** 的 schema、触发器、并发、引擎和 safe-output 文档。它们是配置依据，不是本项目远端运行证据。

- [v1.2.2 发布](https://github.com/github/gh-aw/releases/tag/v1.2.2)
- [固定版本的 workflow schema](https://github.com/github/gh-aw/blob/v1.2.2/pkg/parser/schemas/main_workflow_schema.json)
- [触发器](https://github.github.com/gh-aw/reference/triggers/)
- [并发与队列](https://github.github.com/gh-aw/reference/concurrency/)
- [Safe outputs](https://github.github.com/gh-aw/reference/safe-outputs/)
- [PR 写入范围](https://github.github.com/gh-aw/reference/safe-outputs-pull-requests/)
- [编译流程](https://github.github.com/gh-aw/reference/compilation-process/)
