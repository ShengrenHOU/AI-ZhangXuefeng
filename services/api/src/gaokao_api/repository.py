from __future__ import annotations

from .db import session_scope
from .models import DraftKnowledgeRecordModel, FeedbackModel, SessionStateModel


class SessionRepository:
    def create(
        self,
        thread_id: str,
        state: str,
        dossier: dict,
        messages: list[dict],
        pending_recommendation_confirmation: bool = False,
        field_provenance: dict | None = None,
        recommendation: dict | None = None,
        recommendation_fingerprint: str | None = None,
        recommendation_versions: list | None = None,
        task_timeline: list | None = None,
    ) -> SessionStateModel:
        with session_scope() as session:
            model = SessionStateModel(
                thread_id=thread_id,
                state=state,
                dossier=dossier,
                messages=messages,
                pending_recommendation_confirmation=pending_recommendation_confirmation,
                field_provenance=field_provenance or {},
                recommendation=recommendation,
                recommendation_fingerprint=recommendation_fingerprint,
                recommendation_versions=recommendation_versions or [],
                task_timeline=task_timeline or [],
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
        recommendation: dict | None = None,
        recommendation_fingerprint: str | None = None,
        recommendation_versions: list | None = None,
        task_timeline: list | None = None,
        clear_recommendation: bool = False,
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
            if clear_recommendation:
                model.recommendation = None
                model.recommendation_fingerprint = None
            elif recommendation is not None:
                model.recommendation = recommendation
            if not clear_recommendation and recommendation_fingerprint is not None:
                model.recommendation_fingerprint = recommendation_fingerprint
            if recommendation_versions is not None:
                model.recommendation_versions = recommendation_versions
            if task_timeline is not None:
                model.task_timeline = task_timeline
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


class DraftKnowledgeRepository:
    def create_many(self, records: list[dict]) -> list[DraftKnowledgeRecordModel]:
        if not records:
            return []
        with session_scope() as session:
            models = [DraftKnowledgeRecordModel(**record) for record in records]
            session.add_all(models)
            session.flush()
            for model in models:
                session.refresh(model)
            return models
