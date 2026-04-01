from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from recommendation_core.models import RecommendationRun, StudentDossier


class ConflictNoticeResponse(BaseModel):
    code: str
    message: str


class ReadinessResponse(BaseModel):
    level: Literal["insufficient_info", "near_ready", "ready_for_recommendation"]
    can_recommend: bool
    missing_fields: list[str]
    missing_labels: list[str]
    conflicts: list[ConflictNoticeResponse]


class SessionStartResponse(BaseModel):
    thread_id: str
    state: str
    dossier: StudentDossier
    readiness: ReadinessResponse
    pending_recommendation_confirmation: bool
    field_provenance: dict[str, str]


class SessionSnapshotResponse(BaseModel):
    thread_id: str
    state: str
    dossier: StudentDossier
    messages: list[dict]
    readiness: ReadinessResponse
    pending_recommendation_confirmation: bool
    field_provenance: dict[str, str]


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class ChatMessageResponse(BaseModel):
    thread_id: str
    state: str
    assistant_message: str
    dossier: StudentDossier
    model_action: dict
    readiness: ReadinessResponse
    pending_recommendation_confirmation: bool
    field_provenance: dict[str, str]
    recommendation: RecommendationRun | None = None


class ComparePayload(BaseModel):
    left_program_id: str
    right_program_id: str


class CompareResponse(BaseModel):
    left_program_id: str
    right_program_id: str
    summary: str
    source_ids: list[str]


class ExportSummaryResponse(BaseModel):
    title: str
    body: str
    source_ids: list[str]
    trace_id: str


class FeedbackRequest(BaseModel):
    thread_id: str
    rating: Literal["up", "down", "neutral"]
    comment: str = ""


class SourceRecordResponse(BaseModel):
    source_id: str
    kind: str
    title: str
    year: int
    publication_status: str
    source_url: str
    fetched_at: str
    summary: str
