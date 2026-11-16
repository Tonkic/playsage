# 第三方更新核查：2026-11-13

## 范围与结论

- 本机时区 UTC+08:00；线上版本快照采集于 2026-11-13 02:17:57，随后补充稳定版比较与关键文件核验。
- 阅读 README、设计文档、主依赖配置、六个独立 Git 克隆，以及实际接入脚本和历史实测记录。
- 结论：需要有选择地更新，不建议六个仓库一起拉取最新分支。
- 本次仅新增核查报告；没有拉取/检出第三方代码、升级包、改写依赖声明或锁文件，也没有启动后端或操作游戏。

## GitHub 版本核对

“分支新增”指相对本地 HEAD，当前本地所处分支的线上 HEAD 新增的提交；不是稳定版新增提交。稳定版取 GitHub releases/latest。以下比较均返回 ahead，未发现相对比较目标的本地独有提交。

| 仓库 | 本地 HEAD | 检查分支 | 上游分支 HEAD | 分支新增 | 最新稳定版 | 稳定版相对本地新增 |
| --- | --- | --- | --- | ---: | --- | ---: |
| OneDragon | cc3e80f | main | 3cbeda9 | 18 | v2.6.1 | 18 |
| OK-WW | 43ef519 | master | e04bfc3 | 37 | v3.8.0 | 37 |
| OK-EF | d80402a | master | 1e7a548 | 41 | v2.0.18 | 39 |
| SRA | d362db4 | main | b92a06e | 36 | v2.25.1 | 36 |
| BetterGI | 43eecc2 | refactor/20260930 | cc3099a | 27 | 0.67.0 | 26 |
| March7thAssistant | 4a0308e | main | 5bad271 | 28 | v2026.11.8 | 8 |

工作区状态：SRA 有未跟踪的 `starrailassistant.egg-info/`；其余五个仓库 `git status --short` 为空。六个克隆均仍是 shallow repository。干净工作区不代表忽略的配置、环境、缓存可以丢弃。

## 分项建议

### 1. OneDragon：建议优先安排受控升级

它是实际运行后端，不只是参考源码；`tools/child_session_bootstrap.py` 使用克隆的环境与源码启动 `zzz_od.backend.entry.server`。

v2.6.1 相对本地包含 OCR 匹配、低分辨率战斗识别、运行结束动作和依赖更新。88 个比较文件中未发现 MCP 路径变动，但控制器与依赖有变化，不能据此承诺实机兼容。建议固定稳定版目标，保留配置/环境回滚点，独立同步其依赖。

升级后至少验证 `tools/onedragon_step.py` 使用的 `check_game_window`、`analyze_screen`、`get_run_status`、`click_game`、`key_tap` 的名称及参数；核对 screenshot_path、1920×1080 图片、窗口/子会话身份、短按释放与停止状态。测试通过前不恢复无人值守执行。

### 2. SRA：建议更新，但先处理本项目已有兼容缺口

v2.25.1 有货币战争事件/流程及 OCR 修复。提交 `38098f75e79f01bb552412804daba7ec4c14108f` 的停止信号修复实际只修改 `tasks/zz_account_switch.py`，不能宣传为所有任务的停止保障。

比版本落后更直接的问题：

- `src/questweaver/adapters.py:100` 只接受 PNG，并在第 109 行固定使用 `.png` 后缀。
- `tools/sra_mcp.py:1` 已注明新版 SRA 返回 JPEG；正式 CLI 与开发工具存在契约分叉，升级上游不会自动修复它。
- 项目开发客户端仍使用 5000 端口；本地当前 SRA 的 `SRAServer/config.py:14` 已默认 5073。显式传入旧端口可以成立，但服务端启动参数和客户端必须匹配。
- 当前本地 SRA 已使用 `standard` extra、Python >=3.12,<3.13 和 `sra` 入口。因此发布说明里 CLI/Server 合并、端口、full→standard 的迁移不是这次版本差异新引入的全部风险。
- `sra_operator_call` 的 `parameters` 为 JSON 字符串或 null；REST `/api/operator/call` 的 `params` 为对象。不能混用。

建议先统一图像格式处理与端点配置，增加真实返回格式的契约测试，再更新并验证截图、OCR、操作结果及停止。SRA 的完整文件比较触及 GitHub 300 文件上限，本次没有宣称完成全部变更审查。

### 3. OK-WW：值得更新，但实际安装版不能被覆盖式升级

`docs/live-ww.md:8` 记录真正运行的是用户另行安装的 OKWW；v3.7.12 是 2026-11-01 的历史实测版本，不是本次重新确认的安装版本。更新 `third_party/OK-WW` 不会自动更新那个安装环境。

本项目依赖安装版的本地修改：

- `docs/live-ww.md:23`：TacetTask 两处加载等待 120→600 秒。
- `docs/live-ww-events.md:9`：TacetEliminationTask 添加 `run_simple_stage`，并修改识别及结束判断。
- `tools/okww/tacet_simple.py:17` 和 `tools/okww/tacet_resume_simple.py:18` 仍调用这个扩展方法。

上游 v3.8.0 包含角色/识别和打包更新，依赖切换到 ok-script 3.0.5b7。虽然主程序是稳定发布，其该底座依赖带 beta 标识。需要先复核实际安装版本，备份并重放本地补丁，再验证 connection.json、bearer、子会话、run_task/get_run_status/stop_task/reload_tasks 以及自定义任务接口；不能只看仓库工作区干净就覆盖安装目录。

### 4. OK-EF：按需更新，非当前紧急项

稳定版 v2.0.18 相对克隆新增 39 个提交，涉及导航资源、委托和截图适配；分支另有后续提交。`game_packs/ef/knowledge.md` 仍明确未完成实机接入。准备接入时再固定稳定版并单独验证，不因与 OK-WW 同底座而假设接口兼容。

### 5. BetterGI：本项目当前无需为已用功能更新

`tools/child-session/QuestWeaver.ChildSession.csproj:11` 开始直接链接四个上游 C# 文件，并非只用于阅读：

- BetterGenshinImpact/View/Controls/ChildSession/RdpActiveXHost.cs
- BetterGenshinImpact/Service/ChildSession/ChildSessionNativeMethods.cs
- BetterGenshinImpact/Service/ChildSession/ChildSessionEnvironmentCheck.cs
- BetterGenshinImpact/Service/ChildSession/ChildSessionConnectionFailedEventArgs.cs

逐文件将本地内容与稳定版 0.67.0、所处分支最新提交 cc3099a 对比，统一 CRLF/LF 并忽略 UTF-8 BOM 后，八项比较全部文本一致。因此当前已用四文件没有更新收益，建议保持现有固定来源。未来切换来源要同步 NOTICE，重新构建并验证子会话宿主；未在本次运行构建或实际会话测试。

### 6. March7thAssistant：低优先级，区分参考和接入

在本项目接入脚本中，查到的是 M7A-style 输入实现参考，没有找到直接运行这个克隆的证据；不能断言外部配置完全不使用它。

稳定版 v2026.11.8 相对本地新增 8 个提交；main 新增 28 个。桌面分身及暂停/恢复回执竞态修复位于后续 main，尤其 `5bad271dffa4bf3415707660c0c5e594a841bf03` 修改 utils/pause.py 并补充测试，不在这次 latest 稳定版差集中。若只是保留参考源码可按需更新；不要声称安装当前稳定版即可获得这些后续修复。

## 主项目 Python 依赖

通过 PyPI JSON 查询所有正式、未撤回且满足当前约束的版本；本次没有升级。

| 包 | 锁定版本 | 约束内最新 | 结论 |
| --- | --- | --- | --- |
| pydantic | 2.14.2 | 2.14.3 | 可单独安排补丁更新并测试 |
| ruff | 0.17.3 | 0.17.5 | 可单独安排工具更新，先记录现有 lint 基线 |
| mcp | 1.30.0 | 1.30.0 | 已是 `<2` 范围内最新；不直接放宽到 2.3.0 |
| pillow | 12.3.0 | 12.3.0 | 已是 `<13` 范围内最新；不直接放宽到 13.0.0 |
| pyyaml | 6.0.3 | 6.0.3 | 无需更新 |
| pytest | 9.2.0 | 9.2.0 | 无需更新 |

各后端依赖环境必须独立；其 MCP/Pillow 版本不同不等于主项目应一起改约束，也不单凭 SDK 主版本差就认定协议不兼容。

## 实际执行的验证

- `uv lock --check --offline`：通过。
- `uv run --frozen --no-sync pytest -q`：76 passed。
- `uv run --frozen --no-sync ruff check src tests --output-format concise`：通过。
- `uv run --frozen --no-sync ruff check .`：71 个既有问题，集中在 tools，包括未使用导入、宽泛异常捕获、异步阻塞 sleep 等。本次未顺手修改无关脚本。
- 没有安装候选版本、运行第三方测试套件、启动游戏、验证升级后的实机行为，或重新读取工作区外的 OKWW 安装内容。以上基线不能视为新版本通过验收。

## 台账维护建议

`third_party/repositories.json` 明确是四仓库的初始克隆记录，不是当前运行版本锁。README 仍按四仓库介绍，未完整登记 March7thAssistant；SRA 当前 HEAD 已不同于初始记录。后续实施升级时应保留初始来源，并另外记录当前 commit、稳定版 tag、实际运行环境、补丁和最后验证状态，避免将历史实测写成当前状态。

## 线上证据与复查方法

来源为官方 GitHub API、raw.githubusercontent.com 和 PyPI，而非搜索摘要。查询模板：

```text
https://api.github.com/repos/{owner}/{repo}/commits/{branch}
https://api.github.com/repos/{owner}/{repo}/releases/latest
https://api.github.com/repos/{owner}/{repo}/compare/{local_sha}...{upstream_sha_or_release_tag}
https://api.github.com/repos/{owner}/{repo}/commits/{specific_sha}
https://raw.githubusercontent.com/{owner}/{repo}/{sha_or_tag}/{file_path}
https://pypi.org/pypi/{package}/json
```

对应仓库：OneDragon-Anything/ZenlessZoneZero-OneDragon；ok-oldking/ok-wuthering-waves；AliceJump/ok-end-field；Shasnow/StarRailAssistant；babalae/better-genshin-impact；moesnow/March7thAssistant。

GitHub 比较接口文件列表最多返回 300 个，本次 BetterGI、SRA 达到上限；提交差数量与稳定版比较来自独立接口响应。BetterGI 四个直接引用文件另做逐文件核对，未使用截断列表推断它们未变。
