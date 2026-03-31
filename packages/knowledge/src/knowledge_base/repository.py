from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(slots=True)
class KnowledgeRepository:
    root: Path

    @classmethod
    def from_root(cls, root: str | Path) -> "KnowledgeRepository":
        return cls(root=Path(root))

    def _version_root(self, province: str = "henan", year: int = 2026) -> Path:
        return self.root / "published" / province / str(year)

    def load_schools(self, province: str = "henan", year: int = 2026) -> list[dict[str, Any]]:
        return self._load_json(self._version_root(province, year) / "schools.json")

    def load_programs(self, province: str = "henan", year: int = 2026) -> list[dict[str, Any]]:
        return self._load_json(self._version_root(province, year) / "programs.json")

    def load_sources(self, province: str = "henan", year: int = 2026) -> list[dict[str, Any]]:
        return self._load_json(self._version_root(province, year) / "sources.json")

    def load_manifest(self, province: str = "henan", year: int = 2026) -> dict[str, Any]:
        return self._load_json(self._version_root(province, year) / "manifest.json")

    def get_source(self, source_id: str, province: str = "henan", year: int = 2026) -> dict[str, Any] | None:
        for source in self.load_sources(province=province, year=year):
            if source["source_id"] == source_id:
                return source
        return None

    def _load_json(self, path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)

