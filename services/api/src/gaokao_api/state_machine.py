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
    ("province", "先确认一下你报考的是哪个省份？"),
    ("rank_or_score", "告诉我你的位次或分数，我才能开始做更稳的推荐。"),
    ("subject_combination", "你的选科组合是什么？例如 physics chemistry biology。"),
    ("major_interests", "你目前更倾向哪些专业方向？"),
    ("budget", "家庭一年能接受的大概学费预算是多少？"),
]


@dataclass(slots=True)
class SessionStateMachine:
    repository: KnowledgeRepository
    recommendation_core: RecommendationCore
    planner_client: ArkCodingPlanClient | None = None
    province: str = "henan"
    target_year: int = 2026

    def initialize(self) -> dict[str, Any]:
        dossier = StudentDossier(province=self.province, target_year=self.target_year)
        return {
            "thread_id": str(uuid.uuid4()),
            "state": "entry_intent",
            "dossier": dossier.model_dump(),
            "messages": [],
        }

    def handle_message(self, state: dict[str, Any], content: str) -> dict[str, Any]:
        dossier = StudentDossier(**state["dossier"])
        deterministic_patch = self._extract_patch(content)
        draft_dossier = self._merge_dossier(dossier, deterministic_patch)
        missing_fields = self._missing_fields(draft_dossier)
        planner_action = self._plan_with_live_model(dossier=dossier, user_message=content, missing_fields=missing_fields)
        live_patch = self._patch_from_action(planner_action)
        patch = self._merge_patch_objects(deterministic_patch, live_patch)
        dossier = self._merge_dossier(dossier, patch)

        next_question = self._next_question(dossier, planner_action=planner_action)
        action = "ask_followup" if next_question else "explain_results"
        assistant_message = next_question or self._result_message(planner_action)
        recommendation = None

        if action == "explain_results":
            run = self.recommendation_core.run(
                request=RecommendationRequest(thread_id=state["thread_id"], dossier=dossier),
                programs=self.repository.load_programs(province=self.province, year=self.target_year),
                schools=self.repository.load_schools(province=self.province, year=self.target_year),
                knowledge_version=self.repository.load_manifest(province=self.province, year=self.target_year)["version"],
                model_version="mock-structured-output",
            )
            recommendation = run.model_dump()
            assistant_message = self._result_message(planner_action)
            state_name = "result_explanation"
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
            "model_action": {
                "action": action,
                "dossierPatch": patch.model_dump(exclude_none=True, exclude_defaults=True),
                "nextQuestion": next_question,
                "reasoningSummary": self._reasoning_summary(planner_action, recommendation is not None),
                "sourceIds": recommendation["items"][0]["source_ids"] if recommendation and recommendation["items"] else planner_action.source_ids if planner_action else [],
            },
            "recommendation": recommendation,
        }

    def _missing_fields(self, dossier: StudentDossier) -> list[str]:
        missing: list[str] = []
        for field_name, _ in FOLLOW_UP_ORDER:
            if field_name == "province" and not dossier.province:
                missing.append(field_name)
            elif field_name == "rank_or_score" and dossier.rank is None and dossier.score is None:
                missing.append(field_name)
            elif field_name == "subject_combination" and not dossier.subject_combination:
                missing.append(field_name)
            elif field_name == "major_interests" and not dossier.major_interests:
                missing.append(field_name)
            elif field_name == "budget" and dossier.family_constraints.annual_budget_cny is None:
                missing.append(field_name)
        return missing

    def _plan_with_live_model(self, *, dossier: StudentDossier, user_message: str, missing_fields: list[str]) -> PlannerAction | None:
        if self.planner_client is None or not self.planner_client.is_configured():
            return None
        return self.planner_client.plan_conversation_action(
            dossier=dossier.model_dump(),
            user_message=user_message,
            missing_fields=missing_fields,
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

    def _next_question(self, dossier: StudentDossier, planner_action: PlannerAction | None = None) -> str | None:
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
        return None

    def _result_message(self, planner_action: PlannerAction | None) -> str:
        if planner_action and planner_action.reasoning_summary:
            return planner_action.reasoning_summary
        return "我先按当前档案给你一版建议，后面你还可以继续补条件来重排。"

    def _reasoning_summary(self, planner_action: PlannerAction | None, has_recommendation: bool) -> str:
        if planner_action and planner_action.reasoning_summary:
            return planner_action.reasoning_summary
        if has_recommendation:
            return "The workflow collected enough dossier fields and triggered recommendation generation."
        return "The workflow updated dossier state and asked for the next required field."

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

        subjects = []
        for subject in ["physics", "chemistry", "biology", "history", "politics", "geography"]:
            if subject in lowered:
                subjects.append(subject)
        if "物理" in content:
            subjects.append("physics")
        if "化学" in content:
            subjects.append("chemistry")
        if "生物" in content:
            subjects.append("biology")
        if subjects:
            patch.subject_combination = sorted(set(subjects))

        interests = []
        keyword_map = {
            "computer_science": ["计算机", "computer", "cs"],
            "engineering": ["电气", "engineer", "automation"],
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
        cities = []
        for city in ["zhengzhou", "xinyang", "xinxiang", "郑州", "信阳", "新乡"]:
            if city in lowered or city in content:
                mapped = {"郑州": "Zhengzhou", "信阳": "Xinyang", "新乡": "Xinxiang"}.get(city, city.title())
                cities.append(mapped)
        if cities:
            constraints.city_preference = sorted(set(cities))
        if constraints.model_dump(exclude_none=True, exclude_defaults=True):
            patch.family_constraints = constraints

        if "稳" in content or "conservative" in lowered:
            patch.risk_appetite = "conservative"
        elif "冲" in content or "aggressive" in lowered:
            patch.risk_appetite = "aggressive"
        elif "平衡" in content or "balanced" in lowered:
            patch.risk_appetite = "balanced"

        if content:
            patch.summary_notes = [content.strip()]
        return patch
