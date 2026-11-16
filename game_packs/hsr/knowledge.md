# 崩坏：星穹铁道 / SRA

后端来源：[StarRailAssistant](https://github.com/Shasnow/StarRailAssistant)。
契约来源：[官方 MCP 文档](https://starrailassistant.top/server/mcp/)，核验日期 2026-10-31。

早期公开地址为 `http://localhost:5000/mcp`；本项目只读客户端为兼容已有配置仍默认使用 `http://127.0.0.1:5000/mcp`。SRA 2.25.x 服务端默认 5073，按实际启动端口传入 CLI 的 `--url`，不自动改写运行配置。
`sra_screenshot` 无参数。2026-11-13 更新后，CLI 通过 tools/list 核验工具，验证内联 PNG/JPEG，并按真实格式保存原始字节；不依赖 MIME 声明决定扩展名。
原生工具另有 sra_ocr、sra_ocr_match、sra_click_point_rel、sra_press_key、sra_task_stop。
这些名称用于发现线索；调用前检查运行中的 inputSchema，不能猜测返回 JSON。

当前接入：工具探测、图片读取。未接入：窗口身份验证、OCR 归一化、按键、任务分发、停止确认。
截图尺寸可能与游戏客户端尺寸不同；相对点击仍需确认目标和当前窗口。不要假设 720p 坐标等于桌面坐标。
不调用 sra_startup 自动启动后端。后端安装与运行由独立 SRA 项目管理。
