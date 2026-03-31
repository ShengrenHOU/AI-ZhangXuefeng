from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field
from recommendation_core.models import RecommendationRun, StudentDossier


class SessionStartResponse(BaseModel):
    thread_id: str
    state: str
    dossier: StudentDossier


class SessionSnapshotResponse(BaseModel):
    thread_id: str
    state: str
    dossier: StudentDossier
    messages: list[dict]


class ChatMessageRequest(BaseModel):
    content: str = Field(min_length=1)


class ChatMessageResponse(BaseModel):
    thread_id: str
    state: str
    assistant_message: str
    dossier: StudentDossier
    model_action: dict
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
