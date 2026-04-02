# Gaokao MVP AGENTS Guide

## Scope

This file applies to everything under `E:/research_projects/gaokao-mvp`.

## Product Rules

- This is an AI-first product repository, not a generic agent playground.
- The online recommendation path is model-led.
- Workflow exists to organize turns, memory, retrieval, streaming, and auditability.
- Published knowledge is trusted context, not the recommendation boundary.
- Model-native search is preferred when available; controlled retrieval remains fallback.
- Code should keep minimum hard guardrails, provenance, and auditability instead of replacing the model as the main recommender.
- Every recommendation item must keep at least one `source_id`.
- The product primarily serves Chinese students and families.
- Assume a China-based network environment for retrieval choices and operational defaults.
- Prefer China-friendly search sources and prioritize Chinese official/education domains such as `gov.cn`, `edu.cn`, provincial examination authorities, and university admissions sites.
- Use English filenames only.

## Write Targets

- Durable engineering truth belongs in `docs/`.
- Published knowledge belongs under `packages/knowledge/data/published/`.
- Draft or unreviewed knowledge belongs under `packages/knowledge/data/draft/`.
- Do not place durable files in the repository root beyond repository metadata.

## Online Runtime Boundaries

- `services/api` owns session flow, dossier persistence, API routing, runtime prompt execution, retrieval orchestration, streaming, and output validation.
- `packages/recommendation-core` is fallback, hint, and minimum guardrail only.
- `packages/knowledge` owns source records and knowledge version reads.
- `apps/web` owns product UX only and should keep source links and provenance hidden by default unless the user explicitly drills down.

## Validation

- Run API tests before claiming the backend is ready.
- Run the web build before claiming the frontend scaffold is ready.
- If a feature is stubbed, say so explicitly and keep the interface stable.
