# ADR 0001: Dual Runtime Shape

## Decision

Use a product-first online runtime and keep knowledge operations in a separate offline lane.

## Context

A generic agent harness adds capability, but the online gaokao recommendation chain must remain deterministic, replayable, and auditable.

## Consequences

- the online runtime is implemented as a typed workflow
- recommendation logic stays outside the model layer
- knowledge operations can grow independently without destabilizing user-facing recommendations

