from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any

from .models import RecommendationDecision, RecommendationRequest, RecommendationRun


@dataclass(slots=True)
class RecommendationCore:
    rules_version: str = "rules-v0.1.0"

    def run(
        self,
        request: RecommendationRequest,
        programs: list[dict[str, Any]],
        schools: list[dict[str, Any]],
        knowledge_version: str,
        model_version: str = "deterministic",
    ) -> RecommendationRun:
        school_index = {school["school_id"]: school for school in schools}
        decisions: list[RecommendationDecision] = []

        for program in programs:
            eligible, reasons = self._check_eligibility(request, program)
            if not eligible:
                continue

            score = self._score_candidate(request, program)
            bucket = self._classify_bucket(request, program)
            risks = self._build_risks(request, program)
            school = school_index[program["school_id"]]
            fit_reasons = reasons + self._build_fit_reasons(request, program, school)
            trace = [
                f"eligibility=pass:{';'.join(reasons)}",
                f"bucket={bucket}",
                f"score={score:.3f}",
                f"rules_version={self.rules_version}",
            ]
            decisions.append(
                RecommendationDecision(
                    school_id=program["school_id"],
                    program_id=program["program_id"],
                    school_name=school["name"],
                    program_name=program["name"],
                    city=program["city"],
                    tuition_cny=program["tuition_cny"],
                    bucket=bucket,
                    fit_reasons=fit_reasons,
                    risk_warnings=risks,
                    parent_summary=self._build_parent_summary(program["name"], school["name"], bucket, risks),
                    source_ids=program["source_ids"],
                    trace=trace,
                    score=score,
                )
            )

        decisions.sort(key=lambda item: item.score, reverse=True)
        return RecommendationRun(
            trace_id=str(uuid.uuid4()),
            rules_version=self.rules_version,
            knowledge_version=knowledge_version,
            model_version=model_version,
            items=decisions,
        )

    def _check_eligibility(self, request: RecommendationRequest, program: dict[str, Any]) -> tuple[bool, list[str]]:
        dossier = request.dossier
        reasons: list[str] = []

        required_subjects = set(program.get("subject_requirements", []))
        dossier_subjects = set(dossier.subject_combination)
        if required_subjects and not required_subjects.issubset(dossier_subjects):
            return False, []
        if required_subjects:
            reasons.append("选科要求满足")

        budget = dossier.family_constraints.annual_budget_cny
        if budget is not None and program["tuition_cny"] > budget:
            return False, []
        if budget is not None:
            reasons.append("学费在当前家庭预算内")

        preferred_cities = dossier.family_constraints.city_preference
        if preferred_cities and program["city"] in preferred_cities:
            reasons.append("城市偏好匹配")

        major_interests = set(dossier.major_interests)
        if major_interests and any(tag in major_interests for tag in program.get("tags", [])):
            reasons.append("专业兴趣方向匹配")

        if not reasons:
            reasons.append("基础条件满足当前筛选")
        return True, reasons

    def _score_candidate(self, request: RecommendationRequest, program: dict[str, Any]) -> float:
        dossier = request.dossier
        base_score = 0.5
        historical_rank = program["historical_rank"]
        if dossier.rank:
            rank_delta = historical_rank - dossier.rank
            base_score += max(min(rank_delta / 100000, 0.35), -0.35)
        if dossier.family_constraints.city_preference and program["city"] in dossier.family_constraints.city_preference:
            base_score += 0.08
        if dossier.major_interests and any(tag in dossier.major_interests for tag in program.get("tags", [])):
            base_score += 0.08
        if dossier.family_constraints.annual_budget_cny and program["tuition_cny"] <= dossier.family_constraints.annual_budget_cny:
            base_score += 0.04
        return round(max(0.0, min(base_score, 0.99)), 3)

    def _classify_bucket(self, request: RecommendationRequest, program: dict[str, Any]) -> str:
        dossier = request.dossier
        if dossier.rank is None:
            return "match"

        delta = dossier.rank - program["historical_rank"]
        if delta <= -5000:
            return "safe"
        if delta <= 5000:
            return "match"
        return "reach"

    def _build_risks(self, request: RecommendationRequest, program: dict[str, Any]) -> list[str]:
        dossier = request.dossier
        risks: list[str] = []
        if dossier.rank and dossier.rank > program["historical_rank"]:
            risks.append("往年位次要求略高于你当前的位次，冲刺风险会偏大")
        if program["tuition_cny"] >= 6000:
            risks.append("学费在当前候选里偏高，需要结合家庭预算再判断")
        if dossier.family_constraints.adjustment_accepted is False:
            risks.append("你不接受调剂，这会进一步压缩保底空间")
        return risks or ["最终填报前，仍需要和官方规则与招生章程再次核对"]

    def _build_fit_reasons(self, request: RecommendationRequest, program: dict[str, Any], school: dict[str, Any]) -> list[str]:
        reasons = [f"{school['name']}位于{program['city']}，与当前地域偏好更容易结合"]
        if request.dossier.risk_appetite == "conservative":
            reasons.append("你当前偏向稳妥方案，系统会优先保留更稳的候选")
        if request.dossier.family_constraints.distance_preference == "near_home":
            reasons.append("你提到希望离家近，系统会优先保留更便于家庭协同的选择")
        return reasons

    def _build_parent_summary(self, program_name: str, school_name: str, bucket: str, risks: list[str]) -> str:
        bucket_zh = {"reach": "冲", "match": "稳", "safe": "保"}[bucket]
        summary = f"{school_name}的{program_name}目前被归在“{bucket_zh}”这一档。"
        if risks:
            summary += f" 当前最需要注意的是：{risks[0]}。"
        return summary
