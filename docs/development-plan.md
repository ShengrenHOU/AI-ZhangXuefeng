# Development Plan

## Purpose

This document is the primary development plan for `gaokao-mvp`.

It defines:

- the current system shape
- the target MVP runtime shape
- the staged implementation order
- the fixed architectural decisions that should not be reopened casually

Topic documents such as `product.md`, `architecture.md`, and
`model-assistance-architecture.md` support this plan, but do not replace it.

## Locked Decisions

- single API service first
- SSE as the primary streaming protocol
- chat as the only formal product entry point
- open web retrieval enabled by default but degradable
- knowledge target shape is a single layered knowledge database
- file-based knowledge remains as a transition input source during MVP
- `recommendation-core` remains as fallback, hint, and minimum guardrail only
- sources stay hidden by default and expand only when the user asks

## Current Structure

- `apps/web`
  - chat UI
  - current recommendation rail
  - task timeline rendering
  - stream consumption
- `services/api`
  - session routing
  - state-machine orchestration
  - runtime promptpacks
  - retrieval
  - streaming responses
  - persistence
- `packages/knowledge`
  - draft and published file knowledge
- `packages/recommendation-core`
  - fallback scoring and minimum guardrails
- `packages/types`
  - shared contracts and schemas
- `tools/ingestion`
  - source normalization and publication helpers

## Target MVP Runtime Shape

### Product Surface

- the product surface is a single chat-first experience
- compare and source drill-down are triggered from chat, not from top-level navigation
- the main UI keeps:
  - chat flow
  - lightweight task trace
  - current recommendation and previous-version context

### Runtime Loop

The online runtime should converge on this loop:

1. understand
2. update_memory
3. plan
4. gather
5. respond
6. reflect

The state machine remains, but only as the orchestrator around the model.

### Runtime Prompt Layer

The runtime prompt layer lives in:

- `services/api/src/gaokao_api/promptpacks/`

The first stable runtime skills are:

- `intent_router`
- `dossier_updater`
- `directional_guidance`
- `retrieval_planner`
- `recommendation_generator`
- `compare_generator`
- `family_summary_writer`
- `safety_style_guard`

### Retrieval Policy

- published knowledge is always the first formal context source
- open web retrieval is enabled by default, but must degrade safely
- retrieval queries must use normalized dossier fields only
- China-first search assumptions apply by default
- low-quality open-web results may inform the model but must not override governed knowledge blindly

### Persistence Policy

- SQLite remains the MVP default
- repositories and schema evolution must remain compatible with later PostgreSQL migration
- persisted runtime entities must include:
  - thread
  - message
  - dossier snapshot
  - recommendation
  - recommendation versions
  - task timeline
  - field provenance
  - knowledge version
  - model version

## Implementation Stages

### Stage A: AI-first Runtime Consolidation

- make `promptpacks/` the primary runtime instruction layer
- route state-machine decisions through runtime skills before falling back to hardcoded behavior
- keep deterministic extraction only as supporting memory enrichment, not as the main conversation driver
- unify recommendation, compare, and refinement around `/stream`

### Stage B: Chat-native Product Consolidation

- keep the chat page as the only formal product surface
- make compare fully chat-triggered
- keep recommendation versions visible in the rail
- keep task trace lightweight and readable
- retain `/compare` and `/sources` only as compatibility and drill-down pages

### Stage C: Knowledge Database Transition

- define the target single-database layered schema
- continue using file knowledge as ingestion input during the transition
- add publication flow that can write to the database without changing product contracts
- gradually move online published reads to the database-backed published layer

### Stage D: SQLite-first Hardening

- harden thread recovery
- harden recommendation and version recovery
- harden timeline and provenance recovery
- keep migration semantics compatible with PostgreSQL

## Non-Goals For This Stage

- no microservice split
- no WebSocket-first runtime
- no default source-link-heavy UI
- no rule-first recommendation engine comeback
- no immediate full migration from file knowledge to database before the schema is stable
