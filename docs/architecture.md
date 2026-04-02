# Architecture

## Runtime Split

The repository uses two runtime lanes:

- online lane: AI-first chat recommendation workflow
- offline lane: knowledge ingestion, normalization, review, and publication

Only the online lane is part of the current product runtime.

## Topology

- one API service first
- one frontend application
- one shared contract layer
- one layered knowledge target database in the long term

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
- `services/api`: session flow, AI-first orchestration, runtime promptpacks, retrieval orchestration, stream APIs, persistence
- `packages/recommendation-core`: fallback, guardrail, and hint layer
- `packages/knowledge`: published and draft knowledge reads plus source records
- `packages/types`: contracts shared by backend and frontend

## Runtime Orchestration Shape

The online loop should be treated as:

1. understand
2. update_memory
3. plan
4. gather
5. respond
6. reflect

The state machine remains the orchestrator, not the main recommender.

## Runtime Prompt Layer

The runtime prompt assets live under:

- `services/api/src/gaokao_api/promptpacks/`

This layer is distinct from repo skills:

- `skills/` define durable repo principles
- `promptpacks/` define runtime model instructions consumed by code

## Design Constraints

- online recommendation never depends on draft knowledge
- external retrieval must degrade safely
- external retrieval queries must never include raw user free text
- recommendation text must remain family-readable
- recommendation items keep internal source trace even when the UI hides links
- workflow should enhance the model, not replace it as the main recommender
- compare and recommendation should both flow through SSE, not separate interaction models
