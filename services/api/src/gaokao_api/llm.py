from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Literal

from openai import OpenAI
from pydantic import BaseModel, Field, ValidationError

from .config import settings
from .promptpacks import RuntimePromptRegistry


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


class RecommendationSelectionItem(BaseModel):
    program_id: str
    bucket: Literal["reach", "match", "safe"]
    fit_reasons: list[str] = Field(default_factory=list)
    risk_warnings: list[str] = Field(default_factory=list)
    parent_summary: str


class RecommendationSelection(BaseModel):
    reasoning_summary: str
    items: list[RecommendationSelectionItem] = Field(default_factory=list)


class RetrievalPlan(BaseModel):
    queries: list[str] = Field(default_factory=list)


class SafetyStyleGuardResult(BaseModel):
    approved: bool = True
    revision_notes: list[str] = Field(default_factory=list)


class CompareResultPayload(BaseModel):
    reasoning_summary: str
    summary: str


class ArkCodingPlanClient:
    """
    Live planner and recommendation adapter for Ark's OpenAI-compatible endpoint.
    Runtime behavior is defined by promptpacks rather than hard-coded prompt strings.
    """

    def __init__(self) -> None:
        self.instant_model = settings.ark_instant_model or settings.ark_model
        self.deepthink_model = settings.ark_deepthink_model or settings.ark_model
        self.model = self.instant_model
        self.base_url = settings.ark_base_url
        self.schemas = StructuredOutputSchemas()
        self.promptpacks = RuntimePromptRegistry(
            settings.repo_root / "services" / "api" / "src" / "gaokao_api" / "promptpacks"
        )
        self._client = (
            OpenAI(api_key=settings.ark_api_key, base_url=self.base_url)
            if settings.ark_api_key and settings.enable_live_llm
            else None
        )

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
                "content": self._intent_router_prompt(
                    dossier=dossier,
                    missing_fields=missing_fields,
                    conflicts=conflicts,
                    readiness_level=readiness_level,
                    user_message=user_message,
                ),
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
            model=self.instant_model,
            messages=messages,
            max_completion_tokens=420,
            temperature=0.15,
            top_p=0.9,
            stream=False,
            response_format={"type": "json_object"},
        )
        raw_content = completion.choices[0].message.content or "{}"
        try:
            parsed = self._parse_json_payload(raw_content)
            return PlannerAction.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError):
            return None

    def plan_turn(
        self,
        *,
        dossier: dict[str, Any],
        user_message: str,
        missing_fields: list[str],
        conflicts: list[dict[str, Any]],
        readiness_level: str,
    ) -> PlannerAction | None:
        return self.plan_conversation_action(
            dossier=dossier,
            user_message=user_message,
            missing_fields=missing_fields,
            conflicts=conflicts,
            readiness_level=readiness_level,
        )

    def update_dossier_patch(
        self,
        *,
        dossier: dict[str, Any],
        user_message: str,
        task_timeline: list[dict[str, Any]],
    ) -> dict[str, Any]:
        if self._client is None:
            return {}

        messages = [
            {
                "role": "system",
                "content": self.promptpacks.render(
                    "dossier_updater",
                    dossier=dossier,
                    user_message=user_message,
                    task_timeline=task_timeline,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "current_dossier": dossier,
                        "latest_user_message": user_message,
                        "task_timeline": task_timeline,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        completion = self._client.chat.completions.create(
            model=self.instant_model,
            messages=messages,
            max_completion_tokens=320,
            temperature=0.1,
            top_p=0.9,
            stream=False,
            response_format={"type": "json_object"},
        )
        raw_content = completion.choices[0].message.content or "{}"
        try:
            parsed = self._parse_json_payload(raw_content)
        except json.JSONDecodeError:
            return {}

        if isinstance(parsed.get("dossier_patch"), dict):
            return parsed["dossier_patch"]
        return parsed if isinstance(parsed, dict) else {}

    def retrieve_queries(
        self,
        *,
        dossier: dict[str, Any],
        user_message: str,
    ) -> RetrievalPlan:
        if self._client is None:
            return self._fallback_retrieval_plan(dossier=dossier, user_message=user_message)

        task_plan = {"goal": "retrieve_relevant_context", "priority": "published_knowledge_then_open_web"}
        messages = [
            {
                "role": "system",
                "content": self.promptpacks.render(
                    "retrieval_planner",
                    dossier=dossier,
                    user_message=user_message,
                    task_plan=task_plan,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "dossier": dossier,
                        "user_message": user_message,
                        "task_plan": task_plan,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        completion = self._client.chat.completions.create(
            model=self.instant_model,
            messages=messages,
            max_completion_tokens=260,
            temperature=0.1,
            top_p=0.9,
            stream=False,
            response_format={"type": "json_object"},
        )
        raw_content = completion.choices[0].message.content or "{}"
        try:
            parsed = self._parse_json_payload(raw_content)
            plan = RetrievalPlan.model_validate(parsed)
            sanitized_queries = self._sanitize_external_queries(plan.queries, dossier=dossier)
            if sanitized_queries:
                return RetrievalPlan(queries=sanitized_queries)
        except (json.JSONDecodeError, ValidationError):
            pass

        return self._fallback_retrieval_plan(dossier=dossier, user_message=user_message)

    def generate_directional_guidance(
        self,
        *,
        dossier: dict[str, Any],
        missing_fields: list[str],
        conflicts: list[dict[str, Any]],
        user_message: str,
        retrieved_context: dict[str, Any],
    ) -> str | None:
        if self._client is None:
            return None

        messages = [
            {
                "role": "system",
                "content": self.promptpacks.render(
                    "directional_guidance",
                    dossier=dossier,
                    missing_fields=missing_fields,
                    conflicts=conflicts,
                    user_message=user_message,
                    retrieved_context=retrieved_context,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "dossier": dossier,
                        "missing_fields": missing_fields,
                        "conflicts": conflicts,
                        "user_message": user_message,
                        "retrieved_context": retrieved_context,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        completion = self._client.chat.completions.create(
            model=self.instant_model,
            messages=messages,
            max_completion_tokens=520,
            temperature=0.2,
            top_p=0.9,
            stream=False,
        )
        content = completion.choices[0].message.content
        return content.strip() if content else None

    def recommend_from_knowledge(
        self,
        *,
        dossier: dict[str, Any],
        retrieved_knowledge: dict[str, Any],
    ) -> RecommendationSelection | None:
        if self._client is None:
            return None

        base_messages = [
            {
                "role": "system",
                "content": self._recommendation_prompt(
                    dossier=dossier,
                    retrieved_knowledge=retrieved_knowledge,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "dossier": dossier,
                        "retrieved_knowledge": retrieved_knowledge,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        for attempt in range(2):
            messages = list(base_messages)
            if attempt == 1:
                messages.insert(
                    1,
                    {
                        "role": "system",
                        "content": "请只输出一个 JSON 对象，不要使用 markdown 代码块，也不要输出对象之外的额外解释。",
                    },
                )

            completion = self._client.chat.completions.create(
                model=self.deepthink_model,
                messages=messages,
                max_completion_tokens=1400,
                temperature=0.2 if attempt == 0 else 0.1,
                top_p=0.9,
                stream=False,
                response_format={"type": "json_object"},
            )
            raw_content = completion.choices[0].message.content or "{}"
            try:
                parsed = self._parse_json_payload(raw_content)
                return RecommendationSelection.model_validate(parsed)
            except (json.JSONDecodeError, ValidationError):
                continue

        return None

    def generate_recommendation(
        self,
        *,
        dossier: dict[str, Any],
        retrieved_knowledge: dict[str, Any],
    ) -> RecommendationSelection | None:
        return self.recommend_from_knowledge(dossier=dossier, retrieved_knowledge=retrieved_knowledge)

    def stream_recommendation_text(
        self,
        *,
        dossier: dict[str, Any],
        retrieved_knowledge: dict[str, Any],
    ) -> Iterator[str]:
        if self._client is None:
            return iter(())

        messages = [
            {
                "role": "system",
                "content": self._recommendation_stream_prompt(
                    dossier=dossier,
                    retrieved_knowledge=retrieved_knowledge,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "dossier": dossier,
                        "retrieved_knowledge": retrieved_knowledge,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        stream = self._client.chat.completions.create(
            model=self.deepthink_model,
            messages=messages,
            max_completion_tokens=900,
            temperature=0.2,
            top_p=0.9,
            stream=True,
        )

        def iterator() -> Iterator[str]:
            for chunk in stream:
                delta = chunk.choices[0].delta.content or ""
                if delta:
                    yield delta

        return iterator()

    def compare_options(
        self,
        *,
        dossier: dict[str, Any],
        left_option: dict[str, Any],
        right_option: dict[str, Any],
    ) -> CompareResultPayload | None:
        if self._client is None:
            return None

        messages = [
            {
                "role": "system",
                "content": self._compare_prompt(
                    dossier=dossier,
                    left_option=left_option,
                    right_option=right_option,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "dossier": dossier,
                        "left_option": left_option,
                        "right_option": right_option,
                    },
                    ensure_ascii=False,
                ),
            },
        ]

        completion = self._client.chat.completions.create(
            model=self.instant_model,
            messages=messages,
            max_completion_tokens=600,
            temperature=0.15,
            top_p=0.9,
            stream=False,
            response_format={"type": "json_object"},
        )
        raw_content = completion.choices[0].message.content or "{}"
        try:
            parsed = self._parse_json_payload(raw_content)
            return CompareResultPayload.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError):
            return None

    def summarize_for_family(
        self,
        *,
        dossier: dict[str, Any],
        recommendation: dict[str, Any],
    ) -> str | None:
        if self._client is None:
            return None

        messages = [
            {
                "role": "system",
                "content": self._family_summary_prompt(
                    dossier=dossier,
                    recommendation=recommendation,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {"dossier": dossier, "recommendation": recommendation},
                    ensure_ascii=False,
                ),
            },
        ]
        completion = self._client.chat.completions.create(
            model=self.deepthink_model,
            messages=messages,
            max_completion_tokens=700,
            temperature=0.2,
            top_p=0.9,
            stream=False,
        )
        return completion.choices[0].message.content

    def guard_user_facing_text(
        self,
        *,
        draft_output: str,
        model_action: str,
        user_context: dict[str, Any],
    ) -> str:
        if self._client is None or not draft_output.strip():
            return draft_output

        messages = [
            {
                "role": "system",
                "content": self.promptpacks.render(
                    "safety_style_guard",
                    draft_output=draft_output,
                    model_action=model_action,
                    user_context=user_context,
                ),
            },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "draft_output": draft_output,
                        "model_action": model_action,
                        "user_context": user_context,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        completion = self._client.chat.completions.create(
            model=self.instant_model,
            messages=messages,
            max_completion_tokens=220,
            temperature=0.1,
            top_p=0.9,
            stream=False,
            response_format={"type": "json_object"},
        )
        raw_content = completion.choices[0].message.content or "{}"
        try:
            parsed = SafetyStyleGuardResult.model_validate(self._parse_json_payload(raw_content))
        except (json.JSONDecodeError, ValidationError):
            return draft_output

        if parsed.approved or not parsed.revision_notes:
            return draft_output

        rewrite = self._client.chat.completions.create(
            model=self.instant_model,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "你是高考志愿助手的语言润色层。请只改写语言风格，不改变事实、结论和条件，"
                        "不要保证录取，不要暴露工程字段，要用平等、克制、面向中国家庭的表达。"
                    ),
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        {
                            "draft_output": draft_output,
                            "revision_notes": parsed.revision_notes,
                            "model_action": model_action,
                            "user_context": user_context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_completion_tokens=420,
            temperature=0.15,
            top_p=0.9,
            stream=False,
        )
        revised = rewrite.choices[0].message.content
        return revised.strip() if revised else draft_output

    def _intent_router_prompt(
        self,
        *,
        dossier: dict[str, Any],
        missing_fields: list[str],
        conflicts: list[dict[str, Any]],
        readiness_level: str,
        user_message: str,
    ) -> str:
        return self.promptpacks.render(
            "intent_router",
            dossier=dossier,
            missing_fields=missing_fields,
            conflicts=conflicts,
            readiness_level=readiness_level,
            user_message=user_message,
        )

    def _recommendation_prompt(
        self,
        *,
        dossier: dict[str, Any],
        retrieved_knowledge: dict[str, Any],
    ) -> str:
        return self.promptpacks.render(
            "recommendation_generator",
            dossier=dossier,
            retrieved_knowledge=retrieved_knowledge,
        )

    def _recommendation_stream_prompt(
        self,
        *,
        dossier: dict[str, Any],
        retrieved_knowledge: dict[str, Any],
    ) -> str:
        return (
            self.promptpacks.render(
                "recommendation_generator",
                dossier=dossier,
                retrieved_knowledge=retrieved_knowledge,
            )
            + "\n\n请把建议写成面向家长和学生的自然语言说明，逐步展开，不要输出 JSON，也不要暴露工程字段。"
        )

    def _compare_prompt(
        self,
        *,
        dossier: dict[str, Any],
        left_option: dict[str, Any],
        right_option: dict[str, Any],
    ) -> str:
        return self.promptpacks.render(
            "compare_generator",
            dossier=dossier,
            left_option=left_option,
            right_option=right_option,
        )

    def _family_summary_prompt(
        self,
        *,
        dossier: dict[str, Any],
        recommendation: dict[str, Any],
    ) -> str:
        return self.promptpacks.render(
            "family_summary_writer",
            dossier=dossier,
            recommendation=recommendation,
        )

    def _fallback_retrieval_plan(self, *, dossier: dict[str, Any], user_message: str) -> RetrievalPlan:
        queries = self._build_safe_external_queries(dossier)
        return RetrievalPlan(queries=queries)

    def _sanitize_external_queries(self, queries: list[str], *, dossier: dict[str, Any]) -> list[str]:
        safe_queries = self._build_safe_external_queries(dossier)
        if not safe_queries:
            return []

        allowed_tokens = {token.lower() for token in self._allowed_external_tokens(dossier)}
        sanitized: list[str] = []
        for query in queries:
            normalized = " ".join(
                token
                for token in query.split()
                if token.lower() in allowed_tokens
            ).strip()
            if normalized and normalized not in sanitized:
                sanitized.append(normalized)

        merged: list[str] = []
        for query in [*sanitized, *safe_queries]:
            if query and query not in merged:
                merged.append(query)
        return merged[:3]

    def _build_safe_external_queries(self, dossier: dict[str, Any]) -> list[str]:
        province = self._display_label(str(dossier.get("province", "")))
        year = str(dossier.get("target_year") or "").strip()
        interests = [self._major_interest_label(value) for value in dossier.get("major_interests") or []]
        subjects = [self._subject_label(value) for value in dossier.get("subject_combination") or []]
        queries: list[str] = []

        base_parts = [part for part in [province, year, "高考", "志愿", "招生"] if part]
        if base_parts:
            queries.append(" ".join(base_parts))

        if interests:
            queries.append(" ".join([part for part in [province, year, interests[0], "专业", "选科要求"] if part]))

        if subjects:
            queries.append(" ".join([part for part in [province, year, " ".join(subjects[:2]), "招生", "专业"] if part]))

        return [query for query in queries if query]

    def _allowed_external_tokens(self, dossier: dict[str, Any]) -> list[str]:
        tokens = [
            "高考",
            "志愿",
            "招生",
            "专业",
            "选科要求",
        ]
        if dossier.get("province"):
            tokens.extend([str(dossier["province"]), self._display_label(str(dossier["province"]))])
        if dossier.get("target_year"):
            tokens.append(str(dossier["target_year"]))
        tokens.extend(self._major_interest_label(value) for value in dossier.get("major_interests") or [])
        tokens.extend(self._subject_label(value) for value in dossier.get("subject_combination") or [])
        return [token for token in tokens if token]

    def _display_label(self, value: str) -> str:
        mapping = {
            "henan": "河南",
            "beijing": "北京",
            "shanghai": "上海",
            "guangzhou": "广州",
            "shenzhen": "深圳",
            "hangzhou": "杭州",
            "nanjing": "南京",
            "wuhan": "武汉",
            "chengdu": "成都",
        }
        return mapping.get(value.lower(), value)

    def _major_interest_label(self, value: str) -> str:
        mapping = {
            "computer_science": "计算机",
            "engineering": "工科",
            "education": "教育",
            "finance": "金融",
            "medicine": "医学",
        }
        return mapping.get(value, value)

    def _subject_label(self, value: str) -> str:
        mapping = {
            "physics": "物理",
            "chemistry": "化学",
            "biology": "生物",
            "history": "历史",
            "politics": "政治",
            "geography": "地理",
        }
        return mapping.get(value, value)

    def _parse_json_payload(self, raw_content: str) -> dict[str, Any]:
        normalized = raw_content.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            if normalized.startswith("json"):
                normalized = normalized[4:]
            normalized = normalized.strip()
        return json.loads(normalized)
