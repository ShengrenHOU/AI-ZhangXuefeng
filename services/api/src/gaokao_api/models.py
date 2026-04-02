from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import DateTime, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .db import Base


class SessionStateModel(Base):
    __tablename__ = "session_states"

    thread_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    state: Mapped[str] = mapped_column(String(32), default="entry_intent")
    dossier: Mapped[dict] = mapped_column(JSON, default=dict)
    messages: Mapped[list] = mapped_column(JSON, default=list)
    pending_recommendation_confirmation: Mapped[bool] = mapped_column(default=False)
    field_provenance: Mapped[dict] = mapped_column(JSON, default=dict)
    recommendation: Mapped[dict | None] = mapped_column(JSON, default=None, nullable=True)
    recommendation_versions: Mapped[list] = mapped_column(JSON, default=list)
    task_timeline: Mapped[list] = mapped_column(JSON, default=list)
    recommendation_fingerprint: Mapped[str | None] = mapped_column(String(128), default=None, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class FeedbackModel(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64))
    rating: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))


class DraftKnowledgeRecordModel(Base):
    __tablename__ = "draft_knowledge_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    draft_id: Mapped[str] = mapped_column(String(96), unique=True, index=True)
    thread_id: Mapped[str] = mapped_column(String(64))
    province: Mapped[str] = mapped_column(String(32))
    target_year: Mapped[int] = mapped_column(Integer)
    school_name: Mapped[str] = mapped_column(String(256))
    program_name: Mapped[str] = mapped_column(String(256))
    source_title: Mapped[str] = mapped_column(String(512))
    source_url: Mapped[str] = mapped_column(Text)
    source_domain: Mapped[str] = mapped_column(String(256))
    evidence_summary: Mapped[str] = mapped_column(Text)
    tuition_cny: Mapped[int | None] = mapped_column(Integer, nullable=True)
    historical_rank: Mapped[int | None] = mapped_column(Integer, nullable=True)
    subject_requirements: Mapped[list] = mapped_column(JSON, default=list)
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[str] = mapped_column(String(16), default="draft")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
