from __future__ import annotations

import json
from typing import Any

from openai import OpenAI

from .config import settings


class StructuredOutputSchemas:
    def __init__(self) -> None:
        self._schema_root = settings.repo_root / "packages" / "types" / "schemas"

    def conversation_action(self) -> dict[str, Any]:
        return self._load("conversation-action.schema.json")

    def recommendation_run(self) -> dict[str, Any]:
        return self._load("recommendation-run.schema.json")

    def _load(self, name: str) -> dict[str, Any]:
        path = self._schema_root / name
        return json.loads(path.read_text(encoding="utf-8"))


class ArkCodingPlanClient:
    """
    Phase 1 keeps the live call optional.
    This adapter is the stable seam for Ark Coding Plan's OpenAI-compatible coding endpoint.
    """

    def __init__(self) -> None:
        self.model = settings.ark_model
        self.base_url = settings.ark_base_url
        self.schemas = StructuredOutputSchemas()
        self._client = OpenAI(api_key=settings.ark_api_key, base_url=self.base_url) if settings.ark_api_key else None

    def is_configured(self) -> bool:
        return self._client is not None

    def build_chat_payload(self, messages: list[dict[str, Any]], max_completion_tokens: int = 1024) -> dict[str, Any]:
        return {
            "model": self.model,
            "messages": messages,
            "max_completion_tokens": max_completion_tokens,
            "temperature": 0.3,
            "top_p": 0.95,
            "stream": False,
        }
