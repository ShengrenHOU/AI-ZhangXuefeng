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
    recommendation_fingerprint: Mapped[str | None] = mapped_column(String(128), default=None, nullable=True)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))


class FeedbackModel(Base):
    __tablename__ = "feedback"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    thread_id: Mapped[str] = mapped_column(String(64))
    rating: Mapped[str] = mapped_column(String(16))
    comment: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(UTC))
