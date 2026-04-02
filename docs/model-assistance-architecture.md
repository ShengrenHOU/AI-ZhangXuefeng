# Model Assistance Architecture

## Overview

This repository now treats the model as the runtime decision engine, while code
acts as the scaffold around it.

The long-lived assets are:

- workflow
- knowledge
- structure
- runtime promptpacks

The model is expected to understand intent, update dossier memory, request
context, generate directional guidance, recommend options, compare candidates,
and summarize advice for families.

The code is expected to:

- organize the turn loop
- maintain durable state
- retrieve governed context
- keep minimal safety and auditability
- stay replaceable across model vendors

## Four Support Layers

### `skills/`

These remain repository and governance assets for:

- developers
- product rules
- knowledge operations
- architecture boundaries

They define what the repo stands for. They are not the runtime prompt layer.

### `services/api/.../promptpacks/`

This is the runtime prompt asset layer consumed directly by code.

It defines:

- which runtime skill exists
- what input keys it expects
- what output keys it must produce
- which model route it should use

Current runtime skills include:

- `intent_router`
- `dossier_updater`
- `directional_guidance`
- `retrieval_planner`
- `recommendation_generator`
- `compare_generator`
- `family_summary_writer`
- `safety_style_guard`

### `packages/knowledge/`

This is the governed context substrate.

- published official facts
- published governed explainers
- source metadata
- knowledge versioning
- future database-backed publication views

Published knowledge is a trusted context layer, not the full candidate
universe.

### `packages/types/`

This is the structural contract layer.

- dossier shape
- conversation action semantics
- recommendation output
- source and trace records

These contracts should survive model-provider changes.

## Runtime Principle

The runtime is AI-first:

- workflow organizes the turn
- promptpacks translate product intent into model-ready instructions
- knowledge retrieval enriches the model context
- minimal guardrails keep outputs safe and auditable

The model should not be reduced to a field collector.

## Routing Principle

- `instant` handles intent, memory updates, lightweight guidance, and light compare
- `deepthink` handles formal recommendation, complex compare, and family summary
- `/stream` is the formal delivery channel for recommendation and compare output
- SSE remains the primary runtime protocol unless product needs change materially
- model-native search should be preferred when available, with controlled retrieval as fallback

## Model Responsibilities

The model may:

- understand user intent
- extract dossier updates
- propose the next best question
- give directional guidance before full completeness
- generate structured recommendations
- compare options
- write family-facing summaries

The model must not:

- guarantee admission
- fabricate source-backed facts as certainties
- expose internal trace, provenance, or engineering-only fields to users

## Swapability Principle

Changing the base model should primarily affect:

- adapter configuration
- parsing robustness
- runtime promptpacks
- model-route selection

It should not require rewriting:

- product constitution
- governed knowledge
- output schemas
- audit records

## Knowledge Evolution Principle

- short term: file-based knowledge remains a valid ingestion source
- medium term: the product should read published knowledge from a layered database
- long term: model-native open-web retrieval remains preferred, while controlled retrieval stays fallback and draft writeback stays governed
