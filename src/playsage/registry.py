"""SQLite index. Declaring 'verified' in a YAML file never grants replay permission."""

import json
import sqlite3
from pathlib import Path

from .models import is_redirect, load_package


class Registry:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id TEXT PRIMARY KEY, path TEXT NOT NULL UNIQUE, digest TEXT NOT NULL,
                manifest TEXT NOT NULL, status TEXT NOT NULL,
                indexed_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
            CREATE TABLE IF NOT EXISTS runs (
                id TEXT PRIMARY KEY, event_id TEXT NOT NULL, digest TEXT NOT NULL,
                mode TEXT NOT NULL, success INTEGER NOT NULL, trace_path TEXT NOT NULL,
                created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
            );
        """)

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.db.close()

    def index(self, packs: Path) -> list[dict]:
        # Validate everything before modifying the index; duplicate IDs are errors.
        packages = []
        ids = set()
        for path in sorted(packs.glob("*/*/event.yaml")):
            if is_redirect(path.parent.parent) or not path.resolve().is_relative_to(
                packs.resolve()
            ):
                raise ValueError(f"package must stay inside event_packs: {path}")
            manifest, digest = load_package(path.parent)
            if manifest.id in ids:
                raise ValueError(f"duplicate event id: {manifest.id}")
            ids.add(manifest.id)
            packages.append((path.parent.resolve(), manifest, digest))
        result = []
        with self.db:
            # Delete removed IDs first so a renamed package may reuse its original path.
            for row in self.db.execute("SELECT id FROM events").fetchall():
                if row["id"] not in ids:
                    self.db.execute("DELETE FROM events WHERE id=?", (row["id"],))
            for root, manifest, digest in packages:
                previous = self.db.execute(
                    "SELECT * FROM events WHERE id=?", (manifest.id,)
                ).fetchone()
                status = manifest.status
                if status == "verified":
                    status = (
                        "candidate"  # Promotion requires evidence; not yet implemented for live.
                    )
                if previous and (previous["digest"] != digest or previous["status"] == "stale"):
                    status = "stale"
                self.db.execute(
                    """
                    INSERT INTO events(id,path,digest,manifest,status) VALUES(?,?,?,?,?)
                    ON CONFLICT(id) DO UPDATE SET path=excluded.path,digest=excluded.digest,
                    manifest=excluded.manifest,status=excluded.status,indexed_at=CURRENT_TIMESTAMP
                """,
                    (manifest.id, str(root), digest, manifest.model_dump_json(), status),
                )
                result.append({"id": manifest.id, "status": status, "digest": digest})
        return result

    def get(self, event_id: str) -> dict:
        row = self.db.execute("SELECT * FROM events WHERE id=?", (event_id,)).fetchone()
        if row is None:
            raise ValueError(f"event not indexed: {event_id}; run index first")
        return dict(row)

    def search(self, query="", game=None, backend=None, game_version=None, resolution=None):
        results = []
        for row in self.db.execute("SELECT * FROM events ORDER BY id"):
            data = dict(row)
            manifest = json.loads(data.pop("manifest"))
            if game and manifest["game"] != game:
                continue
            if (
                query.casefold()
                not in " ".join([manifest["id"], manifest["name"], manifest["gameplay"]]).casefold()
            ):
                continue
            reasons = []
            try:
                _, digest = load_package(Path(data["path"]))
                if digest != data["digest"]:
                    reasons.append("package_changed")
                    data["status"] = "stale"
            except (OSError, ValueError):
                reasons.append("package_unavailable_or_invalid")
                data["status"] = "stale"
            if data["status"] != "verified":
                reasons.append("not_verified")
            if backend is None:
                reasons.append("backend_unspecified")
            elif backend not in manifest["execution"]["supported_backends"]:
                reasons.append("backend_unsupported")
            expected = manifest["compatibility"]
            if (
                not game_version
                or game_version == "unknown"
                or expected["game_version"] == "unknown"
            ):
                reasons.append("game_version_unknown")
            elif game_version != expected["game_version"]:
                reasons.append("game_version_mismatch")
            if resolution is None:
                reasons.append("resolution_unspecified")
            elif list(resolution) != expected["resolution"]:
                reasons.append("resolution_mismatch")
            results.append(
                {
                    **data,
                    "name": manifest["name"],
                    "game": manifest["game"],
                    "replay_allowed": not reasons,
                    "rejection_reasons": reasons,
                }
            )
        return results

    def mark_stale(self, event_id: str):
        self.get(event_id)
        with self.db:
            self.db.execute("UPDATE events SET status='stale' WHERE id=?", (event_id,))

    def record_run(self, result: dict):
        with self.db:
            self.db.execute(
                "INSERT INTO runs VALUES(?,?,?,?,?,?,CURRENT_TIMESTAMP)",
                (
                    result["run_id"],
                    result["event_id"],
                    result["digest"],
                    result["mode"],
                    int(result["success"]),
                    result["trace_path"],
                ),
            )

    def history(self, event_id: str):
        return [
            dict(row)
            for row in self.db.execute(
                "SELECT * FROM runs WHERE event_id=? ORDER BY created_at,id", (event_id,)
            )
        ]
