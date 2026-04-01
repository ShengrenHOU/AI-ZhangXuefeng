from __future__ import annotations

from pathlib import Path

from gaokao_api.llm import ArkCodingPlanClient
from gaokao_api.promptpacks import RuntimePromptRegistry


def test_promptpack_registry_loads_expected_runtime_skills() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    registry = RuntimePromptRegistry(repo_root / "services" / "api" / "src" / "gaokao_api" / "promptpacks")

    skill_ids = {asset.skill_id for asset in registry.list_assets()}
    assert skill_ids == {
        "intent_router",
        "dossier_updater",
        "directional_guidance",
        "retrieval_planner",
        "recommendation_generator",
        "compare_generator",
        "family_summary_writer",
        "safety_style_guard",
    }


def test_promptpack_render_works_for_intent_router() -> None:
    repo_root = Path(__file__).resolve().parents[3]
    registry = RuntimePromptRegistry(repo_root / "services" / "api" / "src" / "gaokao_api" / "promptpacks")

    rendered = registry.render(
        "intent_router",
        dossier={"province": "henan"},
        missing_fields=["rank_or_score"],
        conflicts=[],
        readiness_level="near_ready",
        user_message="帮我先看看方向。",
    )

    assert "henan" in rendered
    assert "rank_or_score" in rendered
    assert "帮我先看看方向" in rendered


def test_external_retrieval_queries_do_not_include_raw_user_text() -> None:
    client = ArkCodingPlanClient()

    plan = client.retrieve_queries(
        dossier={
            "province": "henan",
            "target_year": 2026,
            "major_interests": ["computer_science"],
            "subject_combination": ["physics", "chemistry"],
        },
        user_message="我是张三，身份证后四位1234，帮我查一下河南2026计算机的公开信息。",
    )

    assert plan.queries
    joined = " ".join(plan.queries)
    assert "张三" not in joined
    assert "1234" not in joined
    assert "身份证" not in joined
