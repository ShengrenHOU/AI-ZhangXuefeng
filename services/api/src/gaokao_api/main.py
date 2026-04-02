from __future__ import annotations

import json
from queue import Queue
from threading import Thread
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from knowledge_base import KnowledgeRepository
from recommendation_core import RecommendationCore
from recommendation_core.models import RecommendationRequest, StudentDossier

from .config import settings
from .db import Base, engine, ensure_schema_compatibility
from .llm import ArkCodingPlanClient
from .repository import FeedbackRepository, SessionRepository
from .schemas import (
    ChatMessageRequest,
    ChatMessageResponse,
    ComparePayload,
    CompareResponse,
    ExportSummaryResponse,
    FeedbackRequest,
    SessionSnapshotResponse,
    SessionStartResponse,
    SourceRecordResponse,
)
from .state_machine import SessionStateMachine
from .web_retrieval import WebRetriever

Base.metadata.create_all(bind=engine)
ensure_schema_compatibility()

app = FastAPI(title="Gaokao Assistant API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

knowledge_repo = KnowledgeRepository.from_root(settings.knowledge_path)
state_machine = SessionStateMachine(
    repository=knowledge_repo,
    recommendation_core=RecommendationCore(),
    planner_client=ArkCodingPlanClient(),
    web_retriever=WebRetriever(
        max_results=settings.web_retrieval_max_results,
        max_chars=settings.web_context_char_limit,
    )
    if settings.enable_web_retrieval
    else None,
    province=settings.province,
    target_year=settings.target_year,
)
session_repo = SessionRepository()
feedback_repo = FeedbackRepository()


@app.get("/healthz")
def healthcheck() -> dict:
    return {
        "status": "ok",
        "model": settings.ark_model,
        "instant_model": settings.ark_instant_model or settings.ark_model,
        "deepthink_model": settings.ark_deepthink_model or settings.ark_model,
        "live_llm_enabled": settings.enable_live_llm,
        "web_retrieval_enabled": settings.enable_web_retrieval,
        "web_retrieval_strategy": "bing_rss_primary_duckduckgo_fallback",
        "knowledge_root": str(settings.knowledge_path),
    }


@app.post("/api/session/start", response_model=SessionStartResponse)
def start_session() -> SessionStartResponse:
    initial = state_machine.initialize()
    session_repo.create(
        initial["thread_id"],
        initial["state"],
        initial["dossier"],
        initial["messages"],
        pending_recommendation_confirmation=initial["pending_recommendation_confirmation"],
        field_provenance=initial["field_provenance"],
        recommendation=None,
        recommendation_fingerprint=None,
        recommendation_versions=[],
        task_timeline=[],
    )
    return SessionStartResponse(
        thread_id=initial["thread_id"],
        state=initial["state"],
        dossier=StudentDossier(**initial["dossier"]),
        readiness=initial["readiness"],
        pending_recommendation_confirmation=initial["pending_recommendation_confirmation"],
        field_provenance=initial["field_provenance"],
        recommendation=None,
        recommendation_versions=[],
        task_timeline=[],
    )


@app.post("/api/session/{thread_id}/message", response_model=ChatMessageResponse)
def send_message(thread_id: str, payload: ChatMessageRequest) -> ChatMessageResponse:
    existing = session_repo.get(thread_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="thread not found")

    state = {
        "thread_id": existing.thread_id,
        "state": existing.state,
        "dossier": existing.dossier,
        "messages": existing.messages,
        "pending_recommendation_confirmation": existing.pending_recommendation_confirmation,
        "field_provenance": existing.field_provenance,
        "recommendation": existing.recommendation,
        "recommendation_fingerprint": existing.recommendation_fingerprint,
        "recommendation_versions": existing.recommendation_versions,
        "task_timeline": existing.task_timeline,
    }
    result = state_machine.handle_message(state, payload.content)
    session_repo.update(
        thread_id,
        result["state"],
        result["dossier"],
        state["messages"],
        pending_recommendation_confirmation=result["pending_recommendation_confirmation"],
        field_provenance=result["field_provenance"],
        recommendation=result["recommendation"] if result["recommendation"] is not None else existing.recommendation,
        recommendation_fingerprint=result["recommendation_fingerprint"],
        recommendation_versions=result["recommendation_versions"],
        task_timeline=result["task_timeline"],
    )

    return ChatMessageResponse(
        thread_id=thread_id,
        state=result["state"],
        assistant_message=result["assistant_message"],
        dossier=StudentDossier(**result["dossier"]),
        model_action=result["model_action"],
        readiness=result["readiness"],
        pending_recommendation_confirmation=result["pending_recommendation_confirmation"],
        field_provenance=result["field_provenance"],
        recommendation=result["recommendation"] if result["recommendation"] is not None else existing.recommendation,
        recommendation_versions=result["recommendation_versions"],
        task_timeline=result["task_timeline"],
    )


@app.get("/api/session/{thread_id}/dossier", response_model=StudentDossier)
def get_dossier(thread_id: str) -> StudentDossier:
    existing = session_repo.get(thread_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return StudentDossier(**existing.dossier)


@app.get("/api/session/{thread_id}", response_model=SessionSnapshotResponse)
def get_session(thread_id: str) -> SessionSnapshotResponse:
    existing = session_repo.get(thread_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="thread not found")
    return SessionSnapshotResponse(
        thread_id=existing.thread_id,
        state=existing.state,
        dossier=StudentDossier(**existing.dossier),
        messages=existing.messages,
        readiness=state_machine.evaluate_dossier(StudentDossier(**existing.dossier)),
        pending_recommendation_confirmation=existing.pending_recommendation_confirmation,
        field_provenance=existing.field_provenance,
        recommendation=existing.recommendation,
        recommendation_versions=existing.recommendation_versions,
        task_timeline=existing.task_timeline,
    )


@app.post("/api/session/{thread_id}/stream")
def stream_message(thread_id: str, payload: ChatMessageRequest) -> StreamingResponse:
    existing = session_repo.get(thread_id)
    if existing is None:
        raise HTTPException(status_code=404, detail="thread not found")

    state = {
        "thread_id": existing.thread_id,
        "state": existing.state,
        "dossier": existing.dossier,
        "messages": existing.messages,
        "pending_recommendation_confirmation": existing.pending_recommendation_confirmation,
        "field_provenance": existing.field_provenance,
        "recommendation": existing.recommendation,
        "recommendation_fingerprint": existing.recommendation_fingerprint,
        "recommendation_versions": existing.recommendation_versions,
        "task_timeline": existing.task_timeline,
    }

    def event_stream():
        yield _sse_event("status", {"message": "正在理解你的意图"})

        queue: Queue[tuple[str, dict[str, object]] | tuple[str, dict[str, object], dict | None]] = Queue()

        def emit(event: str, payload: dict[str, object]) -> None:
            queue.put((event, payload))

        def worker() -> None:
            result = state_machine.handle_message(state, payload.content, emit=emit)
            persisted_recommendation = result["recommendation"] if result["recommendation"] is not None else existing.recommendation
            session_repo.update(
                thread_id,
                result["state"],
                result["dossier"],
                state["messages"],
                pending_recommendation_confirmation=result["pending_recommendation_confirmation"],
                field_provenance=result["field_provenance"],
                recommendation=persisted_recommendation,
                recommendation_fingerprint=result["recommendation_fingerprint"],
                recommendation_versions=result["recommendation_versions"],
                task_timeline=result["task_timeline"],
            )
            queue.put(("__done__", result, persisted_recommendation))

        Thread(target=worker, daemon=True).start()

        result = None
        persisted_recommendation = None
        while True:
            item = queue.get()
            if item[0] == "__done__":
                result = item[1]
                persisted_recommendation = item[2]
                break
            yield _sse_event(item[0], item[1])

        if result is None:
            return

        if result["model_action"]["action"] == "directional_guidance":
            yield _sse_event(
                "directional_guidance",
                {
                    "assistant_message": result["assistant_message"],
                    "readiness": result["readiness"],
                },
            )
        if result["model_action"]["action"] in {"recommend", "refine_recommendation", "explain_results"} and persisted_recommendation:
            yield _sse_event("status", {"message": "正在生成正式建议"})
            for chunk in _stream_recommendation_text(result["dossier"], payload.content):
                yield _sse_event("assistant_delta", {"delta": chunk})
        elif result["model_action"]["action"] == "compare_options":
            yield _sse_event("status", {"message": "正在比较候选方案"})
            for chunk in _chunk_text(result["assistant_message"]):
                yield _sse_event("compare_delta", {"delta": chunk})
        if persisted_recommendation:
            for item in persisted_recommendation["items"]:
                yield _sse_event("recommendation_delta", item)
        yield _sse_event(
            "final_message",
            {
                "thread_id": thread_id,
                "state": result["state"],
                "assistant_message": result["assistant_message"],
                "dossier": result["dossier"],
                "readiness": result["readiness"],
                "pending_recommendation_confirmation": result["pending_recommendation_confirmation"],
                "field_provenance": result["field_provenance"],
                "recommendation": persisted_recommendation,
                "recommendation_versions": result["recommendation_versions"],
                "task_timeline": result["task_timeline"],
                "model_action": result["model_action"],
            },
        )

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/api/recommendation/run")
def run_recommendation(request: RecommendationRequest) -> dict:
    run, _ = state_machine.build_recommendation_run(request.thread_id or "adhoc-run", request.dossier)
    return run


@app.post("/api/recommendation/compare", response_model=CompareResponse)
def compare_programs(payload: ComparePayload) -> CompareResponse:
    programs = {program["program_id"]: program for program in knowledge_repo.load_programs(province=settings.province, year=settings.target_year)}
    left = programs[payload.left_program_id]
    right = programs[payload.right_program_id]
    left_tags = "、".join(left["tags"])
    right_tags = "、".join(right["tags"])
    summary = (
        f"{left['name']}和{right['name']}的侧重点并不一样。"
        f"前者更偏向 {left_tags}，后者更偏向 {right_tags}。"
        "如果你现在更看重稳妥和家庭可接受度，就要结合学费、城市、风险提示一起看，而不是只看专业名称。"
    )
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
        "家庭沟通摘要",
        "",
        f"省份：{request.dossier.province or settings.province}",
        f"年份：{request.dossier.target_year or settings.target_year}",
        "",
    ]
    for item in items[:3]:
        lines.append(f"- {item['school_name']} / {item['program_name']}（{item['bucket']}）：{item['parent_summary']}")
    return ExportSummaryResponse(
        title="高考志愿家庭摘要",
        body="\n".join(lines),
        source_ids=source_ids,
        trace_id=run["trace_id"],
    )


@app.post("/api/feedback")
def create_feedback(payload: FeedbackRequest) -> dict:
    feedback = feedback_repo.create(thread_id=payload.thread_id, rating=payload.rating, comment=payload.comment)
    return {"id": feedback.id, "thread_id": feedback.thread_id, "rating": feedback.rating}


def _sse_event(event: str, payload: dict) -> str:
    return f"event: {event}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"


def _stream_recommendation_text(dossier: dict, user_message: str):
    if state_machine.planner_client is not None and state_machine.planner_client.is_configured():
        try:
            context_slice = state_machine._retrieve_knowledge_slice(StudentDossier(**dossier), user_message)
            for chunk in state_machine.planner_client.stream_recommendation_text(
                dossier=dossier,
                retrieved_knowledge=context_slice,
            ):
                if chunk:
                    yield chunk
            return
        except Exception:
            pass
    for chunk in _chunk_text("正在整理正式建议，请稍等。"):
        yield chunk


def _chunk_text(text: str, chunk_size: int = 18):
    for index in range(0, len(text), chunk_size):
        yield text[index : index + chunk_size]
