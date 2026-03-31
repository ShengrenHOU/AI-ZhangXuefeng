from __future__ import annotations

import re
import uuid
from dataclasses import dataclass
from typing import Any

from knowledge_base import KnowledgeRepository
from recommendation_core import RecommendationCore
from recommendation_core.models import FamilyConstraintSet, RecommendationRequest, StudentDossier

from .llm import ArkCodingPlanClient, PlannerAction


FOLLOW_UP_ORDER = [
    ("province", "先确认一下，你报考的是哪个省份？"),
    ("rank_or_score", "告诉我你的位次或分数，我才能继续往下收敛推荐。"),
    ("subject_combination", "你的选科组合是什么？比如物理、化学、生物。"),
    ("major_interests", "你现在更倾向哪些专业方向？可以先说一两个。"),
    ("budget", "家里一年大概能接受多少学费预算？"),
]

MISSING_FIELD_LABELS = {
    "province": "报考省份",
    "target_year": "报考年份",
    "rank_or_score": "位次或分数",
    "subject_combination": "选科组合",
    "major_interests": "专业兴趣",
    "budget": "学费预算",
    "preference_or_constraint": "至少一个偏好或约束",
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


@dataclass(slots=True)
class SessionStateMachine:
    repository: KnowledgeRepository
    recommendation_core: RecommendationCore
    planner_client: ArkCodingPlanClient | None = None
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
        }

    def handle_message(self, state: dict[str, Any], content: str) -> dict[str, Any]:
        dossier = StudentDossier(**state["dossier"])
        deterministic_patch = self._extract_patch(content)
        draft_dossier = self._merge_dossier(dossier, deterministic_patch)
        draft_readiness = self.evaluate_dossier(draft_dossier)

        planner_action = self._plan_with_live_model(
            dossier=dossier,
            user_message=content,
            missing_fields=draft_readiness["missing_fields"],
            conflicts=draft_readiness["conflicts"],
            readiness_level=draft_readiness["level"],
        )

        live_patch = self._patch_from_action(planner_action)
        patch = self._merge_patch_objects(deterministic_patch, live_patch)
        dossier = self._merge_dossier(dossier, patch)
        readiness = self.evaluate_dossier(dossier)

        action = self._resolve_action(readiness)
        next_question = self._next_question(dossier, readiness, planner_action=planner_action)
        assistant_message = self._build_assistant_message(action, readiness, planner_action, next_question)
        recommendation = None

        if action == "explain_results" and readiness["can_recommend"]:
            run = self.recommendation_core.run(
                request=RecommendationRequest(thread_id=state["thread_id"], dossier=dossier),
                programs=self.repository.load_programs(province=self.province, year=self.target_year),
                schools=self.repository.load_schools(province=self.province, year=self.target_year),
                knowledge_version=self.repository.load_manifest(province=self.province, year=self.target_year)["version"],
                model_version="mock-structured-output",
            )
            recommendation = run.model_dump()
            state_name = "result_explanation"
        elif action == "confirm_constraints":
            state_name = "constraint_confirmation"
        else:
            state_name = "follow_up_questioning"

        state["dossier"] = dossier.model_dump()
        state["state"] = state_name
        state["messages"] = state["messages"] + [
            {"role": "user", "content": content},
            {"role": "assistant", "content": assistant_message},
        ]
        return {
            "thread_id": state["thread_id"],
            "state": state_name,
            "assistant_message": assistant_message,
            "dossier": dossier.model_dump(),
            "readiness": readiness,
            "model_action": {
                "action": action,
                "dossierPatch": patch.model_dump(exclude_none=True, exclude_defaults=True),
                "nextQuestion": next_question,
                "reasoningSummary": self._reasoning_summary(planner_action, readiness, recommendation is not None),
                "sourceIds": recommendation["items"][0]["source_ids"] if recommendation and recommendation["items"] else planner_action.source_ids if planner_action else [],
                "readiness": readiness,
            },
            "recommendation": recommendation,
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
        if not self._has_preference_or_constraint(dossier):
            missing.append("preference_or_constraint")
        if not dossier.major_interests:
            missing.append("major_interests")
        if dossier.family_constraints.annual_budget_cny is None:
            missing.append("budget")

        conflicts = self._detect_conflicts(dossier)
        hard_missing = [item for item in missing if item in {"province", "target_year", "rank_or_score", "subject_combination", "preference_or_constraint"}]

        if not hard_missing and not conflicts:
            level = "ready_for_recommendation"
        elif len(hard_missing) <= 1:
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
            elif isinstance(value, list):
                updated[key] = value
            else:
                updated[key] = value
        return StudentDossier(**updated)

    def _resolve_action(self, readiness: dict[str, Any]) -> str:
        if readiness["conflicts"]:
            return "confirm_constraints"
        if readiness["can_recommend"]:
            return "explain_results"
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

    def _has_preference_or_constraint(self, dossier: StudentDossier) -> bool:
        return bool(
            dossier.major_interests
            or dossier.family_constraints.annual_budget_cny is not None
            or dossier.family_constraints.city_preference
            or dossier.family_constraints.adjustment_accepted is not None
            or dossier.risk_appetite is not None
        )

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

    def _extract_patch(self, content: str) -> StudentDossier:
        lowered = content.lower()
        patch = StudentDossier()
        constraints = FamilyConstraintSet()

        if "henan" in lowered or "河南" in content:
            patch.province = "henan"
            patch.target_year = self.target_year

        rank_match = re.search(r"(位次|rank)\s*[:：]?\s*(\d{4,6})", content, re.IGNORECASE)
        if rank_match:
            patch.rank = int(rank_match.group(2))

        score_match = re.search(r"(分数|score)\s*[:：]?\s*(\d{3})", content, re.IGNORECASE)
        if score_match:
            patch.score = int(score_match.group(2))

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

        interests: list[str] = []
        keyword_map = {
            "computer_science": ["计算机", "computer", "cs"],
            "engineering": ["电气", "工科", "automation", "engineer"],
            "education": ["师范", "教育", "teacher"],
        }
        for canonical, keywords in keyword_map.items():
            if any(keyword in lowered or keyword in content for keyword in keywords):
                interests.append(canonical)
        if interests:
            patch.major_interests = interests

        budget_match = re.search(r"(预算|学费)\s*[:：]?\s*(\d{4,5})", content)
        if budget_match:
            constraints.annual_budget_cny = int(budget_match.group(2))
        if "家里条件一般" in content:
            constraints.notes.append("family mentioned budget sensitivity")
            constraints.annual_budget_cny = constraints.annual_budget_cny or 6000
        if "离家近" in content or "near home" in lowered:
            constraints.distance_preference = "near_home"
        if "接受调剂" in content:
            constraints.adjustment_accepted = True
        if "不接受调剂" in content:
            constraints.adjustment_accepted = False

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

        if constraints.model_dump(exclude_none=True, exclude_defaults=True):
            patch.family_constraints = constraints

        if "稳" in content or "保守" in content or "conservative" in lowered:
            patch.risk_appetite = "conservative"
        elif "冲" in content or "aggressive" in lowered:
            patch.risk_appetite = "aggressive"
        elif "平衡" in content or "balanced" in lowered:
            patch.risk_appetite = "balanced"

        if content:
            patch.summary_notes = [content.strip()]
        return patch
