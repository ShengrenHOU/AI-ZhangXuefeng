# Architecture

## Runtime Split

The repository uses two runtime lanes:

- online lane: AI-first chat recommendation workflow
- offline lane: knowledge ingestion, normalization, review, and publication

Only the online lane is part of the current product runtime.

## Online Request Flow

1. the user sends a message
2. the online workflow updates session memory and dossier state
3. the model interprets intent through runtime promptpacks
4. the system gathers published knowledge and optional open-web context
5. the model returns either:
   - a follow-up
   - directional guidance
   - a recommendation
   - a comparison
   - a refinement
6. the API stores recommendation versions and task timeline
7. the frontend renders chat, task trace, and current suggestion state

## Module Boundaries

- `apps/web`: chat UI, current shortlist rail, task timeline, stream rendering
- `services/api`: session flow, runtime promptpacks, retrieval orchestration, stream APIs, persistence
- `packages/recommendation-core`: fallback, guardrail, and hint layer
- `packages/knowledge`: published and draft knowledge reads plus source records
- `packages/types`: contracts shared by backend and frontend

## Runtime Prompt Layer

The runtime prompt assets live under:

- `services/api/src/gaokao_api/promptpacks/`

This layer is distinct from repo skills:

- `skills/` define durable repo principles
- `promptpacks/` define runtime model instructions consumed by code

## Design Constraints

- online recommendation never depends on draft knowledge
- external retrieval must degrade safely
- recommendation text must remain family-readable
- recommendation items keep internal source trace even when the UI hides links
- workflow should enhance the model, not replace it as the main recommender
