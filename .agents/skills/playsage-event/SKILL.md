---
name: playsage-event
description: Explore a game event in PlaySage, find compatible event knowledge, and record observations and bounded trials for reuse.
---

在项目根目录使用 CLI。先读取 README.md 的当前能力边界，再按游戏读取 game_packs/<game>/knowledge.md。

使用 `playsage` 主命令与 `playsage.*` 实现；已安装技能需重新加载项目目录才能看到新 ID。迁移边界见 docs/rename-playsage.md。

1. `uv run playsage index`；`uv run playsage search "活动名" --game hsr --backend sra --game-version VERSION --resolution WIDTH HEIGHT`。
2. 只加载命中活动的 SKILL.md、event.yaml 与所需规则。`replay_allowed=false` 的包只能作为知识参考。
3. 无已验证技能时进入探索。用 `sra probe` 读取实际工具 schema，用 `sra observe` 获取图片后实际打开图片；路径或成功返回码不能代替图像接收。
4. 通用CLI只支持SRA只读观察；OneDragon开发工具已接入原生受限输入，见对应游戏知识包与 tools/onedragon_step.py。自动技能分发与verified晋升仍未实现。通过原生MCP探索时先停止其他控制者，确认窗口身份和坐标，执行有限动作并重新观察；本地锁不能约束独立原生MCP或人工输入。
5. 保存活动规则、成功条件、失败记录与证据路径。未知规则明确标记未知。重复流程整理为候选包，使用 playsage-skill-author。

停止条件：窗口/分辨率变化、截图过期、目标不确定、预算耗尽、用户接管。不要盲目重试输入。
`demo` 永远是模拟，不证明真实游戏活动完成。
