# GameScaling-S3 RSI 离线原型

本模块把 GameScaling-S3 的迁移和 RSI 流程先落在离线数据层。它记录屏幕帧引用、原生键鼠动作、时间戳、失败信号和人工接管片段，并在固定任务集上比较 Champion 与 Challenger。

当前实现不连接游戏、不采集屏幕、不发送输入、不加载 GameScaling 权重、不训练或修改模型参数。`promote` 只记录通过离线门槛的晋级决定，不切换运行时模型。

## 数据布局

所有记录位于活动包之外的运行产物目录：

```text
runs/gamescaling_rsi/
  episodes.jsonl          # 轨迹、帧引用、动作和失败信号
  takeovers.jsonl         # 独立记录的人工接管片段
  model_versions.jsonl    # Champion、Challenger 和候选版本登记
  evaluations.jsonl       # 固定任务集的离线评估结果
  decisions.jsonl         # 显式记录的离线晋级决定
```

轨迹中的 `frames[].ref` 应指向已有证据或外部帧索引；模块不会复制图像或猜测画面内容。记录使用严格 JSON 契约，时间序列必须有序，重复 ID 会被拒绝。

## CLI

以下命令均为离线操作。JSON 和 JSONL 输入必须位于项目根目录内；从其他目录调用时，先传 `--root`。

```powershell
uv run playsage rsi trajectory import notes/episodes.jsonl
uv run playsage rsi trajectory list --limit 20
uv run playsage rsi hard-examples --limit 50 --min-score 3
uv run playsage rsi takeover add notes/takeover.json
uv run playsage rsi model register notes/model.json
uv run playsage rsi evaluate import notes/evaluation.json
uv run playsage rsi evaluate compare --champion s3-base --challenger zzz-lora-001 --suite fixed-v1
uv run playsage rsi model promote --champion s3-base --challenger zzz-lora-001 --suite fixed-v1
```

难例筛选综合人工接管、失败或中止、目标进度、最低置信度、解析失败、卡住、战斗失败、UI 错误和超时信号。它只返回训练候选引用，不自动生成训练任务。

晋级要求 Champion 和 Challenger 使用同一固定任务集，且 Challenger 成功率严格提升，同时解析失败率和不安全动作率不得上升。评估结果中的 `runtime_switch=false` 和 `weights_modified=false` 是固定安全边界。

## 后续接入顺序

1. 先导入少量真实或人工复核的目标游戏轨迹，确认帧引用、动作时间戳和失败分类。
2. 再接入经过验证的 GameScaling-S3 推理与原生 action chunk parser。
3. 训练前固定回归任务集和输出目录，使用每款游戏独立 LoRA；数据按不重叠分片提交到受控 GPU 队列。
4. 通过离线 Champion/Challenger 门槛后，再单独进行人工监督的实机验证。

没有真实轨迹、可用 checkpoint 和经过核验的推理/训练脚本时，不应提交 GPU 训练，也不能把离线晋级记录解释为游戏成功率或无人值守权限。
