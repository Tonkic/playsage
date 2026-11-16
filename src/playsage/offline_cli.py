"""CLI surface for offline analysis; never opens a backend connection."""

import uuid
from pathlib import Path

from .evidence import (
    DEFAULT_CAPACITY,
    EvidenceContext,
    EvidenceStore,
    atomic_write,
    json_bytes,
    read_json,
    safe_path,
)
from .memory import EventMemory


def add_commands(sub):
    evidence = sub.add_parser("evidence", help="离线原图回看；不能授权实时输入")
    commands = evidence.add_subparsers(dest="evidence_command", required=True)
    for name in ("import", "history", "inspect", "pixels", "compare", "stats", "cleanup-preview"):
        command = commands.add_parser(name)
        command.add_argument("--capacity-bytes", type=int, default=DEFAULT_CAPACITY)
        if name == "import":
            command.add_argument("source", type=Path)
            command.add_argument("--run-id")
            command.add_argument("--event-id")
            command.add_argument("--package-digest")
            command.add_argument("--game-version")
            command.add_argument("--resolution", nargs=2, type=int)
        elif name == "history":
            command.add_argument("--run-id")
            command.add_argument("--event-id")
            command.add_argument("--limit", type=int, default=100)
            command.add_argument("--offset", type=int, default=0)
        elif name in {"inspect", "pixels", "compare"}:
            command.add_argument("ref")
            if name == "compare":
                command.add_argument("second")
            command.add_argument("--roi", type=int, nargs=4, metavar=("X1", "Y1", "X2", "Y2"))

    memory = sub.add_parser("memory", help="包外活动记忆；不授予 verified")
    commands = memory.add_subparsers(dest="memory_command", required=True)
    for name in ("show", "add", "update", "export"):
        command = commands.add_parser(name)
        command.add_argument("event_id")
        command.add_argument("--game-version")
        command.add_argument("--resolution", nargs=2, type=int)
        if name in {"show", "export"}:
            command.add_argument("--digest", help="查看旧包记忆，不继承为当前事实")
        else:
            command.add_argument("--file", type=Path, required=True, help="JSON 条目或局部更新")
            command.add_argument("--expected-revision", type=int, required=True)
        if name == "update":
            command.add_argument("entry_id")

    model = sub.add_parser("model", help="基于标注和证据的离线规则检查")
    commands = model.add_subparsers(dest="model_command", required=True)
    validate = commands.add_parser("validate-grid")
    validate.add_argument("file", type=Path)
    validate.add_argument("--report", action="store_true", help="保存 JSON 到 runs/reports")


def dispatch_offline(args, root):
    if args.command == "evidence":
        store = EvidenceStore(root, args.capacity_bytes)
        command = args.evidence_command
        if command == "import":
            context = EvidenceContext(event_id=args.event_id, package_digest=args.package_digest,
                                      game_version=args.game_version,
                                      resolution=args.resolution).model_dump()
            return {"frames": store.import_observation(args.source, args.run_id, context)}
        if command == "history":
            return store.history(args.run_id, args.event_id, args.limit, args.offset)
        if command == "stats":
            return store.stats()
        if command == "cleanup-preview":
            return store.cleanup_preview()
        if command == "compare":
            return store.compare(args.ref, args.second, args.roi)
        return getattr(store, command)(args.ref, args.roi)
    if args.command == "memory":
        memory = EventMemory(root, args.event_id, args.game_version, args.resolution)
        if args.memory_command in {"show", "export"}:
            return getattr(memory, args.memory_command)(args.digest)
        payload = read_json(safe_path(root, args.file))
        return memory.change(payload, args.expected_revision, getattr(args, "entry_id", None))
    if args.command == "model":
        from .rule_validation import validate_grid

        result = validate_grid(read_json(safe_path(root, args.file)), EvidenceStore(root))
        if args.report:
            path = safe_path(root, "runs", "reports", f"grid-{uuid.uuid4().hex}.json")
            atomic_write(path, json_bytes(result))
            result["report"] = str(path)
        return result
    raise ValueError("unknown offline command")
