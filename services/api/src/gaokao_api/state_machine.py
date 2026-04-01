from __future__ import annotations

import hashlib
import json
import re
import uuid
from dataclasses import dataclass
from typing import Any

from knowledge_base import KnowledgeRepository
from recommendation_core import RecommendationCore
from recommendation_core.models import FamilyConstraintSet, RecommendationDecision, RecommendationRequest, RecommendationRun, StudentDossier

from .llm import ArkCodingPlanClient, PlannerAction, RecommendationSelection
from .web_retrieval import WebRetriever


FOLLOW_UP_ORDER = [
    ("province", "先确认一下，你报考的是哪个省份？"),
    ("rank_or_score", "告诉我你的位次或分数，我才能继续往下收敛推荐。"),
    ("subject_combination", "你的选科组合是什么？比如物理、化学、生物。"),
    ("major_interests", "你现在更倾向哪些专业方向？可以先说一两个。"),
    ("budget", "家里一年大概能接受多少学费预算？"),
    ("decision_anchor", "我还想确认一个家庭决策锚点：比如更看重离家近、接受不接受调剂，或者你想偏稳一点还是偏冲一点。"),
]

MISSING_FIELD_LABELS = {
    "province": "报考省份",
    "target_year": "报考年份",
    "rank_or_score": "位次或分数",
    "subject_combination": "选科组合",
    "major_interests": "专业兴趣",
    "budget": "学费预算",
    "decision_anchor": "家庭决策偏好",
    "preference_or_constraint": "至少一个偏好或约束",
}

RECOMMENDATION_GATE_FIELDS = {
    "province",
    "target_year",
    "rank_or_score",
    "subject_combination",
    "major_interests",
    "budget",
    "decision_anchor",
}

AFFIRMATIVE_RECOMMENDATION_SIGNALS = {
    "可以",
    "是的",
    "开始推荐",
    "开始吧",
    "就按这些条件",
    "就按照这些条件",
    "按照这些条件",
    "推荐即可",
    "没问题",
    "可以开始",
    "开始正式推荐",
    "确认",
    "好的",
    "ok",
    "okay",
    "yes",
}

NEGATIVE_RECOMMENDATION_SIGNALS = {
    "不可以",
    "不行",
    "我还想改一下条件",
    "先别正式推荐",
    "先改一下",
    "等等",
    "不对",
    "还要补充",
    "先别推荐",
    "先修改",
    "not yet",
}

OUTSIDE_HENAN_CITIES = {
    "北京": "Beijing",
    "上海": "Shanghai",
    "深圳": "Shenzhen",
    "广州": "Guangzhou",
    "杭州": "Hangzhou",
    "南京": "Nanjing",
    "武汉": "Wuhan",
    "成都": "Chengdu",
    "西安": "Xi'an",
}

DISPLAY_LABELS = {
    "henan": "河南",
    "Beijing": "北京",
    "Shanghai": "上海",
    "Shenzhen": "深圳",
    "Guangzhou": "广州",
    "Hangzhou": "杭州",
    "Nanjing": "南京",
    "Wuhan": "武汉",
    "Chengdu": "成都",
    "Xi'an": "西安",
    "Zhengzhou": "郑州",
    "Xinyang": "信阳",
    "Xinxiang": "新乡",
}

SUBJECT_COMBINATION_ALIASES = {
    "物化生": ["physics", "chemistry", "biology"],
    "物化政": ["physics", "chemistry", "politics"],
    "物化地": ["physics", "chemistry", "geography"],
    "物生政": ["physics", "biology", "politics"],
    "物生地": ["physics", "biology", "geography"],
    "物政地": ["physics", "politics", "geography"],
    "史政地": ["history", "politics", "geography"],
    "史化政": ["history", "chemistry", "politics"],
    "史化地": ["history", "chemistry", "geography"],
    "史生政": ["history", "biology", "politics"],
    "史生地": ["history", "biology", "geography"],
}

KEYWORD_MAP = {
    "computer_science": ["计算机", "computer", "cs", "软件", "人工智能", "ai"],
    "engineering": ["电气", "工科", "automation", "engineer", "自动化", "机械", "电子信息"],
    "education": ["师范", "教育", "teacher"],
    "finance": ["金融", "经管", "会计", "财务"],
    "medicine": ["医学", "临床", "护理", "药学"],
}


@dataclass(slots=True)
class SessionStateMachine:
    repository: KnowledgeRepository
    recommendation_core: RecommendationCore
    planner_client: ArkCodingPlanClient | None = None
    web_retriever: WebRetriever | None = None
    province: str = "henan"
    target_year: int = 2026

    def initialize(self) -> dict[str, Any]:
        dossier = StudentDossier(province=self.province, target_year=self.target_year)
        readiness = self.evaluate_dossier(dossier)
        return {
            "thread_id": str(uuid.uuid4()),
            "state": "entry_intent",
            "dossier": dossier.model_dump(),
            "messages": [],
            "readiness": readiness,
            "pending_recommendation_confirmation": False,
            "field_provenance": {},
        }

    def handle_message(self, state: dict[str, Any], content: str) -> dict[str, Any]:
        dossier = StudentDossier(**state["dossier"])
        original_dossier = StudentDossier(**state["dossier"])
        existing_provenance = dict(state.get("field_provenance", {}))
        pending_recommendation_confirmation = bool(state.get("pending_recommendation_confirmation", False))
        cached_recommendation = state.get("recommendation")
        cached_recommendation_fingerprint = state.get("recommendation_fingerprint")
        recommendation_versions = list(state.get("recommendation_versions", []))
        task_timeline: list[dict[str, Any]] = [self._task_step("understand", "completed", "正在理解你的意图")]

        deterministic_patch, deterministic_provenance = self._extract_patch(content)
        draft_dossier = self._merge_dossier(dossier, deterministic_patch)
        draft_readiness = self.evaluate_dossier(draft_dossier)

        planner_action = self._plan_with_live_model(
            dossier=draft_dossier,
            user_message=content,
            missing_fields=draft_readiness["missing_fields"],
            conflicts=draft_readiness["conflicts"],
            readiness_level=draft_readiness["level"],
        )

        live_patch = self._patch_from_action(planner_action)
        live_provenance = self._provenance_from_patch(
            live_patch.model_dump(exclude_none=True, exclude_defaults=True),
            source="llm_patch",
        )

        patch = self._merge_patch_objects(deterministic_patch, live_patch)
        dossier = self._merge_dossier(dossier, patch)
        field_provenance = self._merge_provenance(existing_provenance, deterministic_provenance, live_provenance)
        readiness = self.evaluate_dossier(dossier)
        task_timeline.append(self._task_step("update_memory", "completed", "正在更新学生档案"))

        recommendation = None
        next_question: str | None = None
        reasoning_summary_override: str | None = None
        compare_pair = self._resolve_compare_pair(content, cached_recommendation)

        if compare_pair:
            action = "compare_options"
            state_name = "comparison_explanation"
            pending_recommendation_confirmation = False
            assistant_message = self._build_compare_message(dossier, compare_pair[0], compare_pair[1])
            next_question = "如果你还想继续缩小范围，可以直接告诉我你更看重城市、专业还是稳妥程度。"
            task_timeline.append(self._task_step("compare", "completed", "正在比较候选专业"))
        elif readiness["conflicts"]:
            action = "confirm_constraints"
            state_name = "constraint_confirmation"
            pending_recommendation_confirmation = False
            next_question = self._next_question(dossier, readiness, planner_action)
            assistant_message = next_question or readiness["conflicts"][0]["message"]
        elif pending_recommendation_confirmation and self._is_negative_confirmation(content):
            action = "ask_followup"
            state_name = "follow_up_questioning"
            pending_recommendation_confirmation = False
            next_question = "好，我们先不正式推荐。你最想先改哪一项条件？比如位次、选科、预算，或者你更在意离家近和城市本身哪个。"
            assistant_message = next_question
        elif cached_recommendation and self._is_negative_confirmation(content):
            action = "ask_followup"
            state_name = "follow_up_questioning"
            pending_recommendation_confirmation = False
            next_question = "好，我们先不沿用这版建议。你最想先改哪一项条件，或者你最想重新考虑哪个方向？"
            assistant_message = next_question
        elif pending_recommendation_confirmation and readiness["can_recommend"] and self._is_affirmation(content):
            if self._has_confirmation_relevant_change(original_dossier, dossier):
                action = "confirm_constraints"
                state_name = "constraint_confirmation"
                pending_recommendation_confirmation = True
                next_question = self._build_confirmation_prompt(dossier)
                assistant_message = "我注意到你在确认时又补充了新条件，我先按更新后的版本再和你确认一遍。\n" + next_question
            else:
                recommendation_fingerprint = self._recommendation_fingerprint(dossier)
                if cached_recommendation and cached_recommendation_fingerprint == recommendation_fingerprint:
                    recommendation = cached_recommendation
                    recommendation_summary = "你确认过的条件没有变化，我继续沿用刚才这版正式建议。"
                else:
                    recommendation, recommendation_summary, context_slice = self._run_recommendation(state["thread_id"], dossier, content)
                    task_timeline.extend(self._context_task_steps(context_slice))
                action = "explain_results"
                state_name = "result_explanation"
                pending_recommendation_confirmation = False
                field_provenance = self._merge_provenance(
                    field_provenance,
                    {key: "user_confirmed" for key in self._confirmed_paths(dossier)},
                    {},
                )
                assistant_message = recommendation_summary
                reasoning_summary_override = recommendation_summary
                if recommendation is not None:
                    recommendation_versions = self._append_recommendation_version(
                        recommendation_versions,
                        recommendation,
                        label="当前版本",
                    )
                task_timeline.append(self._task_step("recommend", "completed", "正在生成正式建议"))
        elif readiness["can_recommend"]:
            action = "confirm_constraints"
            state_name = "constraint_confirmation"
            pending_recommendation_confirmation = True
            next_question = self._build_confirmation_prompt(dossier)
            assistant_message = next_question
            task_timeline.append(self._task_step("reflect", "completed", "正在确认最新条件"))
        elif self._looks_like_recommendation_request(content):
            action = "directional_guidance"
            state_name = "directional_guidance"
            pending_recommendation_confirmation = False
            assistant_message, context_slice = self._build_directional_guidance(dossier, readiness, content)
            next_question = self._next_question(dossier, readiness, planner_action)
            task_timeline.extend(self._context_task_steps(context_slice))
            task_timeline.append(self._task_step("respond", "completed", "正在整理方向性建议"))
        else:
            action = "ask_followup"
            state_name = "follow_up_questioning"
            pending_recommendation_confirmation = False
            next_question = self._next_question(dossier, readiness, planner_action)
            assistant_message = self._build_assistant_message(action, readiness, planner_action, next_question)

        state["dossier"] = dossier.model_dump()
        state["state"] = state_name
        state["messages"] = state["messages"] + [
            {"role": "user", "content": content},
            {"role": "assistant", "content": assistant_message},
        ]
        state["pending_recommendation_confirmation"] = pending_recommendation_confirmation
        state["field_provenance"] = field_provenance
        state["recommendation"] = recommendation if recommendation is not None else cached_recommendation
        state["recommendation_versions"] = recommendation_versions
        state["task_timeline"] = task_timeline

        return {
            "thread_id": state["thread_id"],
            "state": state_name,
            "assistant_message": assistant_message,
            "dossier": dossier.model_dump(),
            "readiness": readiness,
            "pending_recommendation_confirmation": pending_recommendation_confirmation,
            "field_provenance": field_provenance,
            "recommendation_fingerprint": self._recommendation_fingerprint(dossier) if recommendation is not None else cached_recommendation_fingerprint,
            "recommendation_versions": recommendation_versions,
            "task_timeline": task_timeline,
            "model_action": {
                "action": action,
                "dossierPatch": patch.model_dump(exclude_none=True, exclude_defaults=True),
                "nextQuestion": next_question,
                "reasoningSummary": reasoning_summary_override or self._reasoning_summary(planner_action, readiness, recommendation is not None),
                "sourceIds": recommendation["items"][0]["source_ids"] if recommendation and recommendation["items"] else planner_action.source_ids if planner_action else [],
                "readiness": readiness,
            },
            "recommendation": recommendation if recommendation is not None else cached_recommendation,
        }

    def evaluate_dossier(self, dossier: StudentDossier) -> dict[str, Any]:
        missing: list[str] = []
        if not dossier.province:
            missing.append("province")
        if dossier.target_year is None:
            missing.append("target_year")
        if dossier.rank is None and dossier.score is None:
            missing.append("rank_or_score")
        if not dossier.subject_combination:
            missing.append("subject_combination")
        if not dossier.major_interests:
            missing.append("major_interests")
        if dossier.family_constraints.annual_budget_cny is None:
            missing.append("budget")
        if not self._has_decision_anchor(dossier):
            missing.append("decision_anchor")
        if not self._has_preference_or_constraint(dossier):
            missing.append("preference_or_constraint")

        conflicts = self._detect_conflicts(dossier)
        hard_missing = [item for item in missing if item in RECOMMENDATION_GATE_FIELDS]

        if not hard_missing and not conflicts:
            level = "ready_for_recommendation"
        elif len(hard_missing) <= 2:
            level = "near_ready"
        else:
            level = "insufficient_info"

        return {
            "level": level,
            "can_recommend": level == "ready_for_recommendation",
            "missing_fields": missing,
            "missing_labels": [MISSING_FIELD_LABELS.get(item, item) for item in missing],
            "conflicts": conflicts,
        }

    def _plan_with_live_model(
        self,
        *,
        dossier: StudentDossier,
        user_message: str,
        missing_fields: list[str],
        conflicts: list[dict[str, Any]],
        readiness_level: str,
    ) -> PlannerAction | None:
        if self.planner_client is None or not self.planner_client.is_configured():
            return None
        return self.planner_client.plan_conversation_action(
            dossier=dossier.model_dump(),
            user_message=user_message,
            missing_fields=missing_fields,
            conflicts=conflicts,
            readiness_level=readiness_level,
        )

    def build_recommendation_run(self, thread_id: str, dossier: StudentDossier, user_message: str = "") -> tuple[dict[str, Any], str]:
        run, summary, _ = self._run_recommendation(thread_id, dossier, user_message)
        return run, summary

    def _run_recommendation(self, thread_id: str, dossier: StudentDossier, user_message: str) -> tuple[dict[str, Any], str, dict[str, Any]]:
        knowledge_slice = self._retrieve_knowledge_slice(dossier, user_message)
        knowledge_version = knowledge_slice["knowledge_version"]

        if self.planner_client is not None and self.planner_client.is_configured():
            recommendation_selection = self.planner_client.recommend_from_knowledge(
                dossier=dossier.model_dump(),
                retrieved_knowledge=knowledge_slice,
            )
            if recommendation_selection is not None:
                model_led_run = self._materialize_recommendation_run(
                    thread_id=thread_id,
                    selection=recommendation_selection,
                    retrieved_knowledge=knowledge_slice,
                    knowledge_version=knowledge_version,
                )
                if model_led_run.items:
                    return model_led_run.model_dump(), recommendation_selection.reasoning_summary, knowledge_slice

        run = self.recommendation_core.run(
            request=RecommendationRequest(thread_id=thread_id, dossier=dossier),
            programs=self.repository.load_programs(province=self.province, year=self.target_year),
            schools=self.repository.load_schools(province=self.province, year=self.target_year),
            knowledge_version=knowledge_version,
            model_version="knowledge-first-fallback",
        )
        return run.model_dump(), "我先基于当前已发布知识和你确认过的条件，整理出一版更稳妥的建议。后面你继续补条件，我会继续帮你重排。", knowledge_slice

    def _patch_from_action(self, planner_action: PlannerAction | None) -> StudentDossier:
        if planner_action is None:
            return StudentDossier()
        try:
            return StudentDossier(**planner_action.dossier_patch)
        except Exception:
            return StudentDossier()

    def _merge_patch_objects(self, primary: StudentDossier, secondary: StudentDossier) -> StudentDossier:
        merged = primary.model_dump(exclude_none=True, exclude_defaults=True)
        secondary_data = secondary.model_dump(exclude_none=True, exclude_defaults=True)
        for key, value in secondary_data.items():
            if key == "family_constraints":
                merged_constraints = {**merged.get("family_constraints", {}), **value}
                merged["family_constraints"] = merged_constraints
            else:
                merged[key] = value
        return StudentDossier(**merged)

    def _merge_dossier(self, dossier: StudentDossier, patch: StudentDossier) -> StudentDossier:
        updated = dossier.model_dump()
        patch_data = patch.model_dump(exclude_none=True, exclude_defaults=True)
        for key, value in patch_data.items():
            if key == "family_constraints":
                merged_constraints = {**updated["family_constraints"], **value}
                updated["family_constraints"] = merged_constraints
            elif isinstance(value, list) and key == "summary_notes":
                combined = [*(updated.get(key) or []), *value]
                updated[key] = list(dict.fromkeys(combined))
            elif isinstance(value, list):
                updated[key] = value
            else:
                updated[key] = value
        return StudentDossier(**updated)

    def _retrieve_knowledge_slice(self, dossier: StudentDossier, user_message: str = "") -> dict[str, Any]:
        manifest = self.repository.load_manifest(province=self.province, year=self.target_year)
        programs = self.repository.load_programs(province=self.province, year=self.target_year)
        schools = self.repository.load_schools(province=self.province, year=self.target_year)
        sources = self.repository.load_sources(province=self.province, year=self.target_year)

        school_index = {school["school_id"]: school for school in schools}
        source_index = {source["source_id"]: source for source in sources}
        candidates: list[dict[str, Any]] = []

        for program in programs:
            required_subjects = set(program.get("subject_requirements", []))
            dossier_subjects = set(dossier.subject_combination)
            if required_subjects and not required_subjects.issubset(dossier_subjects):
                continue

            school = school_index[program["school_id"]]
            retrieval_score = self._candidate_retrieval_score(dossier, program)
            merged_source_ids = sorted(set(program.get("source_ids", []) + school.get("source_ids", [])))
            source_summaries = [
                {
                    "source_id": source_id,
                    "kind": source_index[source_id]["kind"],
                    "title": source_index[source_id]["title"],
                    "summary": source_index[source_id]["summary"],
                }
                for source_id in merged_source_ids
                if source_id in source_index
            ]

            candidates.append(
                {
                    "program_id": program["program_id"],
                    "school_id": program["school_id"],
                    "school_name": school["name"],
                    "program_name": program["name"],
                    "city": program["city"],
                    "tuition_cny": program["tuition_cny"],
                    "historical_rank": program["historical_rank"],
                    "tags": program.get("tags", []),
                    "subject_requirements": program.get("subject_requirements", []),
                    "school_tier": school.get("tier"),
                    "source_ids": merged_source_ids,
                    "source_summaries": source_summaries,
                    "retrieval_score": retrieval_score,
                }
            )

        candidates.sort(key=lambda item: item["retrieval_score"], reverse=True)
        top_candidates = candidates[:6]
        for index, candidate in enumerate(top_candidates, start=1):
            candidate["retrieval_rank"] = index
            candidate["city_label"] = DISPLAY_LABELS.get(candidate["city"], candidate["city"])

        web_results = self._retrieve_web_results(dossier, user_message)

        return {
            "province": self.province,
            "target_year": self.target_year,
            "knowledge_version": manifest["version"],
            "candidates": top_candidates,
            "web_results": web_results,
        }

    def _candidate_retrieval_score(self, dossier: StudentDossier, program: dict[str, Any]) -> float:
        score = 0.2
        tags = set(program.get("tags", []))

        if dossier.major_interests and tags.intersection(dossier.major_interests):
            score += 0.35
        if dossier.family_constraints.city_preference and program["city"] in dossier.family_constraints.city_preference:
            score += 0.18
        if dossier.family_constraints.annual_budget_cny is not None and program["tuition_cny"] <= dossier.family_constraints.annual_budget_cny:
            score += 0.08
        if dossier.family_constraints.distance_preference == "near_home" and program["city"] in {"Zhengzhou", "Xinxiang", "Xinyang"}:
            score += 0.06
        if dossier.rank is not None:
            rank_gap = abs(program["historical_rank"] - dossier.rank)
            score += max(0.0, 0.22 - min(rank_gap / 120000, 0.22))
        return round(min(score, 0.99), 3)

    def _materialize_recommendation_run(
        self,
        *,
        thread_id: str,
        selection: RecommendationSelection,
        retrieved_knowledge: dict[str, Any],
        knowledge_version: str,
    ) -> RecommendationRun:
        candidate_index = {candidate["program_id"]: candidate for candidate in retrieved_knowledge.get("candidates", [])}
        decisions: list[RecommendationDecision] = []

        for selection_item in selection.items:
            candidate = candidate_index.get(selection_item.program_id)
            if candidate is None:
                continue

            decisions.append(
                RecommendationDecision(
                    school_id=candidate["school_id"],
                    program_id=selection_item.program_id,
                    school_name=candidate["school_name"],
                    program_name=candidate["program_name"],
                    city=candidate["city_label"],
                    tuition_cny=candidate["tuition_cny"],
                    bucket=selection_item.bucket,
                    fit_reasons=selection_item.fit_reasons,
                    risk_warnings=selection_item.risk_warnings,
                    parent_summary=selection_item.parent_summary,
                    source_ids=candidate["source_ids"],
                    trace=[
                        "selection=model_led",
                        f"knowledge_version={knowledge_version}",
                        f"retrieval_rank={candidate['retrieval_rank']}",
                        f"retrieval_score={candidate['retrieval_score']}",
                        f"thread_id={thread_id}",
                    ],
                    score=float(candidate["retrieval_score"]),
                )
            )

        return RecommendationRun(
            trace_id=str(uuid.uuid4()),
            rules_version="guardrails-v0.2.0",
            knowledge_version=knowledge_version,
            model_version=self.planner_client.deepthink_model if self.planner_client and self.planner_client.is_configured() else "knowledge-first-fallback",
            items=decisions,
        )

    def _build_confirmation_prompt(self, dossier: StudentDossier) -> str:
        decision_anchor_notes: list[str] = []
        if dossier.family_constraints.distance_preference:
            decision_anchor_notes.append(self._join_labels([dossier.family_constraints.distance_preference], passthrough=True))
        if dossier.family_constraints.adjustment_accepted is not None:
            adjustment_label = "接受调剂" if dossier.family_constraints.adjustment_accepted else "不接受调剂"
            decision_anchor_notes.append(adjustment_label)
        if dossier.family_constraints.city_preference:
            decision_anchor_notes.append(f"城市偏好：{self._join_labels(dossier.family_constraints.city_preference, passthrough=True)}")
        if dossier.risk_appetite:
            decision_anchor_notes.append(f"风险偏好：{self._join_labels([dossier.risk_appetite], passthrough=True)}")

        fields = [
            f"省份：{self._join_labels([dossier.province or '待确认'], passthrough=True)}",
            f"年份：{dossier.target_year or '待确认'}",
            f"选科：{self._join_labels(dossier.subject_combination or [], subject_mode=True) or '待确认'}",
            f"专业兴趣：{self._join_labels(dossier.major_interests or [], major_mode=True) or '待确认'}",
            f"预算：{str(dossier.family_constraints.annual_budget_cny) + ' 元/年' if dossier.family_constraints.annual_budget_cny else '待确认'}",
        ]
        if dossier.rank is not None:
            fields.insert(2, f"位次：{dossier.rank}")
        elif dossier.score is not None:
            fields.insert(2, f"分数：{dossier.score}")
        if decision_anchor_notes:
            fields.append(f"当前更看重：{'；'.join(decision_anchor_notes)}")
        summary = "我先把当前条件给你复述一遍：\n" + "\n".join(fields)
        summary += "\n如果没问题，你直接回复“可以，就按这些条件开始推荐”；如果还想改，直接告诉我哪里不对。"
        return summary

    def _build_ready_summary(self, planner_action: PlannerAction | None) -> str:
        if planner_action and planner_action.reasoning_summary:
            return planner_action.reasoning_summary
        return "好的，我就按你刚刚确认过的条件开始正式推荐。"

    def _has_preference_or_constraint(self, dossier: StudentDossier) -> bool:
        return bool(
            dossier.major_interests
            or dossier.family_constraints.annual_budget_cny is not None
            or dossier.family_constraints.city_preference
            or dossier.family_constraints.adjustment_accepted is not None
            or dossier.risk_appetite is not None
        )

    def _has_decision_anchor(self, dossier: StudentDossier) -> bool:
        return bool(
            dossier.family_constraints.distance_preference
            or dossier.family_constraints.adjustment_accepted is not None
            or dossier.family_constraints.city_preference
            or dossier.risk_appetite is not None
        )

    def _resolve_action(self, readiness: dict[str, Any]) -> str:
        if readiness["conflicts"]:
            return "confirm_constraints"
        if readiness["can_recommend"]:
            return "confirm_constraints"
        return "ask_followup"

    def _next_question(self, dossier: StudentDossier, readiness: dict[str, Any], planner_action: PlannerAction | None = None) -> str | None:
        if readiness["conflicts"]:
            if planner_action and planner_action.next_question:
                return planner_action.next_question
            return readiness["conflicts"][0]["message"]

        for field_name, prompt in FOLLOW_UP_ORDER:
            if field_name == "province" and not dossier.province:
                return planner_action.next_question if planner_action and planner_action.next_question else prompt
            if field_name == "rank_or_score" and dossier.rank is None and dossier.score is None:
                return planner_action.next_question if planner_action and planner_action.next_question else prompt
            if field_name == "subject_combination" and not dossier.subject_combination:
                return planner_action.next_question if planner_action and planner_action.next_question else prompt
            if field_name == "major_interests" and not dossier.major_interests:
                return planner_action.next_question if planner_action and planner_action.next_question else prompt
            if field_name == "budget" and dossier.family_constraints.annual_budget_cny is None:
                return planner_action.next_question if planner_action and planner_action.next_question else prompt
            if field_name == "decision_anchor" and not self._has_decision_anchor(dossier):
                return planner_action.next_question if planner_action and planner_action.next_question else prompt
        if readiness["missing_fields"]:
            return f"我还差 {readiness['missing_labels'][0]}，补上这一项后我就能继续往下收敛。"
        return None

    def _build_assistant_message(
        self,
        action: str,
        readiness: dict[str, Any],
        planner_action: PlannerAction | None,
        next_question: str | None,
    ) -> str:
        guidance = self._guidance_before_recommendation(action, readiness, next_question)
        if guidance:
            return guidance
        if action in {"ask_followup", "confirm_constraints"}:
            return next_question or "我还需要再确认一项关键信息，然后才会进入正式推荐。"
        if planner_action and planner_action.reasoning_summary:
            return planner_action.reasoning_summary
        return "你的关键信息已经比较完整了，我先按当前档案给你一版结构化建议。"

    def _reasoning_summary(self, planner_action: PlannerAction | None, readiness: dict[str, Any], has_recommendation: bool) -> str:
        if planner_action and planner_action.reasoning_summary:
            return planner_action.reasoning_summary
        if has_recommendation:
            return "关键信息已经达到推荐门槛，系统已进入正式推荐流程。"
        if readiness["conflicts"]:
            return "系统检测到约束之间存在冲突，先澄清后再推荐会更稳妥。"
        return "当前信息还没成熟到可以正式推荐，我会继续通过多轮对话把关键条件补全。"

    def _is_affirmation(self, content: str) -> bool:
        if self._is_negative_confirmation(content):
            return False
        lowered = content.lower()
        return any(signal in content or signal in lowered for signal in AFFIRMATIVE_RECOMMENDATION_SIGNALS)

    def _is_negative_confirmation(self, content: str) -> bool:
        lowered = content.lower()
        return any(signal in content or signal in lowered for signal in NEGATIVE_RECOMMENDATION_SIGNALS)

    def _merge_provenance(self, existing: dict[str, str], deterministic: dict[str, str], live: dict[str, str]) -> dict[str, str]:
        merged = dict(existing)
        merged.update(deterministic)
        merged.update(live)
        return merged

    def _provenance_from_patch(self, patch_dict: dict[str, Any], source: str = "llm_patch", prefix: str = "") -> dict[str, str]:
        provenance: dict[str, str] = {}
        for key, value in patch_dict.items():
            current_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                provenance.update(self._provenance_from_patch(value, source=source, prefix=current_key))
            else:
                provenance[current_key] = source
        return provenance

    def _join_labels(
        self,
        values: list[str],
        subject_mode: bool = False,
        major_mode: bool = False,
        passthrough: bool = False,
    ) -> str:
        if not values:
            return ""
        if passthrough:
            mapping = {
                "henan": "河南",
                "near_home": "希望离家近",
                "balanced": "平衡考虑",
                "nationwide": "全国都可",
                "conservative": "偏稳",
                "aggressive": "偏冲",
                "接受调剂": "接受调剂",
                "不接受调剂": "不接受调剂",
                **DISPLAY_LABELS,
            }
            return "、".join(mapping.get(value, value) for value in values)
        if subject_mode:
            mapping = {
                "physics": "物理",
                "chemistry": "化学",
                "biology": "生物",
                "history": "历史",
                "politics": "政治",
                "geography": "地理",
            }
            return "、".join(mapping.get(value, value) for value in values)
        if major_mode:
            mapping = {
                "computer_science": "计算机 / 软件 / AI",
                "engineering": "工科 / 电气 / 自动化",
                "education": "教育 / 师范",
                "finance": "金融 / 经管",
                "medicine": "医学 / 临床 / 护理",
            }
            return "、".join(mapping.get(value, value) for value in values)
        return "、".join(values)

    def _confirmed_paths(self, dossier: StudentDossier) -> list[str]:
        paths = [
            "province" if dossier.province else "",
            "target_year" if dossier.target_year is not None else "",
            "rank" if dossier.rank is not None else "",
            "score" if dossier.score is not None else "",
            "subject_combination" if dossier.subject_combination else "",
            "major_interests" if dossier.major_interests else "",
            "family_constraints.annual_budget_cny" if dossier.family_constraints.annual_budget_cny is not None else "",
            "family_constraints.distance_preference" if dossier.family_constraints.distance_preference else "",
            "family_constraints.adjustment_accepted" if dossier.family_constraints.adjustment_accepted is not None else "",
            "family_constraints.city_preference" if dossier.family_constraints.city_preference else "",
            "risk_appetite" if dossier.risk_appetite else "",
        ]
        return [item for item in paths if item]

    def _has_confirmation_relevant_change(self, before: StudentDossier, after: StudentDossier) -> bool:
        return self._confirmation_snapshot(before) != self._confirmation_snapshot(after)

    def _confirmation_snapshot(self, dossier: StudentDossier) -> dict[str, Any]:
        return {
            "province": dossier.province,
            "target_year": dossier.target_year,
            "rank": dossier.rank,
            "score": dossier.score,
            "subject_combination": dossier.subject_combination,
            "major_interests": dossier.major_interests,
            "annual_budget_cny": dossier.family_constraints.annual_budget_cny,
            "distance_preference": dossier.family_constraints.distance_preference,
            "adjustment_accepted": dossier.family_constraints.adjustment_accepted,
            "city_preference": dossier.family_constraints.city_preference,
            "risk_appetite": dossier.risk_appetite,
        }

    def _contains_keyword(self, lowered: str, content: str, keyword: str) -> bool:
        if keyword.isascii() and any(character.isalpha() for character in keyword):
            pattern = rf"(?<![a-z]){re.escape(keyword.lower())}(?![a-z])"
            return re.search(pattern, lowered) is not None
        return keyword in lowered or keyword in content

    def _recommendation_fingerprint(self, dossier: StudentDossier) -> str:
        payload = json.dumps(
            {
                "province": dossier.province,
                "target_year": dossier.target_year,
                "rank": dossier.rank,
                "score": dossier.score,
                "subject_combination": dossier.subject_combination,
                "major_interests": dossier.major_interests,
                "family_constraints": dossier.family_constraints.model_dump(),
                "risk_appetite": dossier.risk_appetite,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
        return hashlib.sha1(payload.encode("utf-8")).hexdigest()

    def _task_step(self, step: str, status: str, label: str) -> dict[str, str]:
        return {"step": step, "status": status, "label": label}

    def _context_task_steps(self, context_slice: dict[str, Any]) -> list[dict[str, str]]:
        steps = [self._task_step("retrieve", "completed", "正在检索已发布知识")]
        if context_slice.get("web_results"):
            steps.append(self._task_step("web_search", "completed", "正在搜索最新公开信息"))
        return steps

    def _retrieve_web_results(self, dossier: StudentDossier, user_message: str) -> list[dict[str, Any]]:
        if self.web_retriever is None or self.planner_client is None or not self.planner_client.is_configured():
            return []
        retrieval_plan = self.planner_client.retrieve_queries(
            dossier=dossier.model_dump(),
            user_message=user_message,
        )
        return self.web_retriever.retrieve(retrieval_plan.queries)

    def _looks_like_recommendation_request(self, content: str) -> bool:
        triggers = ["推荐", "怎么报", "选什么专业", "选什么学校", "怎么选", "给我建议", "shortlist"]
        return any(trigger in content.lower() or trigger in content for trigger in triggers)

    def _resolve_compare_pair(self, content: str, recommendation: dict[str, Any] | None) -> tuple[dict[str, Any], dict[str, Any]] | None:
        if recommendation is None or not recommendation.get("items"):
            return None
        if not any(token in content for token in ["比较", "对比", "哪个好", "哪个更适合"]):
            return None
        items = recommendation["items"]
        if any(token in content for token in ["前两个", "前两条", "前2个", "前2条"]) and len(items) >= 2:
            return items[0], items[1]

        matched = []
        for item in items:
            if item["school_name"] in content or item["program_name"] in content:
                matched.append(item)
        unique = {item["program_id"]: item for item in matched}
        selected = list(unique.values())
        if len(selected) >= 2:
            return selected[0], selected[1]
        return None

    def _build_compare_message(self, dossier: StudentDossier, left: dict[str, Any], right: dict[str, Any]) -> str:
        if self.planner_client is not None and self.planner_client.is_configured():
            compare_payload = self.planner_client.compare_options(
                dossier=dossier.model_dump(),
                left_option=left,
                right_option=right,
            )
            if compare_payload is not None:
                return compare_payload.summary
        return (
            f"我先帮你比较一下 {left['school_name']} / {left['program_name']} 和 {right['school_name']} / {right['program_name']}。"
            f"前者目前属于“{left['bucket']}”档，后者属于“{right['bucket']}”档。"
            f"如果你更看重稳妥，先优先看 {right['school_name']} 这类风险更低的方案；"
            f"如果你更看重专业匹配或学校层次，再结合 {left['school_name']} 这类候选做取舍。"
        )

    def _build_directional_guidance(self, dossier: StudentDossier, readiness: dict[str, Any], user_message: str) -> tuple[str, dict[str, Any]]:
        knowledge_slice = self._retrieve_knowledge_slice(dossier, user_message)
        candidate_names = [
            f"{candidate['school_name']} / {candidate['program_name']}"
            for candidate in knowledge_slice.get("candidates", [])[:2]
        ]
        if candidate_names:
            candidate_text = "、".join(candidate_names)
        else:
            candidate_text = "当前知识库里更匹配的候选"
        missing = "、".join(readiness["missing_labels"][:2]) if readiness["missing_labels"] else "少量关键条件"
        guidance = (
            f"我先给你一个方向判断：按你现在已经给出的条件，我会优先从 {candidate_text} 这一类方向里继续收敛。"
            f"不过 {missing} 还会明显影响最终推荐顺序，所以我会一边给方向，一边继续把条件补全。"
        )
        if knowledge_slice.get("web_results"):
            guidance += " 我还会顺手参考一部分最新公开信息，避免只盯着本地已发布知识。"
        return guidance, knowledge_slice

    def _append_recommendation_version(self, versions: list[dict[str, Any]], recommendation: dict[str, Any], label: str) -> list[dict[str, Any]]:
        new_version = {
            "label": label,
            "trace_id": recommendation["trace_id"],
            "fingerprint": recommendation.get("trace_id"),
            "item_count": len(recommendation.get("items", [])),
        }
        existing = [version for version in versions if version.get("trace_id") != new_version["trace_id"]]
        return [new_version, *existing][:2]

    def _guidance_before_recommendation(self, action: str, readiness: dict[str, Any], next_question: str | None) -> str | None:
        if action != "ask_followup":
            return None

        missing = set(readiness["missing_fields"])
        if "subject_combination" not in missing:
            return None

        question = next_question or "你的选科组合是什么？"
        return (
            "我先回答你这个问题：如果你说的是新高考省份，常见组合通常是在“物理 / 历史”基础上，再搭配化学、生物、政治、地理形成组合。"
            "大家常说的写法一般就是“物化生、物化政、物生地、史政地”这类简称。"
            "如果你只是说“理科生”，现在通常还不够，因为真正会影响专业选择的是具体选科组合。"
            f"{question}"
        )

    def _detect_conflicts(self, dossier: StudentDossier) -> list[dict[str, str]]:
        conflicts: list[dict[str, str]] = []
        subjects = set(dossier.subject_combination)
        interests = set(dossier.major_interests)

        if ("engineering" in interests or "computer_science" in interests) and dossier.subject_combination and "physics" not in subjects:
            conflicts.append(
                {
                    "code": "subject_interest_mismatch",
                    "message": "你现在更偏向工科或计算机方向，但目前提供的选科里没有物理。我想先确认一下，你是不是还要继续优先看这些方向？",
                }
            )

        if dossier.family_constraints.distance_preference == "near_home":
            outside = [city for city in (dossier.family_constraints.city_preference or []) if city in OUTSIDE_HENAN_CITIES.values()]
            if outside:
                conflicts.append(
                    {
                        "code": "distance_city_conflict",
                        "message": f"你一方面希望离家近，另一方面又提到了 {outside[0]} 这类外省城市偏好。我先确认一下，你是更看重离家近，还是更看重城市本身？",
                    }
                )

        if dossier.family_constraints.adjustment_accepted is False and dossier.risk_appetite == "aggressive":
            conflicts.append(
                {
                    "code": "risk_adjustment_conflict",
                    "message": "你希望更冲一点，但又明确不接受调剂。这样会明显压缩可行空间。我先确认一下，你是更想保留冲刺，还是更想坚持不调剂？",
                }
            )

        return conflicts

    def _extract_patch(self, content: str) -> tuple[StudentDossier, dict[str, str]]:
        lowered = content.lower()
        patch = StudentDossier()
        constraints = FamilyConstraintSet()
        provenance: dict[str, str] = {}

        if "henan" in lowered or "河南" in content:
            patch.province = "henan"
            patch.target_year = self.target_year
            provenance["province"] = "deterministic_regex"
            provenance["target_year"] = "deterministic_regex"

        rank_match = re.search(r"(位次|排名|名次|排位|rank)[^\d]{0,6}(\d{3,6})", content, re.IGNORECASE)
        if rank_match:
            patch.rank = int(rank_match.group(2))
            provenance["rank"] = "deterministic_regex"

        score_match = re.search(r"(分数|考了|考到|score)[^\d]{0,6}(\d{3})", content, re.IGNORECASE)
        if score_match is None:
            score_match = re.search(r"(\d{3})\s*分", content)
        if score_match:
            patch.score = int(score_match.group(2) if score_match.lastindex and score_match.lastindex >= 2 else score_match.group(1))
            provenance["score"] = "deterministic_regex"

        subjects: list[str] = []
        for alias, mapped_subjects in SUBJECT_COMBINATION_ALIASES.items():
            if alias in content:
                subjects.extend(mapped_subjects)
        for subject in ["physics", "chemistry", "biology", "history", "politics", "geography"]:
            if subject in lowered:
                subjects.append(subject)
        if "物理" in content:
            subjects.append("physics")
        if "化学" in content:
            subjects.append("chemistry")
        if "生物" in content:
            subjects.append("biology")
        if "历史" in content:
            subjects.append("history")
        if "政治" in content:
            subjects.append("politics")
        if "地理" in content:
            subjects.append("geography")
        if subjects:
            patch.subject_combination = sorted(set(subjects))
            provenance["subject_combination"] = "deterministic_alias_match"

        interests: list[str] = []
        for canonical, keywords in KEYWORD_MAP.items():
            if any(self._contains_keyword(lowered, content, keyword) for keyword in keywords):
                interests.append(canonical)
        if interests:
            patch.major_interests = interests
            provenance["major_interests"] = "deterministic_keyword_match"

        budget_match = re.search(r"(预算|学费)[^\d]{0,8}(\d{4,5})", content)
        if budget_match:
            constraints.annual_budget_cny = int(budget_match.group(2))
            provenance["family_constraints.annual_budget_cny"] = "deterministic_regex"
        if constraints.annual_budget_cny is None and any(token in content for token in ["家里条件一般", "普通家庭", "预算很低", "预算不高", "学费预算很低"]):
            constraints.notes.append("family mentioned budget sensitivity")
            constraints.annual_budget_cny = 6000
            provenance["family_constraints.annual_budget_cny"] = "deterministic_keyword_match"

        if "离家近" in content or "near home" in lowered:
            constraints.distance_preference = "near_home"
            provenance["family_constraints.distance_preference"] = "deterministic_keyword_match"
        if any(token in content for token in ["走出河南", "出河南", "出省", "省外", "外省"]):
            constraints.distance_preference = "nationwide"
            provenance["family_constraints.distance_preference"] = "deterministic_keyword_match"
        if "接受调剂" in content:
            constraints.adjustment_accepted = True
            provenance["family_constraints.adjustment_accepted"] = "deterministic_keyword_match"
        if "不接受调剂" in content:
            constraints.adjustment_accepted = False
            provenance["family_constraints.adjustment_accepted"] = "deterministic_keyword_match"

        cities: list[str] = []
        local_city_map = {
            "郑州": "Zhengzhou",
            "信阳": "Xinyang",
            "新乡": "Xinxiang",
            "zhengzhou": "Zhengzhou",
            "xinyang": "Xinyang",
            "xinxiang": "Xinxiang",
        }
        for city, mapped in local_city_map.items():
            if city in lowered or city in content:
                cities.append(mapped)
        for city, mapped in OUTSIDE_HENAN_CITIES.items():
            if city in content or mapped.lower() in lowered:
                cities.append(mapped)
        if cities:
            constraints.city_preference = sorted(set(cities))
            provenance["family_constraints.city_preference"] = "deterministic_keyword_match"

        if constraints.model_dump(exclude_none=True, exclude_defaults=True):
            patch.family_constraints = constraints

        if "稳" in content or "保守" in content or "conservative" in lowered:
            patch.risk_appetite = "conservative"
            provenance["risk_appetite"] = "deterministic_keyword_match"
        elif "冲" in content or "aggressive" in lowered:
            patch.risk_appetite = "aggressive"
            provenance["risk_appetite"] = "deterministic_keyword_match"
        elif "平衡" in content or "balanced" in lowered:
            patch.risk_appetite = "balanced"
            provenance["risk_appetite"] = "deterministic_keyword_match"

        if content:
            patch.summary_notes = [content.strip()]

        return patch, provenance
