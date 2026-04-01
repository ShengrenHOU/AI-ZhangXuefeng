from __future__ import annotations

from .db import session_scope
from .models import FeedbackModel, SessionStateModel


class SessionRepository:
    def create(
        self,
        thread_id: str,
        state: str,
        dossier: dict,
        messages: list[dict],
        pending_recommendation_confirmation: bool = False,
        field_provenance: dict | None = None,
    ) -> SessionStateModel:
        with session_scope() as session:
            model = SessionStateModel(
                thread_id=thread_id,
                state=state,
                dossier=dossier,
                messages=messages,
                pending_recommendation_confirmation=pending_recommendation_confirmation,
                field_provenance=field_provenance or {},
            )
            session.add(model)
            session.flush()
            session.refresh(model)
            return model

    def get(self, thread_id: str) -> SessionStateModel | None:
        with session_scope() as session:
            return session.get(SessionStateModel, thread_id)

    def update(
        self,
        thread_id: str,
        state: str,
        dossier: dict,
        messages: list[dict],
        pending_recommendation_confirmation: bool | None = None,
        field_provenance: dict | None = None,
    ) -> SessionStateModel | None:
        with session_scope() as session:
            model = session.get(SessionStateModel, thread_id)
            if model is None:
                return None
            model.state = state
            model.dossier = dossier
            model.messages = messages
            if pending_recommendation_confirmation is not None:
                model.pending_recommendation_confirmation = pending_recommendation_confirmation
            if field_provenance is not None:
                model.field_provenance = field_provenance
            session.add(model)
            session.flush()
            session.refresh(model)
            return model


class FeedbackRepository:
    def create(self, thread_id: str, rating: str, comment: str) -> FeedbackModel:
        with session_scope() as session:
            model = FeedbackModel(thread_id=thread_id, rating=rating, comment=comment)
            session.add(model)
            session.flush()
            session.refresh(model)
            return model
