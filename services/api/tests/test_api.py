from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite:///./services/api/test_gaokao_mvp.db"
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

    message = client.post(
        f"/api/session/{thread_id}/message",
        json={"content": "河南，位次: 68000，physics chemistry biology，预算: 6500，想学电气，稳一点。"},
    )
    assert message.status_code == 200
    payload = message.json()
    assert payload["thread_id"] == thread_id
    assert payload["recommendation"] is not None
    assert payload["readiness"]["can_recommend"] is True

    dossier = client.get(f"/api/session/{thread_id}/dossier")
    assert dossier.status_code == 200
    assert dossier.json()["province"] == "henan"

    snapshot = client.get(f"/api/session/{thread_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["thread_id"] == thread_id
    assert len(snapshot.json()["messages"]) >= 2
    assert snapshot.json()["readiness"]["level"] == "ready_for_recommendation"


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

