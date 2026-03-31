from __future__ import annotations

import json
from typing import Any

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

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


class PlannerAction(BaseModel):
    action: str
    dossier_patch: dict[str, Any] = Field(default_factory=dict)
    next_question: str | None = None
    reasoning_summary: str
    source_ids: list[str] = Field(default_factory=list)


class ArkCodingPlanClient:
    """
    Live planner adapter for Ark Coding Plan's OpenAI-compatible endpoint.
    The workflow remains deterministic; the model only helps with dossier extraction,
    follow-up phrasing, and user-facing reasoning summaries.
    """

    def __init__(self) -> None:
        self.model = settings.ark_model
        self.base_url = settings.ark_base_url
        self.schemas = StructuredOutputSchemas()
        self._client = OpenAI(api_key=settings.ark_api_key, base_url=self.base_url) if settings.ark_api_key and settings.enable_live_llm else None

    def is_configured(self) -> bool:
        return self._client is not None

    def plan_conversation_action(self, *, dossier: dict[str, Any], user_message: str, missing_fields: list[str]) -> PlannerAction | None:
        if self._client is None:
            return None

        messages = [
            {
                "role": "system",
                "content": self._system_prompt(missing_fields),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "current_dossier": dossier,
                        "latest_user_message": user_message,
                        "missing_fields": missing_fields,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=700,
            temperature=0.3,
            top_p=0.95,
            stream=False,
            response_format={"type": "json_object"},
        )
        raw_content = completion.choices[0].message.content or "{}"
        try:
            parsed = json.loads(raw_content)
            return PlannerAction.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError):
            return None

    def _system_prompt(self, missing_fields: list[str]) -> str:
        return (
            "You are the planning layer of a gaokao assistant. "
            "Return one JSON object only. "
            "Use snake_case keys exactly: action, dossier_patch, next_question, reasoning_summary, source_ids. "
            "Never invent school or program recommendations. "
            "Only extract fields directly supported by the user's message. "
            "If missing_fields is non-empty, prefer action=ask_followup and ask one concise question that targets the highest-priority missing field. "
            "If missing_fields is empty, use action=explain_results and summarize what the workflow should do next. "
            "Valid dossier_patch keys are province, target_year, rank, score, subject_combination, major_interests, risk_appetite, family_constraints, summary_notes. "
            "family_constraints may include annual_budget_cny, city_preference, distance_preference, adjustment_accepted, notes. "
            f"Current required missing fields list: {missing_fields}. "
            "Set source_ids to an empty list during planning because recommendation evidence is added later."
        )

