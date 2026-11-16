"""Run the bounded PlaySage documentation review through an OpenAI-compatible API."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import urllib.error
import urllib.request
from pathlib import Path

ALLOWED = ("README.md", "docs/design.md", "docs/evidence-memory.md", "docs/rename-playsage.md")
MAX_DOCUMENT_BYTES = 120_000
MAX_PATCH_BYTES = 100_000


def fail(message: str) -> int:
    report = {
        "before": os.environ.get("DOCS_BEFORE", ""),
        "head": os.environ.get("GITHUB_SHA", ""),
        "status": "受阻",
        "changed_files": [],
        "reason": message,
        "verification": ["未生成文档修改"],
        "test_evidence": "unavailable",
        "limitations": ["项目测试与实机未验证；模型或 API 调用失败。"],
    }
    Path(os.environ.get("DOCS_REPORT", "/tmp/gh-aw/docs-sync-report.json")).write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(message, file=sys.stderr)
    return 1


def parse_model_json(content: object) -> dict:
    if not isinstance(content, str):
        raise TypeError("tonkic API returned non-text message content")
    text = content.strip()
    if text.startswith("```") and text.endswith("```"):
        lines = text.splitlines()
        if len(lines) < 3:
            raise RuntimeError("tonkic API returned an empty JSON code fence")
        text = "\n".join(lines[1:-1]).strip()
    result = json.loads(text)
    if not isinstance(result, dict):
        raise TypeError("tonkic API returned a JSON value instead of an object")
    return result


def call_api(prompt: str) -> dict:
    base = os.environ.get("TONKIC_API_BASE", "https://tonkicapi.xyz/v1").rstrip("/")
    model = os.environ.get("TONKIC_API_MODEL", "")
    key = os.environ.get("TONKIC_API_KEY", "")
    if not model:
        raise RuntimeError("TONKIC_API_MODEL repository variable is missing")
    if not key:
        raise RuntimeError("TONKIC_API_KEY repository secret is missing")
    body = json.dumps({
        "model": model,
        "temperature": 0,
        "messages": [
            {"role": "system", "content": "你是 PlaySage 文档维护者。只按用户要求返回 JSON。"},
            {"role": "user", "content": prompt},
        ],
    }).encode("utf-8")
    request = urllib.request.Request(
        base + "/chat/completions", data=body,
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=300) as response:
            payload = json.load(response)
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
        raise RuntimeError(f"tonkic API request failed: {exc}") from exc
    try:
        content = payload["choices"][0]["message"]["content"]
        return parse_model_json(content)
    except (KeyError, IndexError, TypeError, json.JSONDecodeError, RuntimeError) as exc:
        raise RuntimeError("tonkic API returned an invalid JSON response") from exc


def main() -> int:
    root = Path.cwd()
    context_path = Path(os.environ.get("DOCS_CONTEXT", "/tmp/gh-aw/docs-sync/context.json"))
    diff_path = Path(os.environ.get("DOCS_DIFF", "/tmp/gh-aw/docs-sync/changes.diff"))
    report_path = Path(os.environ.get("DOCS_REPORT", "/tmp/gh-aw/docs-sync-report.json"))
    context = json.loads(context_path.read_text(encoding="utf-8"))
    documents = {}
    for name in (*ALLOWED, "docs/documentation-standard.md"):
        documents[name] = (root / name).read_text(encoding="utf-8")
    prompt = (
        "检查本次 push 的完整文档影响。只能编辑以下白名单：" + ", ".join(ALLOWED) + "。\n"
        "禁止修改代码、测试、依赖、workflow、规则、数据或其他文件；不运行项目代码。\n"
        "必须返回 JSON：{status, changed_files, reason, verification, limitations, edits}。"
        "status 只能是 已更新 或 无需修改；changed_files 必须是排序后的文件名数组；"
        "edits 是文件名到完整 UTF-8 文本的对象，无需修改时为空。限制中必须写项目测试与实机未验证，"
        "test_evidence 不要返回，脚本会固定写 unavailable。\n"
        f"push context:\n{json.dumps(context, ensure_ascii=False, indent=2)}\n"
        f"changes.diff:\n{diff_path.read_text(encoding='utf-8')}\n"
        f"documents:\n{json.dumps(documents, ensure_ascii=False)}"
    )
    try:
        result = call_api(prompt)
        status = result.get("status")
        edits = result.get("edits", {})
        changed = sorted(edits) if isinstance(edits, dict) else []
        if status not in {"已更新", "无需修改"} or not isinstance(edits, dict):
            return fail("模型返回的文档结果结构无效")
        if status == "无需修改" and changed:
            return fail("模型声称无需修改但返回了文档编辑")
        if status == "已更新" and not changed:
            return fail("模型声称已更新但没有返回文档编辑")
        if set(changed) - set(ALLOWED):
            return fail("模型返回了白名单之外的文件")
        if not isinstance(result.get("reason"), str) or not result["reason"].strip():
            return fail("模型没有返回有效的修改理由")
        for field in ("verification", "limitations"):
            items = result.get(field)
            if not isinstance(items, list) or not items or any(
                not isinstance(item, str) or not item.strip() for item in items
            ):
                return fail(f"模型没有返回有效的 {field} 列表")
        if not any("未验证" in item for item in result["limitations"]):
            return fail("模型限制中缺少项目测试与实机未验证说明")
        pending = {}
        for name in changed:
            text = edits[name]
            path = root / name
            if not isinstance(text, str) or not text.strip() or len(text.encode("utf-8")) > MAX_DOCUMENT_BYTES:
                return fail(f"文档编辑无效或超出大小限制：{name}")
            if path.is_symlink() or not path.is_file() or not path.resolve().is_relative_to(root.resolve()):
                return fail(f"文档路径无效：{name}")
            pending[name] = text
        for name, text in pending.items():
            (root / name).write_text(text, encoding="utf-8", newline="\n")
        diff = subprocess.run(
            ["git", "diff", "--no-ext-diff", "--no-textconv", "--no-renames", "--", *ALLOWED],
            capture_output=True, check=True,
        ).stdout
        if len(diff) > MAX_PATCH_BYTES:
            return fail("文档补丁超过 100 KB 限制")
        report = {
            "before": context["before"], "head": context["head"], "status": status,
            "changed_files": changed, "reason": result["reason"],
            "verification": result["verification"], "test_evidence": "unavailable",
            "limitations": result["limitations"],
        }
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return 0
    except (OSError, RuntimeError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return fail(str(exc))


if __name__ == "__main__":
    raise SystemExit(main())
