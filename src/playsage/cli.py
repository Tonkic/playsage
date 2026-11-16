import argparse
import asyncio
import json
import sys
import uuid
from pathlib import Path

import yaml

from .adapters import observe_sra, sra_session, tool_inventory
from .demo import run_demo
from .models import EventManifest, load_package
from .registry import Registry


def emit(value):
    print(json.dumps(value, ensure_ascii=False, indent=2))


def scaffold(root, game, slug, name):
    data = {
        "id": f"{game}.{slug}",
        "game": game,
        "name": name,
        "gameplay": "unknown",
        "version": "0.1.0",
        "status": "draft",
        "compatibility": {"resolution": [1920, 1080], "game_version": "unknown"},
        "execution": {"preferred_backend": "mock", "supported_backends": ["mock"]},
        "entrypoints": {"mock": {"type": "python", "path": "scripts/policy.py"}},
        "verification": {"required_scene": "replace_with_observed_goal", "fresh_screenshot": True},
        "limits": {"max_retries": 0, "timeout_seconds": 60, "max_actions": 10},
    }
    EventManifest.model_validate(data)  # Validate identifiers before using them as paths.
    target = root / "event_packs" / game / slug
    target.mkdir(parents=True, exist_ok=False)
    (target / "scripts").mkdir()
    (target / "references").mkdir()
    (target / "event.yaml").write_text(
        yaml.safe_dump(data, allow_unicode=True, sort_keys=False), encoding="utf-8"
    )
    frontmatter = yaml.safe_dump({"name": slug, "description": name}, allow_unicode=True)
    (target / "SKILL.md").write_text(
        f"---\n{frontmatter}---\n\n草稿：记录活动入口、规则、成功条件与停止条件。\n"
        "未验证，不能用于自动重放。证据放在 references/，运行记录放在 runs/。\n",
        encoding="utf-8",
    )
    (target / "scripts" / "policy.py").write_text(
        'async def run(ctx):\n    raise NotImplementedError("Draft policy requires implementation")\n',
        encoding="utf-8",
    )
    (target / "references" / "rules.md").write_text(
        "# 探索记录\n\n来源与截图：待观察\n\n规则：未知\n\n成功条件：未知\n\n失败与恢复：未知\n",
        encoding="utf-8",
    )
    return {"path": str(target.resolve()), "status": "draft"}


async def sra_command(args, root):
    async with asyncio.timeout(args.timeout):
        async with sra_session(args.url) as session:
            if args.sra_command == "probe":
                inventory = await tool_inventory(session)
                return {"endpoint": args.url, "tools": inventory, "input_enabled": False}
            return await observe_sra(session, root / "runs" / "observations" / uuid.uuid4().hex)


def parser():
    result = argparse.ArgumentParser(description="PlaySage 活动知识与回放开发工具")
    result.add_argument("--root", type=Path, default=Path.cwd(), help="项目根目录")
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("index", help="校验并索引活动包；变动标记 stale")
    check = sub.add_parser("validate", help="校验单个活动包")
    check.add_argument("path", type=Path)
    search = sub.add_parser("search", help="检索技能并报告自动重放拒绝原因")
    search.add_argument("query", nargs="?", default="")
    search.add_argument("--game", choices=["zzz", "ww", "ef", "hsr"])
    search.add_argument("--backend")
    search.add_argument("--game-version")
    search.add_argument("--resolution", type=int, nargs=2, metavar=("WIDTH", "HEIGHT"))
    for command in ("show", "history", "stale"):
        item = sub.add_parser(command)
        item.add_argument("event_id")
    new = sub.add_parser("new", help="创建未验证的活动包草稿")
    new.add_argument("game", choices=["zzz", "ww", "ef", "hsr"])
    new.add_argument("slug")
    new.add_argument("--name", required=True)
    sub.add_parser("demo", help="运行内置模拟策略，不操作游戏、不授予 verified")
    sub.add_parser("doctor", help="检查本地活动包和开发环境，不启动后端")
    sra = sub.add_parser("sra", help="SRA 只读连接")
    sra.add_argument("sra_command", choices=["probe", "observe"])
    sra.add_argument("--url", default="http://127.0.0.1:5000/mcp")
    sra.add_argument("--timeout", type=float, default=15)
    from .offline_cli import add_commands

    add_commands(sub)
    return result


def dispatch(args):
    root = args.root.resolve()
    if args.command in {"evidence", "memory", "model"}:
        from .offline_cli import dispatch_offline

        return dispatch_offline(args, root)
    if args.command == "validate":
        path = args.path if args.path.is_absolute() else root / args.path
        manifest, digest = load_package(path)
        return {"manifest": manifest.model_dump(), "digest": digest}
    if args.command == "new":
        return scaffold(root, args.game, args.slug, args.name)
    if args.command == "sra":
        if args.timeout <= 0 or args.timeout > 120:
            raise ValueError("timeout must be in (0,120]")
        return asyncio.run(sra_command(args, root))
    if args.command == "doctor":
        packages = []
        for path in sorted((root / "event_packs").glob("*/*/event.yaml")):
            manifest, _ = load_package(path.parent)
            packages.append(manifest.id)
        return {
            "python": sys.version.split()[0],
            "root": str(root),
            "packages": packages,
            "live_input_enabled": False,
            "next_check": "playsage sra probe (requires running SRA-server)",
        }
    with Registry(root / "data" / "events.sqlite") as registry:
        if args.command == "index":
            packs = root / "event_packs"
            if not packs.is_dir():
                raise ValueError("event_packs not found; pass --root or create an event with new")
            return registry.index(packs)
        if args.command == "search":
            return registry.search(
                args.query, args.game, args.backend, args.game_version, args.resolution
            )
        if args.command == "show":
            row = registry.get(args.event_id)
            row["manifest"] = json.loads(row["manifest"])
            return row
        if args.command == "history":
            return registry.history(args.event_id)
        if args.command == "stale":
            registry.mark_stale(args.event_id)
            return {"id": args.event_id, "status": "stale"}
        if args.command == "demo":
            return asyncio.run(run_demo(root, registry))
    raise ValueError("unknown command")


def main(argv=None):
    # Windows pipes otherwise use the local ANSI codepage and corrupt Chinese JSON.
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    args = parser().parse_args(argv)
    try:
        result = dispatch(args)
        emit(result)
        return 1 if isinstance(result, dict) and result.get("success") is False else 0
    except KeyboardInterrupt:
        print("Interrupted", file=sys.stderr)
        return 130
    except Exception as exc:  # noqa: BLE001 -- CLI boundary renders backend failures as JSON.
        # ExceptionGroups from MCP retain the underlying connection failure in JSON.
        def describe(error):
            nested = getattr(error, "exceptions", None)
            return {
                "type": type(error).__name__,
                "message": str(error),
                **({"causes": [describe(item) for item in nested]} if nested else {}),
            }

        print(json.dumps({"error": describe(exc)}, ensure_ascii=False), file=sys.stderr)
        return 1
