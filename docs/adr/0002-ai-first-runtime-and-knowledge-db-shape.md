# ADR 0002: AI-first Runtime and Layered Knowledge Database

## Decision

Adopt an AI-first runtime inside a single API service, and target a single
layered knowledge database as the long-term knowledge shape.

## Context

The repository has moved away from a rule-first shortlist tool and toward a
model-led recommendation product. The remaining architectural question is
whether to split services early or keep a monolithic API while the runtime,
knowledge lifecycle, and streaming contracts are still evolving.

At the same time, knowledge currently lives in file form, but the long-term
product needs a proper database-backed knowledge layer for:

- historical admission records
- curriculum and requirement changes
- review workflow
- publication versions
- source traceability

## Decision Details

- keep a single API service for the MVP and early production shape
- keep SSE as the primary streaming protocol
- keep chat as the only formal product entry point
- keep open web retrieval enabled by default but degradable
- keep file-based knowledge as a temporary ingestion source
- move toward a single layered knowledge database rather than multiple databases
- keep `recommendation-core` only as fallback, hint, and minimum guardrail

## Consequences

- implementation speed stays high during the core product-shaping phase
- retrieval, streaming, and runtime prompt execution remain easy to trace
- future PostgreSQL migration remains possible without redoing product contracts
- knowledge operations can evolve toward a proper database without forcing an early service split
- recommendation stays model-led while still retaining minimum audit and fallback capacity
