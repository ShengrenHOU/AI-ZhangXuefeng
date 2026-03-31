# Model Assistance Architecture

## Overview

This repository treats the model as an assistant to the system, not as the system itself.

The product keeps three long-lived assets independent from any single base model:

- workflow
- knowledge
- structure

## Three Support Layers

### `skills/`

These are behavior and governance assets for:
- developers
- model-assisted runtime design
- repository-level rules

Skills define what should happen, when to use a capability, and what constraints must hold.

### `packages/knowledge/`

This is the live knowledge substrate.

- published official facts
- published governed explainers
- source metadata and versioning

Only published knowledge enters the online recommendation path.

### `packages/types/`

This is the structural contract layer.

- dossier shape
- readiness and conflict semantics
- recommendation output
- source records

These contracts should remain stable even if the model provider changes.

## Model Responsibilities

The model may:
- extract dossier patches
- propose follow-up questions
- explain rule results
- organize family-facing language

The model may not:
- invent recommendation items
- bypass readiness gating
- override Recommendation Core decisions
- bypass source requirements

## Swapability Principle

Changing the base model should primarily affect:
- adapter configuration
- parsing robustness
- prompt phrasing

It should not require rewriting:
- readiness gate
- recommendation core
- knowledge governance
- product constitution

