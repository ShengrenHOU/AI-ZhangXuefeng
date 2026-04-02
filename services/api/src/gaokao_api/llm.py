from __future__ import annotations

import json
import re
import uuid
from collections.abc import Iterator
from typing import Any, Literal
from urllib.parse import urlparse

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


class DiscoveredCandidate(BaseModel):
    school_id: str = ""
    program_id: str = ""
    school_name: str
    program_name: str
    city: str
    tuition_cny: int | None = None
    subject_requirements: list[str] = Field(default_factory=list)
    historical_rank: int | None = None
    tags: list[str] = Field(default_factory=list)
    source_ids: list[str] = Field(default_factory=list)
    evidence_summary: str
    source_urls: list[str] = Field(default_factory=list)
    source_summaries: list[dict[str, Any]] = Field(default_factory=list)
    retrieval_score: float = 0.0


class CandidateDiscoveryResult(BaseModel):
    reasoning_summary: str
    candidates: list[DiscoveredCandidate] = Field(default_factory=list)


class DraftKnowledgePayload(BaseModel):
    draft_id: str
    thread_id: str
    province: str
    target_year: int
    school_name: str
    program_name: str
    source_title: str
    source_url: str
    source_domain: str
    evidence_summary: str
    tuition_cny: int | None = None
    historical_rank: int | None = None
    subject_requirements: list[str] = Field(default_factory=list)
    payload: dict[str, Any] = Field(default_factory=dict)
    status: str = "draft"


class SafetyStyleGuardResult(BaseModel):
    approved: bool = True
    revision_notes: list[str] = Field(default_factory=list)


class CompareResultPayload(BaseModel):
    reasoning_summary: str
    summary: str


class ArkCodingPlanClient:
    def __init__(self) -> None:
        self.instant_model = settings.ark_instant_model or settings.ark_model
        self.deepthink_model = settings.ark_deepthink_model or settings.ark_model
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
                "content": self.promptpacks.render(
                    "intent_router",
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
        return self._json_chat(messages, PlannerAction, model=self.instant_model, max_tokens=420, temperature=0.15)

    def plan_turn(self, **kwargs: Any) -> PlannerAction | None:
        return self.plan_conversation_action(**kwargs)

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
        payload = self._json_chat(messages, dict, model=self.instant_model, max_tokens=320, temperature=0.1)
        if not payload:
            return {}
        if isinstance(payload.get("dossier_patch"), dict):
            return payload["dossier_patch"]
        return payload

    def retrieve_queries(
        self,
        *,
        dossier: dict[str, Any],
        user_message: str,
    ) -> RetrievalPlan:
        if self._client is None:
            return self._fallback_retrieval_plan(dossier)
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
        plan = self._json_chat(messages, RetrievalPlan, model=self.instant_model, max_tokens=260, temperature=0.1)
        if plan and plan.queries:
            sanitized = self._sanitize_external_queries(plan.queries, dossier=dossier)
            if sanitized:
                return RetrievalPlan(queries=sanitized)
        return self._fallback_retrieval_plan(dossier)

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

    def discover_candidates_via_web(
        self,
        *,
        thread_id: str,
        dossier: dict[str, Any],
        user_message: str,
        retrieved_knowledge: dict[str, Any],
        fallback_web_results: list[dict[str, Any]],
    ) -> CandidateDiscoveryResult:
        if self._client is None or not settings.enable_web_retrieval:
            return CandidateDiscoveryResult(reasoning_summary="web discovery disabled", candidates=[])

        native = self._discover_candidates_via_native_web_search(
            thread_id=thread_id,
            dossier=dossier,
            user_message=user_message,
            retrieved_knowledge=retrieved_knowledge,
        )
        if native and native.candidates:
            return native
        if not fallback_web_results:
            return CandidateDiscoveryResult(reasoning_summary="no fallback web results", candidates=[])
        return self._discover_candidates_via_fallback_web_context(
            thread_id=thread_id,
            dossier=dossier,
            user_message=user_message,
            retrieved_knowledge=retrieved_knowledge,
        )

    def extract_web_evidence_for_draft(
        self,
        *,
        thread_id: str,
        dossier: dict[str, Any],
        discovered: CandidateDiscoveryResult,
    ) -> list[dict[str, Any]]:
        if not settings.enable_draft_writeback:
            return []
        province = str(dossier.get("province") or settings.province)
        target_year = int(dossier.get("target_year") or settings.target_year)
        records: list[dict[str, Any]] = []
        for candidate in discovered.candidates:
            source_url = candidate.source_urls[0] if candidate.source_urls else ""
            source_domain = self._source_domain(source_url)
            source_title = candidate.source_summaries[0]["title"] if candidate.source_summaries else f"{candidate.school_name} {candidate.program_name}"
            digest = hashlib.sha1(f"{thread_id}:{candidate.program_id}:{source_url}".encode("utf-8")).hexdigest()[:12]
            records.append(
                DraftKnowledgePayload(
                    draft_id=f"draft-{province}-{target_year}-{digest}",
                    thread_id=thread_id,
                    province=province,
                    target_year=target_year,
                    school_name=candidate.school_name,
                    program_name=candidate.program_name,
                    source_title=source_title,
                    source_url=source_url,
                    source_domain=source_domain,
                    evidence_summary=candidate.evidence_summary,
                    tuition_cny=candidate.tuition_cny,
                    historical_rank=candidate.historical_rank,
                    subject_requirements=candidate.subject_requirements,
                    payload=candidate.model_dump(),
                ).model_dump()
            )
        return records

    def recommend_from_knowledge(
        self,
        *,
        dossier: dict[str, Any],
        retrieved_knowledge: dict[str, Any],
    ) -> RecommendationSelection | None:
        if self._client is None:
            return None
        messages = [
            {
                "role": "system",
                "content": self.promptpacks.render(
                    "recommendation_generator",
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
        return self._json_chat(messages, RecommendationSelection, model=self.deepthink_model, max_tokens=1400, temperature=0.2)

    def generate_recommendation(self, **kwargs: Any) -> RecommendationSelection | None:
        return self.recommend_from_knowledge(**kwargs)

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
                "content": self.promptpacks.render(
                    "recommendation_generator",
                    dossier=dossier,
                    retrieved_knowledge=retrieved_knowledge,
                )
                + "\n\n请把建议写成面向家长和学生的自然语言说明，逐步展开，不要输出 JSON。",
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
                "content": self.promptpacks.render(
                    "compare_generator",
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
        return self._json_chat(messages, CompareResultPayload, model=self.instant_model, max_tokens=600, temperature=0.15)

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
                "content": self.promptpacks.render(
                    "family_summary_writer",
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
        result = self._json_chat(messages, SafetyStyleGuardResult, model=self.instant_model, max_tokens=220, temperature=0.1)
        if not result or result.approved or not result.revision_notes:
            return draft_output
        rewrite = self._chat_text(
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
                            "revision_notes": result.revision_notes,
                            "model_action": model_action,
                            "user_context": user_context,
                        },
                        ensure_ascii=False,
                    ),
                },
            ],
            max_completion_tokens=420,
            temperature=0.15,
        )
        return rewrite.strip() if rewrite else draft_output

    def _chat_text(
        self,
        *,
        model: str,
        messages: list[dict[str, Any]],
        max_completion_tokens: int,
        temperature: float,
    ) -> str | None:
        if self._client is None:
            return None
        completion = self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_completion_tokens,
            temperature=temperature,
            top_p=0.9,
            stream=False,
        )
        content = completion.choices[0].message.content
        return content.strip() if content else None

    def _discover_candidates_via_native_web_search(
        self,
        *,
        thread_id: str,
        dossier: dict[str, Any],
        user_message: str,
        retrieved_knowledge: dict[str, Any],
    ) -> CandidateDiscoveryResult:
        if self._client is None or not settings.prefer_native_web_search:
            return CandidateDiscoveryResult(reasoning_summary="native web search disabled", candidates=[])
        try:
            response = self._client.responses.create(
                model=self.deepthink_model,
                input=[
                    {
                        "role": "system",
                        "content": [
                            {
                                "type": "input_text",
                                "text": (
                                    "你是高考志愿助手的候选发现层。请使用 web search 寻找与用户条件相关的学校和专业候选。"
                                    "最后只输出 JSON，对象键为 reasoning_summary 和 candidates。"
                                ),
                            }
                        ],
                    },
                    {
                        "role": "user",
                        "content": [
                            {
                                "type": "input_text",
                                "text": json.dumps(
                                    {
                                        "thread_id": thread_id,
                                        "dossier": dossier,
                                        "user_message": user_message,
                                        "retrieved_knowledge": retrieved_knowledge,
                                    },
                                    ensure_ascii=False,
                                ),
                            }
                        ],
                    },
                ],
                tools=[{"type": "web_search_preview"}],
            )
            text = self._response_output_text(response)
            if not text:
                return CandidateDiscoveryResult(reasoning_summary="native web search returned empty", candidates=[])
            parsed = self._parse_json_payload(text)
            result = CandidateDiscoveryResult.model_validate(parsed)
            return self._assign_candidate_ids(result)
        except Exception:
            return CandidateDiscoveryResult(reasoning_summary="native web search unavailable", candidates=[])

    def _discover_candidates_via_fallback_web_context(
        self,
        *,
        thread_id: str,
        dossier: dict[str, Any],
        user_message: str,
        retrieved_knowledge: dict[str, Any],
    ) -> CandidateDiscoveryResult:
        if self._client is None or not retrieved_knowledge.get("web_results"):
            return CandidateDiscoveryResult(reasoning_summary="no web context", candidates=[])
        messages = [
            {
                "role": "system",
                    "content": (
                        "你是高考志愿助手的开放检索候选发现层。"
                        "请根据 dossier、已发布知识摘要和网页检索结果，抽取值得进入 recommendation 的候选。"
                        "只输出 JSON，对象键为 reasoning_summary 和 candidates。"
                    ),
                },
            {
                "role": "user",
                "content": json.dumps(
                    {
                        "thread_id": thread_id,
                        "dossier": dossier,
                        "user_message": user_message,
                        "retrieved_knowledge": retrieved_knowledge,
                    },
                    ensure_ascii=False,
                ),
            },
        ]
        result = self._json_chat(messages, CandidateDiscoveryResult, model=self.deepthink_model, max_tokens=1200, temperature=0.2)
        if not result:
            return CandidateDiscoveryResult(reasoning_summary="web fallback unavailable", candidates=[])
        return self._assign_candidate_ids(result)

    def _assign_candidate_ids(self, result: CandidateDiscoveryResult) -> CandidateDiscoveryResult:
        normalized: list[DiscoveredCandidate] = []
        for candidate in result.candidates:
            school_slug = self._slug(candidate.school_name or "unknown-school")
            program_slug = self._slug(candidate.program_name or "unknown-program")
            source_url = candidate.source_urls[0] if candidate.source_urls else ""
            digest = hashlib.sha1(f"{school_slug}:{program_slug}:{source_url}".encode("utf-8")).hexdigest()[:10]
            source_id = f"web-src-{digest}"
            source_domain = self._source_domain(source_url)
            source_title = f"{candidate.school_name} {candidate.program_name}".strip()
            normalized.append(
                candidate.model_copy(
                    update={
                        "school_id": candidate.school_id or f"web-school-{school_slug}",
                        "program_id": candidate.program_id or f"web-{school_slug}-{program_slug}-{digest}",
                        "source_ids": candidate.source_ids or [source_id],
                        "source_summaries": candidate.source_summaries
                        or [
                            {
                                "source_id": source_id,
                                "kind": "web_evidence",
                                "title": source_title,
                                "summary": candidate.evidence_summary,
                                "url": source_url,
                                "domain": source_domain,
                            }
                        ],
                        "retrieval_score": candidate.retrieval_score or 0.32,
                    }
                )
            )
        return CandidateDiscoveryResult(reasoning_summary=result.reasoning_summary, candidates=normalized)

    def _json_chat(
        self,
        messages: list[dict[str, Any]],
        schema: type[BaseModel] | type[dict],
        *,
        model: str,
        max_tokens: int,
        temperature: float,
    ):
        if self._client is None:
            return None
        completion = self._client.chat.completions.create(
            model=model,
            messages=messages,
            max_completion_tokens=max_tokens,
            temperature=temperature,
            top_p=0.9,
            stream=False,
            response_format={"type": "json_object"},
        )
        raw_content = completion.choices[0].message.content or "{}"
        try:
            parsed = self._parse_json_payload(raw_content)
            if schema is dict:
                return parsed
            return schema.model_validate(parsed)
        except (json.JSONDecodeError, ValidationError):
            return None

    def _fallback_retrieval_plan(self, dossier: dict[str, Any]) -> RetrievalPlan:
        queries = self._build_safe_external_queries(dossier)
        return RetrievalPlan(queries=queries)

    def _sanitize_external_queries(self, queries: list[str], *, dossier: dict[str, Any]) -> list[str]:
        safe_queries = self._build_safe_external_queries(dossier)
        if not safe_queries:
            return []
        allowed_tokens = {token.lower() for token in self._allowed_external_tokens(dossier)}
        sanitized: list[str] = []
        for query in queries:
            normalized = " ".join(token for token in query.split() if token.lower() in allowed_tokens).strip()
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
        tokens = ["高考", "志愿", "招生", "专业", "选科要求"]
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

    def _source_domain(self, url: str) -> str:
        return urlparse(url).netloc.lower()

    def _slug(self, value: str) -> str:
        lowered = value.lower().strip()
        lowered = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", lowered)
        lowered = lowered.strip("-")
        return lowered or "unknown"

    def _response_output_text(self, response: Any) -> str:
        output_text = getattr(response, "output_text", "") or ""
        if output_text:
            return output_text
        output = getattr(response, "output", []) or []
        chunks: list[str] = []
        for item in output:
            for content in getattr(item, "content", []) or []:
                text = getattr(content, "text", None)
                if text:
                    chunks.append(text)
        return "".join(chunks)

    def _parse_json_payload(self, raw_content: str) -> dict[str, Any]:
        normalized = raw_content.strip()
        if normalized.startswith("```"):
            normalized = normalized.strip("`")
            if normalized.startswith("json"):
                normalized = normalized[4:]
            normalized = normalized.strip()
        return json.loads(normalized)
