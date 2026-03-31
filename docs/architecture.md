# Architecture

## Runtime Split

The repository uses two runtime lanes:

- online lane: chat-driven recommendation workflow
- offline lane: knowledge ingestion, normalization, review, and publication

Only the online lane is implemented in phase 1.

## Online Request Flow

1. user sends a message
2. session state machine extracts a dossier patch
3. missing fields are checked
4. the assistant either asks a follow-up question or triggers recommendation generation
5. the recommendation core filters, scores, and buckets candidates
6. published knowledge records are attached as evidence
7. the API returns structured cards plus an assistant-facing summary

## Module Boundaries

- `apps/web`: UI shell, chat panel, dossier panel, shortlist, compare, source views
- `services/api`: session storage, API routes, state transitions, export assembly
- `packages/recommendation-core`: deterministic scoring logic
- `packages/knowledge`: source data and published knowledge reads
- `packages/types`: JSON schemas and frontend contracts

## Design Constraints

- online recommendation never reads draft knowledge
- explanation cannot override rule decisions
- recommendation traces must include rule and knowledge versions
- source metadata is first-class UI data, not debug-only data

