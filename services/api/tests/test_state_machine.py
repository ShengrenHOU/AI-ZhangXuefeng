from __future__ import annotations

from pathlib import Path

from knowledge_base import KnowledgeRepository
from recommendation_core import RecommendationCore
from recommendation_core.models import StudentDossier

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
    assert result["state"] == "result_explanation"
    assert result["readiness"]["level"] == "ready_for_recommendation"
    assert result["pending_recommendation_confirmation"] is False
    assert result["recommendation"] is not None


def test_state_machine_recommends_only_after_affirmation() -> None:
    machine = make_machine()
    state = machine.initialize()
    first = machine.handle_message(
        state,
        "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近。",
    )
    assert first["state"] == "result_explanation"
    assert first["pending_recommendation_confirmation"] is False
    assert first["recommendation"] is not None
    assert first["recommendation"]["items"]
    assert first["field_provenance"]
    assert first["recommendation_versions"]


def test_state_machine_accepts_natural_chinese_confirmation() -> None:
    machine = make_machine()
    state = machine.initialize()
    first = machine.handle_message(
        state,
        "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近。",
    )
    assert first["state"] == "result_explanation"
    second = machine.handle_message(state, "是的，就按照这些条件推荐即可。")
    assert second["state"] == "result_explanation"
    assert second["recommendation"] is not None


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
    assert result["state"] == "directional_guidance"
    assert result["recommendation"] is None
    assert "物化生" in result["assistant_message"] or "方向判断" in result["assistant_message"]
    assert "位次或分数" in result["assistant_message"] or "选科组合" in result["assistant_message"]


def test_state_machine_preserves_confirmation_but_allows_negative_reply() -> None:
    machine = make_machine()
    state = machine.initialize()
    first = machine.handle_message(
        state,
        "河南，位次: 65000，选科是物化生，预算: 6500，想学计算机，接受调剂。",
    )
    assert first["state"] == "result_explanation"
    second = machine.handle_message(state, "我还想改一下条件，先别正式推荐。")
    assert second["state"] == "follow_up_questioning"
    assert second["pending_recommendation_confirmation"] is False
    assert second["recommendation"] is not None


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
    assert second["recommendation"] is not None


def test_state_machine_reconfirms_when_user_changes_condition_during_confirmation() -> None:
    machine = make_machine()
    state = machine.initialize()
    machine.handle_message(
        state,
        "河南，位次: 65000，选科是物化生，预算: 6500，想学计算机，接受调剂。",
    )
    second = machine.handle_message(state, "可以，不过预算改成8000再推荐。")
    assert second["state"] == "result_explanation"
    assert second["pending_recommendation_confirmation"] is False
    assert second["recommendation"] is not None
    assert second["dossier"]["family_constraints"]["annual_budget_cny"] == 8000


def test_state_machine_does_not_extract_ai_from_common_english_words() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(state, "wait，我还想再想一下，我们沟通下。")
    assert result["dossier"]["major_interests"] == []


def test_retrieval_excludes_subject_restricted_programs_when_subjects_missing() -> None:
    machine = make_machine()
    dossier = StudentDossier(
        province="henan",
        target_year=2026,
        rank=65000,
        score=650,
        major_interests=["computer_science"],
    )
    dossier.family_constraints.annual_budget_cny = 6500
    retrieved = machine._retrieve_knowledge_slice(dossier)
    assert all(not candidate["subject_requirements"] for candidate in retrieved["candidates"])


def test_state_machine_extracts_rank_score_budget_and_out_of_province_intent_from_natural_sentence() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "排名大概是3000，选科目是物理和生物，我喜欢计算机，学费预算很低我是普通家庭。我想走出河南，分数大概是考了640分左右，您觉着我需要选什么呢？",
    )
    assert result["dossier"]["rank"] == 3000
    assert result["dossier"]["score"] == 640
    assert result["dossier"]["family_constraints"]["annual_budget_cny"] == 6000
    assert result["dossier"]["family_constraints"]["distance_preference"] == "nationwide"
    assert result["dossier"]["subject_combination"] == ["biology", "physics"]
    assert result["dossier"]["major_interests"] == ["computer_science"]
    assert "rank_or_score" not in result["readiness"]["missing_fields"]


def test_state_machine_gives_directional_guidance_for_multi_intent_question() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "我是河南考生，家里条件一般，想稳一点，最好离家近些。我是理科生，我想知道都有哪些选科组合，然后你推荐我选什么专业。",
    )
    assert result["state"] in {"directional_guidance", "follow_up_questioning"}
    assert "方向" in result["assistant_message"] or "选科组合" in result["assistant_message"]
