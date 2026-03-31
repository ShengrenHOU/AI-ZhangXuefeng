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


class XiaomiMimoChatClient:
    """
    Phase 1 keeps the live call optional.
    This adapter is the stable seam for Xiaomi MiMo's OpenAI-compatible chat API.
    """

    def __init__(self) -> None:
        self.model = settings.mimo_model
        self.base_url = settings.mimo_base_url
        self.schemas = StructuredOutputSchemas()
        self._client = OpenAI(api_key=settings.mimo_api_key, base_url=self.base_url) if settings.mimo_api_key else None

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
