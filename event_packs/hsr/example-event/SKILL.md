---
name: hsr-example-event
description: Demonstrate the QuestWeaver event package contract using the mock backend only.
---

此包仅用于模拟活动，不代表真实崩铁活动。
使用 `uv run questweaver index` 后运行 `uv run questweaver demo`。
模拟流程识别“开始挑战”、执行一次点击，并重新观察 `challenge_complete`。
CLI 执行的是内置 `questweaver.demo.start_challenge`，不会动态导入包内 Python。
每次 demo 重置模拟场景；可重复执行验证控制和日志链路。
模拟通过仍是 candidate，不能提升为实机 verified。
