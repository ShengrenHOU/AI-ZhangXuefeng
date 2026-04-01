from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any


PLACEHOLDER_PATTERN = re.compile(r"\{\{\s*([a-zA-Z0-9_]+)\s*\}\}")


@dataclass(frozen=True)
class RuntimePromptAsset:
    skill_id: str
    purpose: str
    model_route: str
    expected_inputs: tuple[str, ...]
    expected_outputs: tuple[str, ...]
    path: Path
    template: str

    def render(self, **context: Any) -> str:
        missing = [key for key in self.expected_inputs if key not in context]
        if missing:
            raise KeyError(f"Missing prompt context for {self.skill_id}: {missing}")

        def replace(match: re.Match[str]) -> str:
            key = match.group(1)
            value = context.get(key, "")
            if isinstance(value, (dict, list, tuple)):
                return json.dumps(value, ensure_ascii=False)
            return str(value)

        return PLACEHOLDER_PATTERN.sub(replace, self.template)


class RuntimePromptRegistry:
    def __init__(self, root: Path) -> None:
        self.root = root
        self._catalog = self._load_catalog()

    def list_assets(self) -> list[RuntimePromptAsset]:
        return list(self._catalog.values())

    def get(self, skill_id: str) -> RuntimePromptAsset:
        try:
            return self._catalog[skill_id]
        except KeyError as exc:
            raise KeyError(f"Unknown runtime prompt asset: {skill_id}") from exc

    def render(self, skill_id: str, **context: Any) -> str:
        return self.get(skill_id).render(**context)

    def _load_catalog(self) -> dict[str, RuntimePromptAsset]:
        registry_path = self.root / "registry.json"
        raw_registry = json.loads(registry_path.read_text(encoding="utf-8"))
        catalog: dict[str, RuntimePromptAsset] = {}
        for skill_id, metadata in raw_registry.items():
            template_path = self.root / metadata["path"]
            catalog[skill_id] = RuntimePromptAsset(
                skill_id=skill_id,
                purpose=metadata["purpose"],
                model_route=metadata["model_route"],
                expected_inputs=tuple(metadata.get("expected_inputs", [])),
                expected_outputs=tuple(metadata.get("expected_outputs", [])),
                path=template_path,
                template=template_path.read_text(encoding="utf-8").strip(),
            )
        return catalog
