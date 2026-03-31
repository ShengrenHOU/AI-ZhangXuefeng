# Skills Index

This repository keeps project-specific skills under `skills/`.

These skills are not generic prompt snippets. They are durable operating rules for:

- repo development
- product behavior boundaries
- knowledge governance
- model assistance constraints

## Development Skills

### `workflow-orchestration`
- Use during implementation, refactor, review handoff, and validation planning
- Defines how execution and review roles should collaborate

### `engineering-principles`
- Use before introducing new abstractions, complex prompt logic, or extra services
- Anchors the repo in simplicity, elegance, and minimum necessary complexity

### `product-constitution`
- Use when making product, UX, copy, or prioritization decisions
- Defines why the project exists and who it is for

### `frontend-assistant-ux`
- Use when changing the assistant UI, conversation layout, cards, or copy
- Keeps the product feeling like a mature AI assistant rather than a demo console

## Runtime Assistance Skills

### `readiness-gate`
- Use when changing intake flow, recommendation gating, or follow-up logic
- Defines when the system may ask, clarify, or recommend

### `recommendation-explainer`
- Use when generating parent-facing recommendation language
- Limits model behavior to explanation, not verdict replacement

### `knowledge-governance`
- Use when collecting, reviewing, promoting, or versioning source material
- Keeps official facts, governed explainers, and generated artifacts separated

### `model-independence`
- Use when adapting to a new foundation model or provider
- Protects the repo from binding its architecture to one base model

## How To Use

- During development: read the relevant skill before changing that area
- During runtime design: encode the skill constraints into workflow, schemas, and prompts
- During review: treat any violation of a hard constraint as a design bug, not a stylistic preference

## Constitutional vs Auxiliary

Constitutional skills:
- `product-constitution`
- `engineering-principles`
- `readiness-gate`
- `knowledge-governance`
- `model-independence`

Execution-support skills:
- `workflow-orchestration`
- `frontend-assistant-ux`
- `recommendation-explainer`

