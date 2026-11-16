# 回看证据、维护活动记忆和验证网格规则

使用本页流程，你可以导入已有观察、检查原始画面、恢复活动工作进度，并比较网格规则预测与观测标注。所有新 CLI 命令都只操作本地文件，不连接 MCP、不启动游戏、不发送真实输入。

本功能借鉴视觉历史、文件化活动记忆和按需规则建模思路，不移植论文框架，也不宣称复现论文成绩。组件关系见[架构与执行边界](design.md)。

> **重要：** 历史证据只能用于分析。记忆标为 `supported` 或回测返回 `match`，都不能授予 `verified`、替代实时观察或授权真实重放。

## 前提条件

- 已按[项目入门说明](../README.md)同步依赖，并在项目根目录打开 PowerShell。
- 导入源是已有的 `runs/onedragon/` 或 `runs/observations/` 观察记录。截图位于该记录目录内。
- 使用活动记忆前，对应的 `event_packs/<game>/<slug>/` 已存在且校验通过。
- 写入记忆或运行回测前，准备项目目录内的 UTF-8 JSON 文件。使用无 BOM 编码。
- 将示例中 `<...>` 占位值替换为真实值；不要把示例版本、包摘要或状态当成采集事实。

若从其他目录调用，把 `--root D:\PlaySage` 放在子命令之前。记忆和回测 JSON 的相对路径按项目根目录解析，不能指向项目外部。历史观察中的旧来源路径保持原样，不因目录移动重写证据。

## 导入并回看观察

此流程不采集新画面。先找到已经保存的 `observation.json`，再执行以下步骤。

1. 导入前置观察，保存返回的帧引用。

   ```powershell
   $beforeSource = 'runs/observations/<before-id>/observation.json'
   $before = uv run playsage evidence import $beforeSource --run-id review1 | ConvertFrom-Json
   $beforeRef = $before.frames[0].ref
   ```

2. 检索运行记录，并取得原图路径。

   ```powershell
   uv run playsage evidence history --run-id review1 --limit 20 --offset 0
   uv run playsage evidence inspect $beforeRef
   ```

   打开 `inspect` 返回的 `path`，确认图像内容。保存或返回路径不代表 Agent 已经看到图片。

3. 查看局部画面或读取像素。以下区域要求图片至少为 20 × 20 像素。

   ```powershell
   uv run playsage evidence inspect $beforeRef --roi 0 0 20 20
   uv run playsage evidence pixels $beforeRef --roi 0 0 2 2
   ```

4. 导入另一次独立观察，比较相同区域。

   ```powershell
   $afterSource = 'runs/observations/<after-id>/observation.json'
   $after = uv run playsage evidence import $afterSource --run-id review1 | ConvertFrom-Json
   $afterRef = $after.frames[0].ref
   uv run playsage evidence compare $beforeRef $afterRef --roi 0 0 20 20
   ```

### 预期结果

导入返回 `frames`，每帧包含 `run_id/frame_id` 形式的引用。程序保留 PNG/JPEG 原始字节，不重新编码。SRA 多图按顺序导入，最多 16 张；示例只使用第一张。

`inspect` 不带 ROI 时返回原图，带 ROI 时生成裁剪图。`compare` 输出各 RGB 通道平均绝对差、变化包围框和差异图。包围框相对 ROI；`null` 表示未检出像素差，不表示目标已完成。

ROI 使用图像像素坐标 `[x1,y1,x2,y2)`，包含左上、不包含右下，不能越界。比较要求图像尺寸一致。`pixels` 按行输出解码后的 RGB 值；JPEG 像素不是未经压缩的原场景。

## 为证据绑定活动上下文

只有在活动、包摘要、游戏版本和分辨率均有可靠来源时，才为观察指定完整上下文。缺少的信息保持 `null`，不要从文件名或画面猜测。

> **警告：** 不要给旧截图补上当前包摘要或当前游戏版本，借此把历史资料当作新证据。下面的包摘要必须与采集观察时使用的包一致。

1. 校验对应活动包，取得摘要。

   ```powershell
   $package = uv run playsage validate event_packs/zzz/cyber-healer | ConvertFrom-Json
   $digest = $package.digest
   ```

2. 指定真实来源和版本，再导入观察。以下示例要求原图为 1920 × 1080。

   ```powershell
   $source = 'runs/onedragon/<observation-id>/observation.json'
   $gameVersion = '<observed-version>'
   uv run playsage evidence import $source --run-id review2 --event-id zzz.cyber-healer --package-digest $digest --game-version $gameVersion --resolution 1920 1080
   ```

3. 按活动检索已有证据。

   ```powershell
   uv run playsage evidence history --event-id zzz.cyber-healer
   ```

历史图只有明确的来源标记才保留 `simulation` 真或假，缺失时保持未知。模拟证据可以用于离线流程，但不能授权实机重放。

## 保存并恢复活动记忆

`memory.json` 是唯一权威记录。`GUIDE.md` 与 `WORKING.md` 只是导出视图，不要通过修改这两个文件更新记忆。

1. 读取当前记忆和修订号。新命名空间的修订号为 0。

   ```powershell
   $view = uv run playsage memory show zzz.cyber-healer | ConvertFrom-Json
   $view
   ```

2. 在项目中创建 `notes` 目录，将以下 JSON 以 UTF-8 无 BOM 编码保存为 `notes/new-entry.json`。

   ```json
   {
     "kind": "hypothesis",
     "status": "hypothesis",
     "text": "待核实：进入蓝色通道后是否自动移动两格。",
     "source": "人工观察记录，尚未确认",
     "evidence_refs": []
   }
   ```

3. 使用刚读取的修订号提交条目。

   ```powershell
   $added = uv run playsage memory add zzz.cyber-healer --file notes/new-entry.json --expected-revision $view.revision | ConvertFrom-Json
   $entryId = $added.entry.id
   ```

4. 在另一会话中重新读取记忆，或导出可读快照。

   ```powershell
   uv run playsage memory show zzz.cyber-healer
   uv run playsage memory export zzz.cyber-healer
   ```

### 更新条目

只有在复核证据后，才显式修改结论状态。所有引用的活动、包摘要、游戏版本和分辨率必须与记忆相符。

1. 将以下局部更新保存为 `notes/update.json`，替换帧引用为真实值。

   ```json
   {
     "status": "supported",
     "evidence_refs": ["review2/<frame-id>"],
     "source": "逐帧人工复核"
   }
   ```

2. 重新读取修订号，核对期间的修改，再提交更新。若跨会话，先从 `show` 输出中取得真实条目 ID。

   ```powershell
   $view = uv run playsage memory show zzz.cyber-healer | ConvertFrom-Json
   uv run playsage memory update zzz.cyber-healer $entryId --file notes/update.json --expected-revision $view.revision
   ```

旧条目保留在 `previous_entries`，不会因更新而丢失原证据引用。程序只校验证据与上下文，不替记录人判断结论是否正确。

### 条目字段

| 字段 | 可用值或要求 |
| --- | --- |
| `kind` | `knowledge`、`progress`、`failure`、`hypothesis`、`next_step` |
| `status` | `hypothesis`、`observed`、`supported`、`refuted` |
| `text` | 结论、进度或待验证问题 |
| `source` | 判断来源，不能省略 |
| `evidence_refs` | 帧引用列表；非 `hypothesis` 状态必须有引用 |

`refuted` 的证据用于反驳，其余引用用于观察或支持。需要保留互相冲突的结论时，创建独立条目并说明来源。未知游戏版本不能支持已确认条目。

### 失效与旧版本

默认兼容上下文取活动包声明，不是运行时探测结果。`show/add/update/export` 均支持显式 `--game-version` 和 `--resolution WIDTH HEIGHT`；对同一工作流程使用一致的上下文。

包摘要、游戏版本、分辨率或证据发生变化时，旧记忆显示 `needs_review`，不会自动搬迁到新版本。只有 `context_matches` 也不代表结论正确或允许执行。

查看指定旧包的记忆：

```powershell
uv run playsage memory show zzz.cyber-healer --digest '<old-package-sha256>'
```

长期持有的 `EventMemory` 实例在每次 `show/export` 时重新核对包摘要与兼容声明，并保留显式覆盖值。包变更后，写入前需要重新打开实例。包无法读取或身份改变时直接报错，不继续标为适用。

更新使用协作 OS 锁、修订号比较和原子替换。遇到锁占用或 `revision conflict` 时，重新读取并核对变化，不自动覆盖或重试。导出会覆盖已有 Markdown 视图；不要在视图中保存独立笔记。

## 验证网格规则

此流程只比较规则预测与输入标注。它不识别任意截图、不执行动作，也不补造缺失状态。

### 准备输入

提供明确的棋盘、动作、操作前路径、完整的操作后标注，以及独立的前后证据。前后证据必须属于同一运行，按时间和序号排序，且上下文相符。

下面是合成棋盘的结构示例，不是真实活动记录。替换全部占位值，并使标注与所引用画面一致，然后保存为项目内的 `notes/grid-check.json`。

```json
{
  "schema_version": 1,
  "model_revision": "manual-rules-1",
  "context": {
    "event_id": "zzz.example",
    "package_digest": "<64位小写SHA256>",
    "game_version": "<实际版本>",
    "resolution": [1920, 1080]
  },
  "board": {
    "rows": 1,
    "columns": 3,
    "blocked": [],
    "targets": [],
    "end": [0, 2]
  },
  "interactions": [{
    "prefix": [[0, 0]],
    "action": "d",
    "before_ref": "review2/<before-frame-id>",
    "after_ref": "review2/<after-frame-id>",
    "annotation_source": "人工复核前后画面，已确认停稳",
    "observed": {
      "prefix": [[0, 0], [0, 1]],
      "position": [0, 1],
      "collected": [],
      "turns": 0,
      "complete": false
    }
  }]
}
```

### 运行检查

运行以下命令，将报告保存到 `runs/reports/grid-<uuid>.json`。

```powershell
uv run playsage model validate-grid notes/grid-check.json --report
```

不传 `--report` 时，仅返回结果，不保存报告文件。

### 解释结果

| 结果 | 含义 | 退出码 |
| --- | --- | --- |
| `match` | 当前模型与全部输入标注一致 | 0 |
| `mismatch` | 预测与标注存在差异；结果列出差异字段 | 1 |
| `insufficient_evidence` | 缺图、缺标注、未知版本或规则、非法动作、重复来源或上下文不符 | 1 |

遇到矛盾时，复核标注、规则和采集时机；遇到证据不足时，补充观察或暂不使用模型。同一原始观察重复导入，或同一多图观察内的图片，不能充当独立前后帧。程序通过 `source_sha256` 检查重复来源；独立采集的相同像素图片仍可参与检查。

`success` 只表示这次离线标注检查是否全部匹配。报告始终包含 `mode=offline_annotation_check`、`replay_allowed=false` 和 `goal_status=not_evaluated`。它不是独立视觉验真，也不能证明标注准确。

### 坐标与规则字段

| 字段或约定 | 含义 |
| --- | --- |
| 棋盘坐标 | `[row,column]`，不是截图像素坐标 |
| `w/s/a/d` | 上、下、左、右 |
| `prefix` | 操作前已走过的完整简单路径，包含起点 |
| `observed.prefix` | 操作后完整路径，传送入口和出口均需包含 |
| `collected` | 已收集目标集合 |
| `turns` | 累计顺时针旋转次数模 4 |
| `complete` | 模型中的终点与目标条件，不是实机完成证明 |
| 基础规则 | `blocked`、`excluded`、`targets`、`end`、`rotations`、`ordered_targets` |
| `ports` | 通道端口，例如 `{"cell":[r,c],"ports":"ws"}` |
| `forced` | 强制方向，例如 `{"cell":[r,c],"key":"d"}` |
| `teleports` | 成对坐标列表 |

每边最多 64 格，每次最多 1000 条交互。未知字段被拒绝。报告保留模型标签、棋盘摘要，以及求解器和验证器源码哈希；代码或规则变化后需要重新回测。

## 数据布局与限制

可变数据全部放在活动包之外。更新记忆不会改变活动包摘要，也不会清除 registry 已有的 `stale` 状态。新离线命令不写入 `data/events.sqlite`。

```text
runs/evidence/<run_id>/
  frames/<frame_id>.json       # schema_version=1，来源、上下文、时间与哈希
  frames/<frame_id>.png|jpg    # 原始采集字节，不转码
  steps/<step_id>.json         # 意图、结果、前后帧、预期与实际观察
  derived/*.png               # 裁剪与差异图
runs/reports/grid-<uuid>.json   # 显式保存的离线报告

data/event_memory/<game>/<slug>/<package_digest>/
  memory.json                 # 唯一权威记忆，包含修订号和历史
  GUIDE.md                    # knowledge 导出视图
  WORKING.md                  # 其他工作条目的导出视图
```

证据使用 UTC 时间与运行内序号，不跨进程比较 `Frame.captured_at` 的 monotonic 时钟。历史帧带 `historical_only=true`，不能通过 `--observed` 冒充实时 OneDragon 观察。

ID 使用小写字母、数字、`_` 和 `-`，最长 96 字符；拒绝 Windows 设备名、路径穿越、符号链接和目录 junction。活动 ID 使用 `zzz|ww|ef|hsr.slug` 格式，包摘要为 64 位小写 SHA-256。

| 限制 | 上限 |
| --- | --- |
| 整个 `runs/evidence` | 默认 1 GiB；每个 evidence 子命令支持 `--capacity-bytes` |
| 单张图片 | 64 MiB、1600 万像素 |
| 单次导入 | 16 张图片 |
| 单次像素输出 | 4096 像素 |
| 单份 JSON | 2 MiB |
| 历史页 | 默认 100 条，最多 1000 条 |
| 当前记忆与历史条目 | 各最多 1000 条 |
| 每条记忆的证据引用 | 最多 64 个 |

原图、元数据和派生图都计入证据容量。替换文件前还需预留新记录临时空间。报告和记忆导出视图不计入证据目录容量。容量参数只影响本次调用，不修改用户配置。

SHA-256 用于检测图像意外改动，不是身份签名，也不抵御恶意本地写入。元数据由受信任的本地调用方维护。

## 检查容量与清理预览

运行以下命令查看容量和被记忆引用的运行目录。

```powershell
uv run playsage evidence stats
uv run playsage evidence cleanup-preview
uv run playsage evidence stats --capacity-bytes 2147483648
```

`cleanup-preview` 只生成预览，不删除文件，也不进行全帧录屏。

| 字段 | 含义 |
| --- | --- |
| `protected_runs` | 当前、旧包或历史条目引用过的运行目录 |
| `incomplete_files` | 没有对应元数据的残留原图路径；仍计入容量 |
| `unreferenced_runs` | 未被本次扫描到的记忆引用的实际运行目录 |
| `delete_enabled` | 始终为 `false` |

> **警告：** `unreferenced_runs` 不表示可安全删除。外部报告或人工笔记仍可能引用这些文件。损坏的记忆或已发布元数据会使预览报错，而不是忽略潜在引用。

## 处理故障

故障恢复首先区分“本地记录失败”和“输入可能已发生”。不要因没有后帧就推断动作没有执行。

### 导入失败

原始观察不迁移、不修改、不删除。程序逐帧保存图片后发布元数据；元数据失败时，仅回收本次尚未提交的图片。

多图导入中途失败时，之前已发布的帧保留，命令不会声称整批完成。回收失败会附带残留路径，并可通过 `incomplete_files` 定位。先查看历史和容量，再决定是否重新导入；不要自动删除已发布证据。

### 记忆冲突或不适用

| 情况 | 处理方式 |
| --- | --- |
| `revision conflict` 或锁占用 | 重新 `show`，核对其他会话修改，再显式提交 |
| `needs_review` | 检查包、版本、分辨率和引用；不要直接继承为当前事实 |
| 证据缺失或哈希不符 | 保留原记录，定位丢失或改动原因，再重新核实结论 |
| 包无法读取或身份变化 | 修复包或重新打开正确活动，不绕过身份检查 |

### OneDragon 动作记录不完整

本节说明独立开发工具的故障语义，不是授权执行真实输入的操作步骤。

| 状态 | 含义与处理方式 |
| --- | --- |
| `intent_recorded` | 意图已保存；中断后无法据此确定是否发送，先重新观察 |
| `not_dispatched` | 本次调用在派发前被取消、超时或检查拒绝，明确报告“输入未发送” |
| `backend_returned` | 后端返回，但不能据此认定游戏目标完成 |
| `observed` | 后置观察已归档，目标仍为 `not_evaluated` |
| `incomplete` | 输入可能已发生，停止并重新观察，禁止自动重试 |

前置意图写盘失败时不发送输入。意图持久化后，工具让出事件循环处理取消，再核对绝对时间预算与原始实时观察时效。

派发后的取消、超时、传输失败、截图失败或归档失败都会尽力记录 `incomplete`，并报告“输入可能已发生 / input may have occurred”。若存储本身损坏，文件可能仍停留在先前状态，不能把旧状态视为安全重试信号。客户端取消不代表服务端输入已取消，原有短按释放等待机制保持不变。

## 验证离线流程

在项目根目录运行以下命令。

```powershell
uv run pytest tests/test_evidence.py tests/test_memory.py tests/test_rule_validation.py tests/test_offline_cli.py -q
uv run pytest
uv run ruff check src tests
uv run ruff check tools/onedragon_step.py
uv run ruff check .
```

`test_complete_offline_cli_workflow` 在临时目录中启动真实 CLI 子进程，使用明确标记为模拟的 PNG/JPEG，完成导入、回看、裁剪、像素、对比、记忆恢复与导出、网格回测和报告保存。测试同时核验包摘要与 registry 的 `stale` 状态未变，不连接游戏。

新增记录链路尚未重新实机验收。通用 `run_skill` 仍拒绝动态分发活动包 Python；第三方版本和依赖不随离线分析操作更新。

## 相关内容

- [项目入门与当前能力](../README.md)
- [架构与执行边界](design.md)
- [文档编写规范](documentation-standard.md)
