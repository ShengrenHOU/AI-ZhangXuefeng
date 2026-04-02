from __future__ import annotations

import json
from datetime import UTC, datetime
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

    def _draft_root(self, province: str = "henan", year: int = 2026) -> Path:
        return self.root / "draft" / province / str(year)

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

    def append_draft_discoveries(
        self,
        *,
        province: str,
        year: int,
        records: list[dict[str, Any]],
    ) -> Path | None:
        if not records:
            return None
        draft_root = self._draft_root(province=province, year=year) / "auto-discovery"
        draft_root.mkdir(parents=True, exist_ok=True)
        path = draft_root / "discovered-candidates.jsonl"
        timestamp = datetime.now(UTC).isoformat()
        with path.open("a", encoding="utf-8") as handle:
            for record in records:
                payload = {"captured_at": timestamp, **record}
                handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        return path

    def _load_json(self, path: Path) -> Any:
        with path.open("r", encoding="utf-8") as handle:
            return json.load(handle)
