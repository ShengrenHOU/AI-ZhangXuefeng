from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Literal

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


class CompareResultPayload(BaseModel):
    reasoning_summary: str
    summary: str


class ArkCodingPlanClient:
    """
    Live planner and recommendation adapter for Ark Coding Plan's OpenAI-compatible
    endpoint. The model may extract dossier updates, ask follow-up questions, and
    synthesize recommendations from published knowledge. It must not promise
    admission and should treat retrieved knowledge as the primary context.
    """

    def __init__(self) -> None:
        self.instant_model = settings.ark_instant_model or settings.ark_model
        self.deepthink_model = settings.ark_deepthink_model or settings.ark_model
        self.model = self.instant_model
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

    def retrieve_queries(
        self,
        *,
        dossier: dict[str, Any],
        user_message: str,
    ) -> RetrievalPlan:
        if self._client is None:
            return RetrievalPlan()
        # Keep the first cut conservative: derive a small query set for future web retrieval.
        fragments = []
        if dossier.get("province"):
            fragments.append(str(dossier["province"]))
        if dossier.get("target_year"):
            fragments.append(str(dossier["target_year"]))
        if dossier.get("major_interests"):
            fragments.extend(dossier["major_interests"][:2])
        if not fragments:
            return RetrievalPlan()
        query = " ".join(fragments + [user_message[:24]])
        return RetrievalPlan(queries=[query.strip()])

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
                "content": self._recommendation_prompt(),
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
            {"role": "system", "content": self._recommendation_stream_prompt()},
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
            {"role": "system", "content": self._compare_prompt()},
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
            {"role": "system", "content": self._family_summary_prompt()},
            {
                "role": "user",
                "content": json.dumps({"dossier": dossier, "recommendation": recommendation}, ensure_ascii=False),
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

    def _system_prompt(self, missing_fields: list[str]) -> str:
        return (
            "你是高考志愿助手的规划层。"
            "你必须只返回一个 JSON 对象。"
            "键名必须严格使用 snake_case：action, dossier_patch, next_question, reasoning_summary, source_ids。"
            "你不能承诺录取，也不能制造确定性结论。"
            "你只能从用户最新一句话中抽取明确支持的 dossier 字段，不要猜。"
            "如果用户信息不完整，也允许先给方向性建议，再继续补关键条件。"
            "如果存在冲突约束，优先使用 action=confirm_constraints。"
            "action 可以使用 ask_followup、directional_guidance、confirm_constraints、recommend、compare_options、refine_recommendation、explain_reasoning、refuse。"
            "next_question 必须是中文、简短、像成熟 AI 助手的追问，不要工程味。"
            "reasoning_summary 必须是中文，面向家长可读。"
            "合法 dossier_patch 字段包括 province, target_year, rank, score, subject_combination, major_interests, risk_appetite, family_constraints, summary_notes。"
            "family_constraints 可以包含 annual_budget_cny, city_preference, distance_preference, adjustment_accepted, notes。"
            f"当前缺失字段：{missing_fields}。"
            "source_ids 在规划阶段保持空数组。"
        )

    def _recommendation_prompt(self) -> str:
        return (
            "你是高考志愿助手的推荐层。"
            "你必须优先吸收 retrieved_knowledge 中的已发布知识，再结合你已有的专业判断做推荐。"
            "retrieved_knowledge.web_results 中如果有内容，也允许你参考，但要优先相信官方或高校来源。"
            "你不能承诺录取，不能使用“稳上”“包录取”这类表达。"
            "你只能从 retrieved_knowledge.candidates 中选择推荐项，不能发明新的学校或专业。"
            "你不能凭空推断考生的家庭所在地、通勤距离或未明确说出的隐含条件。"
            "如果候选中存在预算较高、位次压力大、城市冲突等问题，你应该把它们写进 risk_warnings，而不是直接忽略。"
            "你必须输出 JSON 对象，键名严格使用 snake_case：reasoning_summary, items。"
            "items 中每一项只允许包含 program_id, bucket, fit_reasons, risk_warnings, parent_summary。"
            "bucket 只能是 reach, match, safe。"
            "fit_reasons 和 risk_warnings 都要用中文短句。"
            "parent_summary 要写成家长能直接理解的自然语言。"
            "默认给出 2 到 3 条推荐；如果候选明显不足，可以少于 2 条。"
            "不要在输出文本中暴露 source_id、链接或底层工程字段。"
        )

    def _recommendation_stream_prompt(self) -> str:
        return (
            "你是高考志愿助手，正在给用户流式生成正式建议。"
            "你必须基于 retrieved_knowledge 中的已发布知识与公开网页检索结果，逐步生成一段中文建议。"
            "输出必须自然、像顾问说话，不要输出 JSON，不要暴露 source_id 或底层技术字段。"
            "必须先给结论方向，再讲原因，再点风险。"
            "不允许保证录取。"
        )

    def _compare_prompt(self) -> str:
        return (
            "你是高考志愿助手的对比层。"
            "你必须只返回 JSON，对象键名是 reasoning_summary 和 summary。"
            "summary 用中文说明两项方案的关键差异、取舍和更适合什么样的家庭偏好。"
            "不要输出技术字段，不要承诺录取。"
        )

    def _family_summary_prompt(self) -> str:
        return (
            "你是高考志愿助手的家庭沟通摘要层。"
            "请把 recommendation 整理成家长能直接拿去讨论的中文摘要，不要承诺录取，不要暴露底层技术字段。"
        )

    def _parse_json_payload(self, raw_content: str) -> dict[str, Any]:
        normalized = raw_content.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            if normalized.startswith("json"):
                normalized = normalized[4:]
            normalized = normalized.strip()
        return json.loads(normalized)
