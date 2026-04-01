from __future__ import annotations

import os
from pathlib import Path
import tempfile
import uuid

db_path = Path(tempfile.gettempdir()) / f"gaokao_mvp_test_{uuid.uuid4().hex}.db"

os.environ["DATABASE_URL"] = f"sqlite:///{db_path.resolve().as_posix()}"
os.environ["ENABLE_LIVE_LLM"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from gaokao_api.main import app  # noqa: E402


client = TestClient(app)


def test_session_flow_and_dossier_endpoint() -> None:
    start = client.post("/api/session/start")
    assert start.status_code == 200
    start_payload = start.json()
    thread_id = start_payload["thread_id"]
    assert start_payload["readiness"]["level"] == "insufficient_info"
    assert start_payload["pending_recommendation_confirmation"] is False
    assert start_payload["field_provenance"] == {}

    message = client.post(
        f"/api/session/{thread_id}/message",
        json={"content": "河南，位次: 68000，physics chemistry biology，预算: 6500，想学电气，稳一点。"},
    )
    assert message.status_code == 200
    payload = message.json()
    assert payload["thread_id"] == thread_id
    assert payload["recommendation"] is None
    assert payload["readiness"]["can_recommend"] is True
    assert payload["pending_recommendation_confirmation"] is True
    assert payload["field_provenance"]

    confirm = client.post(
        f"/api/session/{thread_id}/message",
        json={"content": "可以，就按这些条件开始推荐。"},
    )
    assert confirm.status_code == 200
    confirm_payload = confirm.json()
    assert confirm_payload["recommendation"] is not None
    assert confirm_payload["pending_recommendation_confirmation"] is False
    assert confirm_payload["recommendation_versions"]
    assert confirm_payload["task_timeline"]

    dossier = client.get(f"/api/session/{thread_id}/dossier")
    assert dossier.status_code == 200
    assert dossier.json()["province"] == "henan"

    snapshot = client.get(f"/api/session/{thread_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["thread_id"] == thread_id
    assert len(snapshot.json()["messages"]) >= 4
    assert snapshot.json()["readiness"]["level"] == "ready_for_recommendation"
    assert snapshot.json()["field_provenance"]
    assert snapshot.json()["recommendation"] is not None
    assert snapshot.json()["recommendation_versions"]
    assert snapshot.json()["task_timeline"]


def test_healthcheck() -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_source_lookup() -> None:
    response = client.get("/api/sources/src-program-henan-tech-electrical")
    assert response.status_code == 200
    assert response.json()["publication_status"] == "published"


def test_conflict_message_does_not_recommend() -> None:
    start = client.post("/api/session/start")
    thread_id = start.json()["thread_id"]
    message = client.post(
        f"/api/session/{thread_id}/message",
        json={"content": "河南，位次: 25000，physics chemistry biology，预算: 9000，想冲一冲，想学电气，不接受调剂，最好离家近，但我也想优先去北京。"},
    )
    assert message.status_code == 200
    payload = message.json()
    assert payload["state"] == "constraint_confirmation"
    assert payload["recommendation"] is None
    assert payload["readiness"]["conflicts"]


def test_stream_endpoint_emits_status_and_final_message() -> None:
    start = client.post("/api/session/start")
    thread_id = start.json()["thread_id"]
    with client.stream(
        "POST",
        f"/api/session/{thread_id}/stream",
        json={"content": "河南，位次: 68000，physics chemistry biology，预算: 6500，想学电气，稳一点。"},
    ) as response:
        assert response.status_code == 200
        body = response.read().decode("utf-8")

    assert "event: status" in body
    assert "event: final_message" in body
    assert "recommendation_versions" in body
    assert "task_timeline" in body


def test_stream_endpoint_returns_task_steps_and_final_message() -> None:
    start = client.post("/api/session/start")
    thread_id = start.json()["thread_id"]
    response = client.post(
        f"/api/session/{thread_id}/stream",
        json={"content": "我是河南考生，位次65000，物化生，想学计算机，预算6500，帮我先给方向，如果合适再正式推荐。"},
    )
    assert response.status_code == 200
    body = response.text
    assert "event: status" in body
    assert "event: task_step" in body
    assert "event: final_message" in body
