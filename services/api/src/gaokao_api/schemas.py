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


class SessionStatePayload(BaseModel):
    dossier: StudentDossier
    readiness: ReadinessResponse
    pending_recommendation_confirmation: bool
    field_provenance: dict[str, str]
    recommendation: RecommendationRun | None = None
    recommendation_versions: list[dict] = Field(default_factory=list)
    task_timeline: list[dict] = Field(default_factory=list)


class SessionStartResponse(SessionStatePayload):
    thread_id: str
    state: str


class SessionSnapshotResponse(SessionStatePayload):
    thread_id: str
    state: str
    messages: list[dict]


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class ChatMessageResponse(SessionStatePayload):
    thread_id: str
    state: str
    assistant_message: str
    model_action: dict


class StreamMessageResponse(BaseModel):
    event: str
    payload: dict


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
