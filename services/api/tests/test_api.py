from __future__ import annotations

import os
from pathlib import Path
import tempfile
import uuid

db_path = Path(tempfile.gettempdir()) / f"gaokao_mvp_test_{uuid.uuid4().hex}.db"

os.environ["DATABASE_URL"] = f"sqlite:///{db_path.resolve().as_posix()}"
os.environ["ENABLE_LIVE_LLM"] = "false"

from fastapi.testclient import TestClient  # noqa: E402

from knowledge_base import KnowledgeRepository  # noqa: E402
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
    assert payload["recommendation"] is not None
    assert payload["readiness"]["can_recommend"] is True
    assert payload["pending_recommendation_confirmation"] is False
    assert payload["field_provenance"]

    dossier = client.get(f"/api/session/{thread_id}/dossier")
    assert dossier.status_code == 200
    assert dossier.json()["province"] == "henan"

    snapshot = client.get(f"/api/session/{thread_id}")
    assert snapshot.status_code == 200
    assert snapshot.json()["thread_id"] == thread_id
    assert len(snapshot.json()["messages"]) >= 2
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


def test_stream_endpoint_emits_compare_delta_for_chat_native_compare() -> None:
    start = client.post("/api/session/start")
    thread_id = start.json()["thread_id"]

    client.post(
        f"/api/session/{thread_id}/message",
        json={"content": "河南，位次: 68000，physics chemistry biology，预算: 6500，想学电气，稳一点，接受调剂。"},
    )
    client.post(
        f"/api/session/{thread_id}/message",
        json={"content": "可以，就按这些条件开始推荐。"},
    )

    response = client.post(
        f"/api/session/{thread_id}/stream",
        json={"content": "帮我比较前两个方案。"},
    )

    assert response.status_code == 200
    body = response.text
    assert "event: compare_delta" in body
    assert "event: final_message" in body


def test_stream_endpoint_recommends_immediately_when_user_explicitly_requests_recommendation() -> None:
    start = client.post("/api/session/start")
    thread_id = start.json()["thread_id"]

    response = client.post(
        f"/api/session/{thread_id}/stream",
        json={"content": "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近，直接给我推荐吧。"},
    )

    assert response.status_code == 200
    body = response.text
    assert "event: assistant_delta" in body
    assert "event: recommendation_delta" in body
    assert "event: final_message" in body


def test_append_draft_discoveries_creates_jsonl_record(tmp_path) -> None:
    repo = KnowledgeRepository.from_root(tmp_path / "knowledge")
    output = repo.append_draft_discoveries(
        province="henan",
        year=2026,
        records=[
            {
                "record_id": "web-henan-tech-electrical",
                "province": "henan",
                "year": 2026,
                "title": "河南工学院 / 电气工程及其自动化",
                "source_url": "https://example.edu.cn/admission",
                "source_domain": "example.edu.cn",
                "school_name": "河南工学院",
                "program_name": "电气工程及其自动化",
                "tuition_cny": 5500,
                "subject_requirements": ["physics"],
                "historical_rank": 76000,
                "evidence_summary": "网页里提到了电气专业、学费和选科要求。",
                "status": "draft",
            }
        ],
    )

    assert output is not None
    assert output.exists()
    lines = output.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1
    assert "河南工学院" in lines[0]
