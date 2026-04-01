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

    def plan_conversation_action(
        self,
        *,
        dossier: dict[str, Any],
        user_message: str,
        missing_fields: list[str],
        conflicts: list[dict[str, Any]],
        readiness_level: str,
    ) -> PlannerAction | None:
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
                        "conflicts": conflicts,
                        "readiness_level": readiness_level,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        completion = self._client.chat.completions.create(
            model=self.model,
            messages=messages,
            max_completion_tokens=700,
            temperature=0.2,
            top_p=0.9,
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
            "你是高考志愿助手的规划层，不是最终推荐器。"
            "你必须只返回一个 JSON 对象。"
            "键名必须严格使用 snake_case：action, dossier_patch, next_question, reasoning_summary, source_ids。"
            "你不能直接给出学校或专业推荐。"
            "你不能承诺录取，也不能制造确定性结论。"
            "你只能从用户最新一句话中抽取明确支持的 dossier 字段，不要猜。"
            "推荐门槛至少需要：省份、年份、位次或分数、选科组合、专业兴趣、预算、一个家庭决策锚点。"
            "家庭决策锚点可以是：更看重离家近、是否接受调剂、城市偏好、或者风险偏好。"
            "如果还有缺失字段，优先使用 action=ask_followup。"
            "如果存在冲突约束，优先使用 action=confirm_constraints。"
            "只有缺失字段为空且冲突为空时，才允许 action=explain_results。"
            "next_question 必须是中文、简短、像成熟 AI 助手的追问，不要工程味。"
            "reasoning_summary 必须是中文，面向家长可读。"
            "合法 dossier_patch 字段包括 province, target_year, rank, score, subject_combination, major_interests, risk_appetite, family_constraints, summary_notes。"
            "family_constraints 可以包含 annual_budget_cny, city_preference, distance_preference, adjustment_accepted, notes。"
            f"当前缺失字段：{missing_fields}。"
            "source_ids 在规划阶段保持空数组。"
        )
