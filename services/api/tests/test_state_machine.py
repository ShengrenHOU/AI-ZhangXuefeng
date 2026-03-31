from __future__ import annotations

from pathlib import Path

from knowledge_base import KnowledgeRepository
from recommendation_core import RecommendationCore

from gaokao_api.state_machine import SessionStateMachine


def make_machine() -> SessionStateMachine:
    repo_root = Path(__file__).resolve().parents[3]
    knowledge = KnowledgeRepository.from_root(repo_root / "packages" / "knowledge" / "data")
    return SessionStateMachine(repository=knowledge, recommendation_core=RecommendationCore())


def test_state_machine_asks_follow_up_for_missing_rank() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(state, "我是河南考生，想学计算机，家里条件一般，离家近一点。")
    assert result["state"] == "follow_up_questioning"
    assert result["model_action"]["action"] == "ask_followup"
    assert "位次" in result["assistant_message"] or "分数" in result["assistant_message"]


def test_state_machine_returns_recommendation_when_dossier_is_complete() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近。",
    )
    assert result["state"] == "result_explanation"
    assert result["recommendation"] is not None
    assert result["recommendation"]["items"]

