from __future__ import annotations

from dataclasses import dataclass

from .reliquary import ReliquaryImport


@dataclass(frozen=True)
class RelicSetInfo:
    id: str
    name: str


@dataclass(frozen=True)
class GameDataCatalog:
    relic_sets: dict[str, RelicSetInfo]

    @classmethod
    def from_reliquary_import(cls, archive: ReliquaryImport) -> GameDataCatalog:
        sets: dict[str, RelicSetInfo] = {}
        for relic in archive.relics:
            sets.setdefault(relic.set_id, RelicSetInfo(id=relic.set_id, name=relic.name))
        return cls(relic_sets=sets)

    def set_name(self, set_id: str) -> str | None:
        info = self.relic_sets.get(set_id)
        if info is None:
            return None
        return info.name

    def unknown_target_sets(self, target_set_ids: set[str]) -> set[str]:
        return {set_id for set_id in target_set_ids if set_id not in self.relic_sets}

