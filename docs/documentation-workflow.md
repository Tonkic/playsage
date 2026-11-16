# 准备文档同步工作流

本页说明 PlaySage 的 GitHub 文档同步流程。每次分支 push 触发一次静态文档影响检查；需要更新时，工作流创建草稿 PR，由维护者审阅并合并。该流程不执行游戏代码、不发送真实输入，也不自动合并。

## 运行入口

| 文件 | 用途 |
| --- | --- |
| [文档规范](documentation-standard.md) | 面向人类任务的写作和证据要求 |
| [TonKic 工作流](../.github/workflows/docs-sync-tonkic.yml) | 普通 GitHub Actions 的审阅与发布流程 |
| [检查程序](../tools/docs_sync.py) | push 范围、白名单、报告和本地链接检查 |
| [TonKic 调用脚本](../tools/tonkic_docs_sync.py) | OpenAI 兼容 API 请求和模型返回校验 |
| [离线回归测试](../tests/test_docs_sync.py) | 临时 Git 仓库中的范围和越界检查 |

旧的 Copilot gh-aw 源文件和 `.lock.yml` 已移除。当前流程不需要 gh-aw 编译器，也不使用 `COPILOT_GITHUB_TOKEN`。

## 配置 GitHub

在仓库 Settings 中配置以下项目：

| 类型 | 名称 | 要求 |
| --- | --- | --- |
| Secret | `TONKIC_API_KEY` | 必填。只保存 TonKic API Token，不写入代码、变量或日志 |
| Variable | `TONKIC_API_MODEL` | 必填。填写 TonKic 实际可用的模型名 |
| Variable | `TONKIC_API_BASE` | 可选。默认 `https://tonkicapi.xyz/v1`；只填写 API 根路径 |
| Variable | `PLAYSAGE_DOCS_SYNC_ENABLED` | 设为 `true` 才启用工作流 |

默认请求地址为 `https://tonkicapi.xyz/v1/chat/completions`。脚本发送 Bearer Token、`model`、`temperature: 0` 和 Chat Completions `messages`，并读取 `choices[0].message.content`。这依赖服务端提供 OpenAI 兼容接口；模型名、Token 权限和服务端响应格式必须通过一次 GitHub Actions 运行确认。

不要把普通 GitHub Token 或 TonKic Token 写入 `COPILOT_GITHUB_TOKEN`。当前流程不依赖 GitHub Copilot 订阅。

## 运行边界

1. 工作流读取完整 `before` 与 `after` SHA。新分支检查整棵当前树；普通或强推使用明确的提交范围。缺少基准对象时停止，不猜测父提交。
2. `review` job 使用 TonKic API，权限只有 `contents: read`。它只能编辑以下白名单文档，并把报告和文档放入绑定当前 SHA 的 Artifact。
3. `publish` job 重新 checkout 触发 SHA，恢复 Artifact 后运行 `tools/docs_sync.py guard`。只有守卫通过，它才使用写权限创建 `gh-aw/docs-sync/tonkic-*` 分支和草稿 PR。
4. Agent 分支被排除，避免自身循环触发；人工文档修改仍会进入检查。
5. 工作流不运行项目测试、不读取测试 CI 结果、不启动游戏。报告中的 `test_evidence` 固定为 `unavailable`，限制中必须明确项目测试和实机未验证。

允许修改的文档固定为：

```text
README.md
docs/design.md
docs/evidence-memory.md
docs/rename-playsage.md
```

检查程序还会拒绝白名单之外的文件、符号链接、删除、可执行模式、超大文档、超大补丁和失效本地链接。模型返回必须是结构化 JSON，状态只能为 `已更新` 或 `无需修改`；报告还必须包含理由、验证列表、限制列表和准确的 before/head。

## 本地检查

在 `D:\PlaySage` 执行：

```powershell
python -m py_compile tools/tonkic_docs_sync.py tools/docs_sync.py
uv run --no-sync pytest tests/test_docs_sync.py -q
uv run --no-sync pytest -q
uv run --no-sync ruff check tools/tonkic_docs_sync.py tools/docs_sync.py tests/test_docs_sync.py
uv run --no-sync python tools/docs_sync.py links --root D:\PlaySage
```

本地检查不能证明 TonKic API 可用、GitHub Secret 正确、Actions 网络可达或草稿 PR 创建成功。完成代码和文档检查后，推送触发分支并查看 Actions 日志；日志不得输出 Token。成功运行后，再记录实际模型、响应格式、范围守卫和草稿 PR 结果。

## 当前状态

本地已完成 TonKic workflow、API 调用脚本和文档边界改造。尚未完成新 workflow 的 GitHub Actions 端到端运行，因此 TonKic 的真实模型名称、Token 鉴权、API 兼容性和草稿 PR 创建仍标记为未验证。失败时工作流应保留受阻报告并停止发布，不把失败当成无需修改。
