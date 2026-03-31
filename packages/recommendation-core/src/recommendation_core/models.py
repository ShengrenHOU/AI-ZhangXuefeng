from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


Bucket = Literal["reach", "match", "safe"]
RiskAppetite = Literal["conservative", "balanced", "aggressive"]
DistancePreference = Literal["near_home", "balanced", "nationwide"]


class FamilyConstraintSet(BaseModel):
    annual_budget_cny: int | None = None
    city_preference: list[str] = Field(default_factory=list)
    distance_preference: DistancePreference | None = None
    adjustment_accepted: bool | None = None
    notes: list[str] = Field(default_factory=list)


class StudentDossier(BaseModel):
    province: str | None = None
    target_year: int | None = None
    rank: int | None = None
    score: int | None = None
    subject_combination: list[str] = Field(default_factory=list)
    major_interests: list[str] = Field(default_factory=list)
    family_constraints: FamilyConstraintSet = Field(default_factory=FamilyConstraintSet)
    risk_appetite: RiskAppetite | None = None
    summary_notes: list[str] = Field(default_factory=list)


class RecommendationRequest(BaseModel):
    thread_id: str | None = None
    dossier: StudentDossier


class RecommendationDecision(BaseModel):
    school_id: str
    program_id: str
    school_name: str
    program_name: str
    city: str
    tuition_cny: int
    bucket: Bucket
    fit_reasons: list[str]
    risk_warnings: list[str]
    parent_summary: str
    source_ids: list[str]
    trace: list[str]
    score: float


class RecommendationRun(BaseModel):
    trace_id: str
    rules_version: str
    knowledge_version: str
    model_version: str
    items: list[RecommendationDecision]
