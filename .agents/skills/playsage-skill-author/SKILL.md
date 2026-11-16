---
name: playsage-skill-author
description: Create and validate PlaySage event packages from observed game rules, policies and execution evidence.
---

用 `uv run playsage new GAME SLUG --name "活动名"` 创建 draft。
契约见 docs/design.md 和 src/playsage/models.py；参考 event_packs/hsr/example-event，但不要照搬模拟成功条件。

使用 `playsage` 主命令与 `playsage.*` 实现；已安装技能需重新加载项目目录才能看到新 ID。迁移边界见 docs/rename-playsage.md。

- 在 SKILL.md 写清入口、适用状态、成功条件、失败恢复及停止条件；在 references/ 保留规则来源与证据索引。
- 每个 supported_backend 必须有独立入口，不能因算法可复用就宣称执行器兼容。
- 未知版本保持 unknown，未验证后端不写进 supported_backends。绝对路径、目录穿越和符号链接不属于可分发活动包。
- Pipeline JSON 交给 MaaFramework 校验和执行；Python 先做离线测试和代码审核。CLI 不加载生成的 Python。
- `uv run playsage validate event_packs/GAME/SLUG`，再 index。测试覆盖失败和变化后的状态，记录 digest 与证据，不能只验证同一初始状态。
- 当前没有实机 verified 晋升命令。不要直接改 SQLite 授权，也不要把 YAML status=verified 当验证通过。模拟记录保持 candidate。
- 包内任意资源变更会触发 stale；重验证后仍需后续实机验证功能才能授权自动重放。
