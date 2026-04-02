from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from knowledge_base import KnowledgeRepository
from recommendation_core import RecommendationCore
from recommendation_core.models import StudentDossier

from gaokao_api.llm import CandidateDiscoveryResult, DiscoveredCandidate, PlannerAction, RecommendationSelection, RecommendationSelectionItem
from gaokao_api.state_machine import SessionStateMachine


class StubPlannerClient:
    def __init__(self, action: PlannerAction, guidance: str | None = None) -> None:
        self._action = action
        self._guidance = guidance or action.reasoning_summary

    def is_configured(self) -> bool:
        return True

    def plan_conversation_action(self, **_: object) -> PlannerAction:
        return self._action

    def update_dossier_patch(self, **_: object) -> dict:
        return {}

    def generate_directional_guidance(self, **_: object) -> str:
        return self._guidance

    def guard_user_facing_text(self, *, draft_output: str, **_: object) -> str:
        return draft_output

    def retrieve_queries(self, **_: object):  # pragma: no cover - not used in these tests
        raise AssertionError("retrieve_queries should not be called in this test")

    def discover_candidates_via_web(self, **_: object) -> CandidateDiscoveryResult:
        return CandidateDiscoveryResult(reasoning_summary="no discovery", candidates=[])

    def extract_web_evidence_for_draft(self, **_: object) -> list[dict]:
        return []


def make_machine(planner_client: object | None = None) -> SessionStateMachine:
    repo_root = Path(__file__).resolve().parents[3]
    knowledge = KnowledgeRepository.from_root(repo_root / "packages" / "knowledge" / "data")
    return SessionStateMachine(
        repository=knowledge,
        recommendation_core=RecommendationCore(),
        planner_client=planner_client,
    )


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
    assert first["state"] == "constraint_confirmation"
    assert first["pending_recommendation_confirmation"] is True
    assert first["recommendation"] is None
    second = machine.handle_message(state, "可以，就按这些条件开始推荐。")
    assert second["state"] == "result_explanation"
    assert second["pending_recommendation_confirmation"] is False
    assert second["recommendation"] is not None
    assert second["recommendation"]["items"]
    assert second["field_provenance"]
    assert second["recommendation_versions"]


def test_state_machine_accepts_natural_chinese_confirmation() -> None:
    machine = make_machine()
    state = machine.initialize()
    first = machine.handle_message(
        state,
        "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近。",
    )
    assert first["state"] == "constraint_confirmation"
    second = machine.handle_message(state, "是的，就按照这些条件推荐即可。")
    assert second["state"] == "result_explanation"
    assert second["recommendation"] is not None


def test_state_machine_recommends_immediately_when_user_explicitly_requests_recommendation() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近，直接给我推荐吧。",
    )
    assert result["state"] == "result_explanation"
    assert result["pending_recommendation_confirmation"] is False
    assert result["recommendation"] is not None


def test_state_machine_still_confirms_when_user_explicitly_asks_for_confirmation_first() -> None:
    machine = make_machine()
    state = machine.initialize()
    result = machine.handle_message(
        state,
        "河南，位次: 70000，physics chemistry biology，预算: 6000，想学电气，稳一点，不接受调剂，离家近，先确认一下再推荐。",
    )
    assert result["state"] == "constraint_confirmation"
    assert result["pending_recommendation_confirmation"] is True
    assert result["recommendation"] is None


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
    assert first["state"] == "constraint_confirmation"
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


def test_state_machine_reconfirms_when_user_changes_condition_during_confirmation() -> None:
    machine = make_machine()
    state = machine.initialize()
    machine.handle_message(
        state,
        "河南，位次: 65000，选科是物化生，预算: 6500，想学计算机，接受调剂。",
    )
    second = machine.handle_message(state, "可以，不过预算改成8000再推荐。")
    assert second["state"] == "constraint_confirmation"
    assert second["pending_recommendation_confirmation"] is True
    assert second["recommendation"] is None
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


def test_directional_guidance_retrieval_keeps_subject_restricted_candidates_when_subjects_missing() -> None:
    machine = make_machine()
    dossier = StudentDossier(
        province="henan",
        target_year=2026,
        rank=65000,
        score=650,
        major_interests=["computer_science"],
    )
    dossier.family_constraints.annual_budget_cny = 6500

    retrieved = machine._retrieve_knowledge_slice(dossier, strict_subject_match=False)

    assert any(candidate["subject_requirements"] for candidate in retrieved["candidates"])


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


def test_state_machine_uses_planner_guidance_even_without_explicit_recommendation_trigger() -> None:
    planner = StubPlannerClient(
        PlannerAction(
            action="directional_guidance",
            dossier_patch={},
            next_question="你更想先看城市还是专业方向？",
            reasoning_summary="我先给你一个方向判断，再补一个最关键的问题。",
            source_ids=[],
        ),
        guidance="先别急着定学校，我先给你一个方向判断：按你现在的条件，先看省内稳妥工科更合理。",
    )
    machine = make_machine(planner_client=planner)
    state = machine.initialize()
    result = machine.handle_message(state, "我家里条件一般，想稳一点，帮我看看大方向。")
    assert result["state"] == "directional_guidance"
    assert result["model_action"]["action"] == "directional_guidance"
    assert "方向判断" in result["assistant_message"]


def test_state_machine_prefers_planner_follow_up_question_over_fixed_prompt() -> None:
    planner = StubPlannerClient(
        PlannerAction(
            action="ask_followup",
            dossier_patch={},
            next_question="先告诉我你更在意离家近，还是更在意专业本身？",
            reasoning_summary="我先补一个最影响后续判断的问题。",
            source_ids=[],
        )
    )
    machine = make_machine(planner_client=planner)
    state = machine.initialize()
    result = machine.handle_message(state, "河南考生，想学计算机，家里条件一般。")
    assert result["state"] == "follow_up_questioning"
    assert "先告诉我你更在意离家近，还是更在意专业本身？" in result["assistant_message"]


def test_next_question_prefers_planner_question_before_fixed_follow_up_order() -> None:
    machine = make_machine()
    dossier = StudentDossier(province="henan", target_year=2026)
    readiness = machine.evaluate_dossier(dossier)
    planner_action = PlannerAction(
        action="ask_followup",
        reasoning_summary="先补关键条件。",
        next_question="先跟我说一下你更倾向的专业方向，我再顺着帮你收敛。",
    )

    next_question = machine._next_question(dossier, readiness, planner_action)

    assert next_question == "先跟我说一下你更倾向的专业方向，我再顺着帮你收敛。"


def test_materialize_recommendation_run_accepts_web_discovered_candidates() -> None:
    machine = make_machine()
    selection = RecommendationSelection(
        reasoning_summary="按开放检索结果整理出的建议。",
        items=[
            RecommendationSelectionItem(
                program_id="web-program-demo",
                bucket="match",
                fit_reasons=["公开检索显示该专业与你的兴趣更匹配"],
                risk_warnings=["学费仍需以后续章程为准"],
                parent_summary="这是基于公开检索形成的一条稳妥候选。",
            )
        ],
    )
    run = machine._materialize_recommendation_run(
        thread_id="demo-thread",
        selection=selection,
        retrieved_knowledge={
            "candidates": [
                {
                    "program_id": "web-program-demo",
                    "school_id": "web-school-demo",
                    "school_name": "示例大学",
                    "program_name": "人工智能",
                    "city": "Zhengzhou",
                    "city_label": "郑州",
                    "tuition_cny": 6200,
                    "retrieval_score": 0.73,
                    "retrieval_rank": 1,
                    "source_ids": ["web-src-demo"],
                }
            ]
        },
        knowledge_version="web-discovery-preview",
    )

    assert run.items
    assert run.items[0].school_name == "示例大学"
    assert run.items[0].program_name == "人工智能"


def test_merge_discovered_candidates_adds_synthetic_candidates() -> None:
    machine = make_machine()
    merged = machine._merge_discovered_candidates(
        {
            "candidates": [],
            "knowledge_version": "kg-v1",
            "web_results": [],
        },
        CandidateDiscoveryResult(
            reasoning_summary="开放检索发现了更大的候选集合。",
            candidates=[
                DiscoveredCandidate(
                    school_name="示例大学",
                    program_name="人工智能",
                    city="Zhengzhou",
                    tuition_cny=6200,
                    subject_requirements=["physics"],
                    tags=["computer_science"],
                    evidence_summary="学校公开页面显示该专业面向物理考生开放。",
                    source_urls=["https://example.edu.cn/ai"],
                )
            ],
        ),
    )

    assert merged["candidates"]
    assert merged["candidates"][0]["program_id"].startswith("web-program-")
    assert merged["candidates"][0]["source_ids"][0].startswith("web-src-")


def test_knowledge_repository_appends_draft_discoveries() -> None:
    with TemporaryDirectory() as tmpdir:
        repo = KnowledgeRepository.from_root(Path(tmpdir))
        path = repo.append_draft_discoveries(
            province="henan",
            year=2026,
            records=[
                {
                    "school_name": "示例大学",
                    "program_name": "人工智能",
                    "source_urls": ["https://example.edu.cn/ai"],
                    "evidence_summary": "公开页面显示该专业开放招生。",
                }
            ],
        )

        assert path is not None
        assert path.exists()
