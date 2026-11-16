# 第三方游戏后端

初始按用户要求，四个游戏后端在本目录独立克隆。每个子目录保留自己的 `.git`、许可证和依赖环境，不并入 QuestWeaver 的 Python 包。另有 BetterGI 桌面分身来源与 March7thAssistant 参考源码；当前更新记录见本文末尾。

| 目录 | 游戏 | 上游 |
| --- | --- | --- |
| OneDragon | 绝区零 | https://github.com/OneDragon-Anything/ZenlessZoneZero-OneDragon |
| OK-WW | 鸣潮 | https://github.com/ok-oldking/ok-wuthering-waves |
| OK-EF | 终末地 | https://github.com/AliceJump/ok-end-field |
| SRA | 崩坏：星穹铁道 | https://github.com/Shasnow/StarRailAssistant |

克隆时间：2026-10-31。使用 `git clone --depth 1`，初始版本见 repositories.json。
需要完整历史时，在对应目录运行 `git fetch --unshallow`。更新前检查工作区和本地配置，不能强制覆盖。

OneDragon 已安装独立 `.venv`（Python 3.11，包含 dev 组提供的 MCP）；SRA 已安装独立 `.venv`（Python 3.12，standard/server extras）。OK-WW、OK-EF 和 March7thAssistant 克隆未在本项目安装运行环境；鸣潮实际运行版仍是仓库外的独立安装，不与克隆混用。
新克隆 OneDragon 包含 MCP；电脑原先的 `D:\zzz-one-dragon` 版本不含这项服务。二者不能混为一谈。

OneDragon 服务入口：

```powershell
cd D:\QuestWeaver\third_party\OneDragon
$env:PYTHONPATH = "$PWD\src"
.\.venv\Scripts\python.exe -m zzz_od.backend.entry.server --host 127.0.0.1 --port 23001
```

默认 MCP 地址为 `http://127.0.0.1:23001/mcp`。真实输入需要服务与游戏处于同一交互式桌面且权限匹配。
停止信号仅表示已发出，必须再检查运行状态。不要同时启动旧 OneDragon 自动任务或其他游戏输入后端。

2026-11-01另克隆 BetterGI（https://github.com/babalae/better-genshin-impact），固定提交43eecc21bf700d3db58a174c2e66f5c90e7c69f9，用于复用 Child Session 桌面分身。它不是第五个游戏后端；来源与GPL许可见 tools/child-session/NOTICE.md。当前活动执行使用分身内23002端点，上述23001仅保留为早期直接启动方式。


## 2026-11-13：仅正式稳定版更新

官方 `releases/latest` 页面与远程发布标签交叉核验后，固定到发布提交（detached HEAD），没有追踪开发分支。`repositories.json` 保留最初克隆记录，不当作当前运行版本锁。

| 目录 | 本轮结果 | 当前提交 | 环境状态 |
| --- | --- | --- | --- |
| OneDragon | 更新到 v2.6.1 | 3cbeda9e20a0bf1ab84ab56861bb01b7ee668aa8 | 已按正式版 uv.lock 同步，保留额外安装包 |
| SRA | 更新到 v2.25.1 | b92a06e593af64654d2815b61e7c00a6ac74fcf9 | editable 安装元数据已从 2.25.0b3 更新到 2.25.1 |
| OK-EF | 更新到 v2.0.18 | a5a5583acee4d89a07123918a210f249b2b87e40 | 仅源码，不额外创建环境 |
| March7thAssistant | 更新到 v2026.11.8 | 17ec9ddc82208aa2f2e01f4deaa20527ff176490 | 仅源码，不追随后续开发提交 |
| OK-WW | 暂缓 | 43ef519f303bf928400e465f37acd35982bcbc5f | v3.8.0 虽是正式发布，但依赖 ok-script 3.0.5b7；遵循不引入预发布依赖的要求，克隆及仓库外安装均未更新 |
| BetterGI | 保持已验证来源 | 43eecc21bf700d3db58a174c2e66f5c90e7c69f9 | 本项目引用的四个文件与新版一致，无需为当前用途更新 |

### 同步与兼容处理

- 主项目更新 pydantic 2.14.3、其依赖 pydantic-core 2.50.4、ruff 0.17.5；MCP、Pillow 的主版本约束不变。`pyproject.toml` 增加 `prerelease = "disallow"`。
- OneDragon 旧 `.venv` 的 home 指向已不存在的 Python，已改为项目内原有 `.runtime/cpython-3.11.15`，未重建虚拟环境或切换 Python 版本。
- OneDragon 正式依赖更新 certifi、charset-normalizer、urllib3，并加入 vgamepad 0.2.0。首次同步在安装脚本等待期间超时；确认上游提供 `VGAMEPAD_SKIP_VIGEMBUS_INSTALL=true` 后，使用该选项完成 Python 包安装。最终查询到 ViGEmBus 正在运行，但未记录安装前驱动状态，不据此声称本轮驱动状态是否变化；未做虚拟手柄实测。
- 后续维护应从后端目录执行或使用 `uv sync --directory third_party/OneDragon --locked --group dev --inexact`，避免其相对 cache-dir 在主项目根目录生成缓存。安装 vgamepad 时显式设置上游跳过驱动安装选项；系统驱动升级不包含在自动依赖同步流程中。
- SRA 正式只读客户端已支持 PNG/JPEG：先验证实际编码，再按格式保存原始字节；仍拒绝路径文本、损坏数据和其他图片格式。没有新增输入权限。
- 客户端保留已有 5000 端口默认值；SRA 默认服务端为 5073，使用实际端口对应的 `--url`，未改写用户运行配置。

### 验证与回滚

- 完整测试：83 passed；新增 JPEG 用例先复现 3 项失败，修复后全部通过。
- 主项目锁文件、src/tests 静态检查通过；主项目、OneDragon、SRA 的 `uv pip check` 均通过。OneDragon 再次 locked dry-run 显示无需修改。
- 全项目 Ruff 仍有更新前已有的 71 项 tools 问题；未扩大范围修复无关开发脚本。
- 没有启动游戏、执行输入或进行更新后的实机回放。源码/依赖检查通过不意味着活动包可自动晋升为 verified。
- 本轮备份位于 `runs/maintenance/stable-updates/20261113-023625/`：原主项目声明与锁文件、后端包清单、接入文件原文和源码前后状态。原 OneDragon pyvenv.cfg 另存于 `runs/maintenance/stable-updates/20261113-023431/`。
- 四个已更新仓库保留原分支，并有 `refs/questweaver-backups/stable-20261113-023625` 回滚引用；回滚前停止对应服务、确认本地改动，再同时恢复相应源码与依赖，不强制重置工作区。
