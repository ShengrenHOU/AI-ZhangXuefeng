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
    assert result["recommendation"] is None
    assert result["readiness"]["level"] != "ready_for_recommendation"
    assert "位次" in result["assistant_message"] or "分数" in result["assistant_message"]


def test_state_machine_returns_recommendation_when_dossier_is_complete() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近。",
    )
    assert result["state"] == "constraint_confirmation"
    assert result["readiness"]["level"] == "ready_for_recommendation"
    assert result["pending_recommendation_confirmation"] is True
    assert result["recommendation"] is None


def test_state_machine_recommends_only_after_affirmation() -> None:
    machine = make_machine()
    state = machine.initialize()
    first = machine.handle_message(
        state,
        "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近。",
    )
    assert state["pending_recommendation_confirmation"] is True
    second = machine.handle_message(state, "可以，就按这些条件开始推荐。")
    assert second["state"] == "result_explanation"
    assert second["pending_recommendation_confirmation"] is False
    assert second["recommendation"] is not None
    assert second["recommendation"]["items"]
    assert second["field_provenance"]


def test_state_machine_blocks_recommendation_when_constraints_conflict() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "河南，位次: 25000，physics chemistry biology，预算: 9000，想冲一冲，想学电气，不接受调剂，最好离家近，但我也想优先去北京。",
    )
    assert result["state"] == "constraint_confirmation"
    assert result["model_action"]["action"] == "confirm_constraints"
    assert result["recommendation"] is None
    assert result["readiness"]["conflicts"]


def test_state_machine_understands_subject_aliases() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "河南，位次: 65000，选科是物化生，预算: 6500，想学计算机，稳一点。",
    )
    assert result["dossier"]["subject_combination"] == ["biology", "chemistry", "physics"]
    assert "subject_combination" not in result["readiness"]["missing_fields"]


def test_state_machine_answers_subject_combo_question_before_recommending() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "我是河南考生，家里条件一般，想稳一点，最好离家近些。我是理科生，我想知道都有哪些选科组合，然后你推荐我选什么专业。",
    )
    assert result["state"] == "follow_up_questioning"
    assert result["recommendation"] is None
    assert "物化生" in result["assistant_message"]
    assert "理科生" in result["assistant_message"]


def test_state_machine_preserves_confirmation_but_allows_negative_reply() -> None:
    machine = make_machine()
    state = machine.initialize()
    first = machine.handle_message(
        state,
        "河南，位次: 65000，选科是物化生，预算: 6500，想学计算机，接受调剂。",
    )
    assert state["pending_recommendation_confirmation"] is True
    second = machine.handle_message(state, "我还想改一下条件，先别正式推荐。")
    assert second["state"] == "follow_up_questioning"
    assert second["pending_recommendation_confirmation"] is False
    assert second["recommendation"] is None


def test_state_machine_does_not_misread_negative_reply_as_affirmation() -> None:
    machine = make_machine()
    state = machine.initialize()
    machine.handle_message(
        state,
        "河南，位次: 65000，选科是物化生，预算: 6500，想学计算机，接受调剂。",
    )
    second = machine.handle_message(state, "不可以，先别正式推荐，我还想再改一下条件。")
    assert second["state"] == "follow_up_questioning"
    assert second["pending_recommendation_confirmation"] is False
    assert second["recommendation"] is None
