"""Prepare a push review and reject unsafe documentation proposals (stdlib only)."""

from __future__ import annotations

import argparse
import json
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

ALLOWED_FILES = (
    "README.md",
    "docs/design.md",
    "docs/evidence-memory.md",
    "docs/rename-playsage.md",
)
BOT_PREFIX = "gh-aw/docs-sync/"
SHA = re.compile(r"[0-9a-f]{40}\Z")
MAX_PATCH_BYTES = 100_000
MAX_DOCUMENT_BYTES = 120_000


class ReviewError(ValueError):
    """A missing fact or unsafe change prevents publication."""


def git(root: Path, *args: str, input_data: bytes | None = None) -> bytes:
    result = subprocess.run(
        ["git", "-c", "core.fsmonitor=false", "-c", "core.hooksPath=/dev/null", *args],
        cwd=root,
        input=input_data,
        capture_output=True,
        check=False,
        timeout=60,
    )
    if result.returncode:
        raise ReviewError(f"git {args[0]} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout


def commit(root: Path, value: str) -> str:
    if not isinstance(value, str) or not SHA.fullmatch(value):
        raise ReviewError("Expected a full lowercase 40-character commit SHA")
    resolved = git(root, "rev-parse", "--verify", f"{value}^{{commit}}").decode().strip()
    if resolved != value:
        raise ReviewError("Commit identity mismatch")
    return value


def paths(data: bytes) -> list[str]:
    return sorted({part.decode("utf-8", "strict") for part in data.split(b"\0") if part})


def review_range(root: Path, event: dict, expected_head: str) -> dict:
    ref = event.get("ref", "")
    if not isinstance(ref, str) or not ref.startswith("refs/heads/"):
        raise ReviewError("Only branch push events are supported")
    branch = ref.removeprefix("refs/heads/")
    if event.get("deleted") or event.get("after") == "0" * 40:
        raise ReviewError("Deleted branches have no reviewable head")
    if branch.startswith("gh-aw/"):
        raise ReviewError("Agent-generated branches are excluded to prevent loops")
    if git(root, "check-ref-format", ref):
        raise ReviewError("Invalid branch ref")
    head = commit(root, expected_head)
    if event.get("after") != head:
        raise ReviewError("Push after SHA does not match the workflow SHA")
    before = event.get("before")
    if not isinstance(before, str) or not SHA.fullmatch(before):
        raise ReviewError("Push before SHA is missing or invalid; do not guess a parent")
    if before == "0" * 40:
        base = git(root, "hash-object", "-w", "-t", "tree", "--stdin", input_data=b"").decode().strip()
        mode = "new_branch_full_tree"
    else:
        base = commit(root, before)
        mode = "push_range"
    changed = paths(git(root, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                        "--name-only", "-z", base, head, "--"))
    return {"before": before, "base": base, "head": head, "branch": branch,
            "mode": mode, "changed_files": changed, "test_evidence": "unavailable"}


def markdown_headings(text: str) -> set[str]:
    text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
    seen: dict[str, int] = {}
    anchors = set()
    for match in re.finditer(r"(?m)^#{1,6}\s+(.+?)\s*#*\s*$", text):
        slug = re.sub(r"[^\w\s-]", "", match.group(1).strip().lower()).replace(" ", "-")
        count = seen.get(slug, 0)
        seen[slug] = count + 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")
    return anchors


def check_links(root: Path, names: list[str] | tuple[str, ...]) -> int:
    count = 0
    for name in names:
        page = root / name
        if page.is_symlink() or not page.resolve().is_relative_to(root.resolve()):
            raise ReviewError(f"Document escapes repository: {name}")
        if not page.is_file() or page.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ReviewError(f"Missing or oversized document: {name}")
        text = page.read_text(encoding="utf-8")
        text = re.sub(r"(?ms)^\s*(`{3,}|~{3,}).*?^\s*\1\s*$", "", text)
        for target in re.findall(r"\[[^\]\n]*\]\(([^\s)]+)\)", text):
            link = urlsplit(target.strip("<>"))
            if link.scheme or link.netloc:
                continue
            relative = unquote(link.path)
            destination = (page.parent / relative).resolve() if relative else page.resolve()
            if not destination.is_relative_to(root.resolve()) or not destination.exists():
                raise ReviewError(f"Broken or out-of-root local link in {name}: {target}")
            if (link.fragment and destination.suffix == ".md"
                    and unquote(link.fragment) not in markdown_headings(
                        destination.read_text(encoding="utf-8")
                    )):
                raise ReviewError(f"Missing heading in {name}: {target}")
            count += 1
    return count


def proposal_paths(root: Path, head: str) -> list[str]:
    commit(root, head)
    tracked = git(root, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                  "--name-only", "-z", head, "--")
    staged = git(root, "diff", "--cached", "--no-ext-diff", "--no-textconv", "--no-renames",
                 "--name-only", "-z", head, "--")
    untracked = git(root, "ls-files", "--others", "--exclude-standard", "-z")
    return sorted(set(paths(tracked) + paths(staged) + paths(untracked)))


def validate_proposal(root: Path, head: str) -> list[str]:
    changed = proposal_paths(root, head)
    forbidden = sorted(set(changed) - set(ALLOWED_FILES))
    if forbidden:
        raise ReviewError("Outside documentation allowlist: " + ", ".join(forbidden))
    patch = git(root, "diff", "--no-ext-diff", "--no-textconv", "--no-renames", head, "--")
    if len(patch) > MAX_PATCH_BYTES:
        raise ReviewError("Documentation patch exceeds the review budget")
    for name in changed:
        path = root / name
        if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
            raise ReviewError(f"Symlink or path escape is not allowed: {name}")
        if not path.is_file() or not stat.S_ISREG(path.lstat().st_mode):
            raise ReviewError(f"Deleting or replacing documents is not allowed: {name}")
        if os.name != "nt" and path.stat().st_mode & 0o111:
            raise ReviewError(f"Executable document is not allowed: {name}")
        # Check staged modes as well as the worktree; neither symlinks nor gitlinks are documents.
        entries = git(root, "ls-files", "--stage", "--", name).decode().splitlines()
        if any(not entry.startswith("100644 ") for entry in entries):
            raise ReviewError(f"Unsafe index file mode: {name}")
        if path.stat().st_size > MAX_DOCUMENT_BYTES:
            raise ReviewError(f"Oversized document: {name}")
        path.read_text(encoding="utf-8")
    check_links(root, changed)
    return changed


def validate_report(report: dict, context: dict, changed: list[str]) -> None:
    if report.get("before") != context["before"] or report.get("head") != context["head"]:
        raise ReviewError("Report does not describe this exact push range")
    if report.get("status") not in {"已更新", "无需修改", "受阻"}:
        raise ReviewError("Report must state 已更新, 无需修改, or 受阻")
    if report.get("changed_files") != changed:
        raise ReviewError("Report changed_files must exactly match the sorted proposed changes")
    if not isinstance(report.get("reason"), str) or not report["reason"].strip():
        raise ReviewError("Report must explain the documentation impact or no-change decision")
    for field in ("verification", "limitations"):
        items = report.get(field)
        if not isinstance(items, list) or not items or any(
            not isinstance(item, str) or not item.strip() for item in items
        ):
            raise ReviewError(f"Report must provide a nonempty {field} list")
    # This workflow deliberately never runs project or game code. Do not accept invented CI claims.
    if report.get("test_evidence") != "unavailable":
        raise ReviewError("This workflow has no project test evidence; mark it unavailable")
    if not any("未验证" in item for item in report["limitations"]):
        raise ReviewError("Missing test evidence must be explicitly labelled 未验证")
    if report["status"] == "受阻":
        raise ReviewError("Agent reported a blocker: " + report["reason"])
    if bool(changed) != (report["status"] == "已更新"):
        raise ReviewError("Report status disagrees with actual documentation changes")


def write_summary(context: dict, report: dict, changed: list[str]) -> None:
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary:
        return
    lines = ["## PlaySage 文档检查", "",
             f"检查范围：`{context['before']}` → `{context['head']}`",
             f"文档结果：{report['status']}", f"修改说明：{report['reason']}",
             "修改文件：" + (", ".join(changed) or "无"),
             "验证与限制：仅执行范围、白名单、报告和本地链接静态检查；项目测试与实机未验证。"]
    lines.extend("- " + item for item in report["limitations"])
    with Path(summary).open("a", encoding="utf-8") as stream:
        stream.write("\n".join(lines) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "guard", "links"])
    parser.add_argument("--root", type=Path, default=Path.cwd())
    parser.add_argument("--event", type=Path)
    parser.add_argument("--head")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--check-remote", action="store_true")
    args = parser.parse_args(argv)
    try:
        root = args.root.resolve()
        if args.command == "links":
            names = (*ALLOWED_FILES, "docs/documentation-standard.md",
                     "docs/documentation-workflow.md")
            print(json.dumps({"status": "ok", "local_links": check_links(root, names)}))
            return 0
        if args.event is None or args.head is None:
            raise ReviewError("--event and --head are required")
        event = json.loads(args.event.read_text(encoding="utf-8"))
        context = review_range(root, event, args.head)
        if args.command == "prepare":
            if args.output is None:
                raise ReviewError("--output is required")
            args.output.mkdir(parents=True, exist_ok=True)
            (args.output / "context.json").write_text(
                json.dumps(context, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            # Filenames cover the complete range. Large raw patches are not silently truncated.
            patch = git(root, "diff", "--no-ext-diff", "--no-textconv", "--no-renames",
                        context["base"], context["head"], "--")
            if len(patch) > 1_000_000:
                raise ReviewError("Push diff exceeds 1 MB; split the review instead of truncating it")
            (args.output / "changes.diff").write_bytes(patch)
        else:
            if args.report is None or args.report.stat().st_size > 32_000:
                raise ReviewError("A bounded --report JSON is required")
            report = json.loads(args.report.read_text(encoding="utf-8"))
            changed = validate_proposal(root, context["head"])
            validate_report(report, context, changed)
            if args.check_remote:
                remote = git(root, "ls-remote", "--exit-code", "origin",
                             "refs/heads/" + context["branch"]).decode().split()
                if not remote or remote[0] != context["head"]:
                    raise ReviewError("Target branch advanced; this report cannot approve its new SHA")
            write_summary(context, report, changed)
        print(json.dumps({"status": "ok", "range": context}, ensure_ascii=False))
        return 0
    except (ReviewError, OSError, ValueError, subprocess.TimeoutExpired) as exc:
        message = f"文档结果：受阻\n验证与限制：{exc}"
        print(message, file=sys.stderr)
        summary = os.environ.get("GITHUB_STEP_SUMMARY")
        if summary:
            with Path(summary).open("a", encoding="utf-8") as stream:
                stream.write("\n" + message + "\n")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
