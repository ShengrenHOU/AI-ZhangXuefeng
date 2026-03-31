from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from knowledge_base import KnowledgeRepository
from recommendation_core import RecommendationCore
from recommendation_core.models import RecommendationRequest, StudentDossier

from .config import settings
from .db import Base, engine
from .repository import FeedbackRepository, SessionRepository
from .schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ComparePayload,
    CompareResponse,
    ExportSummaryResponse,
    FeedbackRequest,
    SessionStartResponse,
    SourceRecordResponse,
)
from .state_machine import SessionStateMachine

Base.metadata.create_all(bind=engine)

app = FastAPI(title="Gaokao Assistant API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

knowledge_repo = KnowledgeRepository.from_root(settings.knowledge_path)
recommendation_core = RecommendationCore()
state_machine = SessionStateMachine(
    repository=knowledge_repo,
    recommendation_core=recommendation_core,
    province=settings.province,
    target_year=settings.target_year,
)
session_repo = SessionRepository()
feedback_repo = FeedbackRepository()


@app.post("/api/session/start", response_model=SessionStartResponse)
def start_session() -> SessionStartResponse:
    initial = state_machine.initialize()
    session_repo.create(initial["thread_id"], initial["state"], initial["dossier"], initial["messages"])
    return SessionStartResponse(thread_id=initial["thread_id"], state=initial["state"], dossier=StudentDossier(**initial["dossier"]))


@app.post("/api/session/{thread_id}/message", response_model=ChatMessageResponse)
def send_message(thread_id: str, payload: ChatMessageRequest) -> ChatMessageResponse:
    existing = session_repo.get(thread_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="thread not found")

    state = {"thread_id": existing.thread_id, "state": existing.state, "dossier": existing.dossier, "messages": existing.messages}
    result = state_machine.handle_message(state, payload.content)
    session_repo.update(thread_id, result["state"], result["dossier"], state["messages"])

    return ChatMessageResponse(
        thread_id=thread_id,
        state=result["state"],
        assistant_message=result["assistant_message"],
        dossier=StudentDossier(**result["dossier"]),
        model_action=result["model_action"],
        recommendation=result["recommendation"],
    )


@app.get("/api/session/{thread_id}/dossier", response_model=StudentDossier)
def get_dossier(thread_id: str) -> StudentDossier:
    existing = session_repo.get(thread_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return StudentDossier(**existing.dossier)


@app.post("/api/recommendation/run")
def run_recommendation(request: RecommendationRequest) -> dict:
    manifest = knowledge_repo.load_manifest(province=settings.province, year=settings.target_year)
    run = recommendation_core.run(
        request=request,
        programs=knowledge_repo.load_programs(province=settings.province, year=settings.target_year),
        schools=knowledge_repo.load_schools(province=settings.province, year=settings.target_year),
        knowledge_version=manifest["version"],
        model_version=settings.mimo_model if settings.mimo_api_key else "mock-structured-output",
    )
    return run.model_dump()


@app.post("/api/recommendation/compare", response_model=CompareResponse)
def compare_programs(payload: ComparePayload) -> CompareResponse:
    programs = {program["program_id"]: program for program in knowledge_repo.load_programs(province=settings.province, year=settings.target_year)}
    left = programs[payload.left_program_id]
    right = programs[payload.right_program_id]
    summary = f"{left['name']} focuses on {', '.join(left['tags'])}, while {right['name']} focuses on {', '.join(right['tags'])}."
    source_ids = sorted(set(left["source_ids"] + right["source_ids"]))
    return CompareResponse(left_program_id=left["program_id"], right_program_id=right["program_id"], summary=summary, source_ids=source_ids)


@app.get("/api/sources/{source_id}", response_model=SourceRecordResponse)
def get_source(source_id: str) -> SourceRecordResponse:
    record = knowledge_repo.get_source(source_id, province=settings.province, year=settings.target_year)
    if record is None:
        raise HTTPException(status_code=404, detail="source not found")
    return SourceRecordResponse(**record)


@app.post("/api/export/family-summary", response_model=ExportSummaryResponse)
def export_family_summary(request: RecommendationRequest) -> ExportSummaryResponse:
    run = run_recommendation(request)
    items = run["items"]
    source_ids = sorted({source_id for item in items for source_id in item["source_ids"]})
    lines = [
        "Family Summary",
        "",
        f"Province: {request.dossier.province or settings.province}",
        f"Year: {request.dossier.target_year or settings.target_year}",
        "",
    ]
    for item in items[:3]:
        lines.append(f"- {item['program_id']} ({item['bucket']}): {item['parent_summary']}")
    return ExportSummaryResponse(
        title="Gaokao Family Summary",
        body="\n".join(lines),
        source_ids=source_ids,
        trace_id=run["trace_id"],
    )


@app.post("/api/feedback")
def create_feedback(payload: FeedbackRequest) -> dict:
    feedback = feedback_repo.create(thread_id=payload.thread_id, rating=payload.rating, comment=payload.comment)
    return {"id": feedback.id, "thread_id": feedback.thread_id, "rating": feedback.rating}
