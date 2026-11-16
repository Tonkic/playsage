"""Offline documentation-policy tests; git fixtures never use the project repository."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("docs_sync", ROOT / "tools/docs_sync.py")
assert SPEC is not None and SPEC.loader is not None
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


def git(root, *args):
    return subprocess.check_output(
        ["git", "-c", "core.hooksPath=/dev/null", *args], cwd=root, stderr=subprocess.PIPE
    ).decode().strip()


def save(root, name, content):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def commit(root, name, content):
    save(root, name, content)
    git(root, "add", "--", name)
    git(root, "commit", "-qm", "fixture")
    return git(root, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "-q", "--initial-branch=main")
    git(root, "config", "user.name", "Offline fixture")
    git(root, "config", "user.email", "fixture@example.invalid")
    git(root, "config", "commit.gpgsign", "false")
    git(root, "config", "core.autocrlf", "false")
    before = commit(root, "README.md", "# Example\n")
    head = commit(root, "src/example.py", "VALUE = 1\n")
    return root, before, head


def event(before, head, **extra):
    return {"before": before, "after": head, "ref": "refs/heads/main", **extra}


def report(before, head, changed=None):
    changed = changed or []
    return {"before": before, "head": head, "status": "已更新" if changed else "无需修改",
            "changed_files": changed, "reason": "已检查当前实现；内部重构不改变操作。",
            "verification": ["源码与文档静态对照"], "test_evidence": "unavailable",
            "limitations": ["项目测试及真实运行未验证。"]}


def test_multi_commit_push_uses_full_range(repo):
    root, before, head = repo
    head = commit(root, "src/second.py", "SECOND = 2\n")
    context = sync.review_range(root, event(before, head), head)
    assert context["changed_files"] == ["src/example.py", "src/second.py"]
    assert context["base"] == before


def test_new_branch_reviews_full_tree(repo):
    root, _, head = repo
    context = sync.review_range(root, event("0" * 40, head), head)
    assert context["mode"] == "new_branch_full_tree"
    assert context["changed_files"] == ["README.md", "src/example.py"]


def test_human_documentation_push_is_not_ignored(repo):
    root, _, before = repo
    head = commit(root, "README.md", "# Human edit\n")
    assert sync.review_range(root, event(before, head), head)["changed_files"] == ["README.md"]


@pytest.mark.parametrize("extra", [
    {"ref": "refs/heads/gh-aw/docs-sync/example"},
    {"ref": "refs/tags/v1"},
    {"deleted": True},
    {"before": "a" * 40},
    {"before": "main"},
    {"after": "b" * 40},
])
def test_invalid_or_agent_push_fails_closed(repo, extra):
    root, before, head = repo
    payload = event(before, head)
    payload.update(extra)
    with pytest.raises(sync.ReviewError):
        sync.review_range(root, payload, head)


def test_force_push_compares_explicit_trees(repo):
    root, before, old = repo
    git(root, "checkout", "-q", before)
    new = commit(root, "src/replacement.py", "REPLACEMENT = 1\n")
    context = sync.review_range(root, event(old, new, forced=True), new)
    assert context["changed_files"] == ["src/example.py", "src/replacement.py"]


@pytest.mark.parametrize("name", [
    "src/example.py", "tests/extra.py", "AGENTS.md", "uv.lock", "pyproject.toml",
    "tools/docs_sync.py", ".github/workflows/docs-sync.md",
    "docs/documentation-standard.md", "docs/documentation-workflow.md",
    "docs/live-ww.md", "event_packs/zzz/demo/event.yaml", "runs/evidence/frame.json",
    "data/event_memory/memory.json", "game_packs/zzz/knowledge.md",
])
def test_forbidden_proposals_are_rejected(repo, name):
    root, _, head = repo
    save(root, name, "forbidden change\n")
    with pytest.raises(sync.ReviewError, match="allowlist"):
        sync.validate_proposal(root, head)


def test_committed_and_uncommitted_docs_are_checked(repo):
    root, _, head = repo
    commit(root, "README.md", "# Updated\n")
    save(root, "docs/design.md", "# Design\n")
    assert sync.validate_proposal(root, head) == ["README.md", "docs/design.md"]


def test_deletion_is_rejected(repo):
    root, _, head = repo
    (root / "README.md").unlink()
    with pytest.raises(sync.ReviewError, match="Deleting"):
        sync.validate_proposal(root, head)


def test_renaming_source_to_document_cannot_bypass_allowlist(repo):
    root, _, head = repo
    git(root, "mv", "src/example.py", "example.md")
    with pytest.raises(sync.ReviewError, match="allowlist"):
        sync.validate_proposal(root, head)


def test_executable_index_mode_is_rejected(repo):
    root, _, head = repo
    git(root, "update-index", "--chmod=+x", "README.md")
    with pytest.raises(sync.ReviewError, match="mode|Executable"):
        sync.validate_proposal(root, head)


@pytest.mark.parametrize("link", ["missing.md", "../outside.md", "#missing-heading"])
def test_broken_links_fail(repo, link):
    root, _, head = repo
    save(root, "README.md", f"# Example\n[Bad]({link})\n")
    with pytest.raises(sync.ReviewError, match="link|heading"):
        sync.validate_proposal(root, head)


def test_unicode_heading_links_pass(repo):
    root, _, head = repo
    save(root, "README.md", "# 查看结果\n[结果](#查看结果)\n")
    assert sync.validate_proposal(root, head) == ["README.md"]


@pytest.mark.parametrize("patch", [
    {"head": "b" * 40}, {"reason": ""}, {"test_evidence": "passed"},
    {"limitations": []}, {"limitations": ["Everything passed"]},
    {"status": "已更新"}, {"verification": []}, {"changed_files": ["README.md"]},
    {"status": "受阻"},
])
def test_false_or_incomplete_reports_fail(repo, patch):
    root, before, head = repo
    context = sync.review_range(root, event(before, head), head)
    proposal = report(before, head)
    proposal.update(patch)
    with pytest.raises(sync.ReviewError):
        sync.validate_report(proposal, context, [])


def test_no_change_report_requires_reason_and_unverified_limits(repo):
    root, before, head = repo
    context = sync.review_range(root, event(before, head), head)
    sync.validate_report(report(before, head), context, [])


def test_prepare_and_guard_cli_write_commit_bound_summary(repo, tmp_path, monkeypatch):
    root, before, head = repo
    payload = tmp_path / "event.json"
    payload.write_text(json.dumps(event(before, head)), encoding="utf-8")
    output = tmp_path / "context"
    common = ["--root", str(root), "--event", str(payload), "--head", head]
    assert sync.main(["prepare", *common, "--output", str(output)]) == 0
    assert json.loads((output / "context.json").read_text())["head"] == head
    save(root, "README.md", "# Updated\n")
    proposal = tmp_path / "report.json"
    proposal.write_text(json.dumps(report(before, head, ["README.md"])), encoding="utf-8")
    summary = tmp_path / "summary.md"
    monkeypatch.setenv("GITHUB_STEP_SUMMARY", str(summary))
    assert sync.main(["guard", *common, "--report", str(proposal)]) == 0
    assert head in summary.read_text(encoding="utf-8")
    assert "未验证" in summary.read_text(encoding="utf-8")
    proposal.unlink()
    assert sync.main(["guard", *common, "--report", str(proposal)]) == 1


def test_tonkic_workflow_preserves_publication_boundary():
    workflow = yaml.safe_load((ROOT / ".github/workflows/docs-sync-tonkic.yml").read_text(
        encoding="utf-8"))
    jobs = workflow["jobs"]
    assert jobs["review"]["permissions"] == {"contents": "read"}
    assert jobs["publish"]["permissions"] == {
        "contents": "write", "pull-requests": "write"}
    review_text = (ROOT / ".github/workflows/docs-sync-tonkic.yml").read_text(encoding="utf-8")
    assert "TONKIC_API_KEY: ${{ secrets.TONKIC_API_KEY }}" in review_text
    assert "TONKIC_API_MODEL: ${{ vars.TONKIC_API_MODEL }}" in review_text
    assert "python3 -I tools/tonkic_docs_sync.py" in review_text
    assert "python3 -I tools/docs_sync.py guard" in review_text
    assert "gh pr create --draft" in review_text
    assert "COPILOT_GITHUB_TOKEN" not in review_text


def test_guard_script_cli_is_standalone():
    result = subprocess.run([sys.executable, "-I", str(ROOT / "tools/docs_sync.py"), "--help"],
                            capture_output=True, check=False)
    assert result.returncode == 0


def test_staged_forbidden_change_cannot_hide_behind_restored_worktree(repo):
    root, _, head = repo
    save(root, "src/example.py", "FORBIDDEN = True\n")
    git(root, "add", "src/example.py")
    save(root, "src/example.py", "VALUE = 1\n")
    with pytest.raises(sync.ReviewError, match="allowlist"):
        sync.validate_proposal(root, head)


def test_project_documentation_links():
    assert sync.main(["links", "--root", str(ROOT)]) == 0
