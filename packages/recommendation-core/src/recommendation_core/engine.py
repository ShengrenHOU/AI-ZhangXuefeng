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
            reasons.append("subject requirements satisfied")

        budget = dossier.family_constraints.annual_budget_cny
        if budget is not None and program["tuition_cny"] > budget:
            return False, []
        if budget is not None:
            reasons.append("tuition within annual budget")

        preferred_cities = dossier.family_constraints.city_preference
        if preferred_cities and program["city"] in preferred_cities:
            reasons.append("city preference matched")

        major_interests = set(dossier.major_interests)
        if major_interests and any(tag in major_interests for tag in program.get("tags", [])):
            reasons.append("major interest matched")

        if not reasons:
            reasons.append("baseline eligibility passed")
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
            risks.append("historical rank line is slightly stronger than the current dossier")
        if program["tuition_cny"] >= 6000:
            risks.append("tuition is relatively high for a public undergraduate option")
        if dossier.family_constraints.adjustment_accepted is False:
            risks.append("no-adjustment preference reduces fallback space")
        return risks or ["recommendation still requires final official volunteering review"]

    def _build_fit_reasons(self, request: RecommendationRequest, program: dict[str, Any], school: dict[str, Any]) -> list[str]:
        reasons = [f"{school['name']} is in {program['city']}"]
        if request.dossier.risk_appetite == "conservative":
            reasons.append("bucketing prefers stability for the current risk appetite")
        if request.dossier.family_constraints.distance_preference == "near_home":
            reasons.append("current routing favors options that are easier for family coordination")
        return reasons

    def _build_parent_summary(self, program_name: str, school_name: str, bucket: str, risks: list[str]) -> str:
        summary = f"{school_name} · {program_name} is currently classified as {bucket}."
        if risks:
            summary += f" Main risk: {risks[0]}."
        return summary

