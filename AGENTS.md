# Gaokao MVP AGENTS Guide

## Scope

This file applies to everything under `E:/research_projects/gaokao-mvp`.

## Product Rules

- This is a product repository, not a generic agent playground.
- The online recommendation path is workflow-first.
- Models may extract, ask follow-up questions, explain, and organize outputs.
- Models may not directly invent school-program recommendations.
- Every recommendation item must keep at least one `source_id`.
- Use English filenames only.

## Write Targets

- Durable engineering truth belongs in `docs/`.
- Published knowledge belongs under `packages/knowledge/data/published/`.
- Draft or unreviewed knowledge belongs under `packages/knowledge/data/draft/`.
- Do not place durable files in the repository root beyond repository metadata.

## Online Runtime Boundaries

- `services/api` owns session flow, dossier persistence, API routing, and output validation.
- `packages/recommendation-core` owns deterministic filtering, scoring, bucket classification, and rule traces.
- `packages/knowledge` owns source records and knowledge version reads.
- `apps/web` owns product UX only and should not hide source or risk metadata.

## Validation

- Run API tests before claiming the backend is ready.
- Run the web build before claiming the frontend scaffold is ready.
- If a feature is stubbed, say so explicitly and keep the interface stable.

