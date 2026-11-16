from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ReliquarySubstat:
    key: str
    value: float
    count: int | None = None
    step: int | None = None


@dataclass(frozen=True)
class ReliquaryRelic:
    uid: str
    set_id: str
    name: str
    slot: str
    rarity: int
    level: int
    mainstat: str
    substats: tuple[ReliquarySubstat, ...]
    preview_substats: tuple[ReliquarySubstat, ...]
    location: str
    lock: bool
    discard: bool


@dataclass(frozen=True)
class ReliquaryCharacter:
    id: str
    name: str
    path: str
    level: int
    eidolon: int


@dataclass(frozen=True)
class ReliquaryImport:
    source: str
    build: str
    version: int
    relics: tuple[ReliquaryRelic, ...]
    characters: tuple[ReliquaryCharacter, ...]


def load_reliquary_import(path: str | Path) -> ReliquaryImport:
    with open(path, "r", encoding="utf-8") as file:
        data = json.load(file)
    return parse_reliquary_import(data)


def parse_reliquary_import(data: dict[str, Any]) -> ReliquaryImport:
    relics = tuple(_parse_relic(raw) for raw in data.get("relics", []))
    _validate_unique_relic_uids(relics)
    return ReliquaryImport(
        source=str(data.get("source", "")),
        build=str(data.get("build", "")),
        version=int(data.get("version", 0)),
        relics=relics,
        characters=tuple(_parse_character(raw) for raw in data.get("characters", [])),
    )


def _parse_relic(raw: dict[str, Any]) -> ReliquaryRelic:
    return ReliquaryRelic(
        uid=str(raw["_uid"]),
        set_id=str(raw["set_id"]),
        name=str(raw.get("name", "")),
        slot=str(raw["slot"]),
        rarity=int(raw["rarity"]),
        level=int(raw["level"]),
        mainstat=str(raw["mainstat"]),
        substats=tuple(_parse_substat(sub) for sub in raw.get("substats", [])),
        preview_substats=tuple(_parse_substat(sub) for sub in raw.get("preview_substats", [])),
        location=str(raw.get("location", "")),
        # Only an explicit JSON boolean false authorizes an unlocked import.
        # Missing/null/legacy string fields must never bypass owner protection.
        lock=raw.get("lock") is not False,
        discard=bool(raw.get("discard", False)),
    )


def _parse_substat(raw: dict[str, Any]) -> ReliquarySubstat:
    return ReliquarySubstat(
        key=str(raw["key"]),
        value=float(raw["value"]),
        count=None if raw.get("count") is None else int(raw["count"]),
        step=None if raw.get("step") is None else int(raw["step"]),
    )


def _parse_character(raw: dict[str, Any]) -> ReliquaryCharacter:
    return ReliquaryCharacter(
        id=str(raw["id"]),
        name=str(raw.get("name", "")),
        path=str(raw.get("path", "")),
        level=int(raw.get("level", 0)),
        eidolon=int(raw.get("eidolon", 0)),
    )


def _validate_unique_relic_uids(relics: tuple[ReliquaryRelic, ...]) -> None:
    seen: set[str] = set()
    duplicates: set[str] = set()
    for relic in relics:
        if not relic.uid:
            raise ValueError("Reliquary relic is missing _uid")
        if relic.uid in seen:
            duplicates.add(relic.uid)
        seen.add(relic.uid)
    if duplicates:
        sample = ", ".join(sorted(duplicates)[:5])
        raise ValueError(f"Duplicate Reliquary relic _uid values: {sample}")
