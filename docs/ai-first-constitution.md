# AI-First Constitution

## Core Stance

`gaokao-mvp` is an AI-first product for Chinese students and families.

The model is the main reasoning engine.

The repository exists to give the model:

- memory
- workflow orchestration
- governed knowledge
- open retrieval
- streaming UX
- auditability
- minimum guardrails

The repository does not exist to replace the model as the final recommender.

## Product Principles

- AI-first, not workflow-first
- chat-first, not tool-dashboard-first
- knowledge as trusted memory, not candidate boundary
- model-native search first, controlled retrieval fallback second
- source visibility hidden by default, expandable on demand
- equal conversation, no elitist or patronizing language
- China-first users and network assumptions

## Runtime Principles

- workflow enhances the model rather than judging it
- recommendation should default to model-led candidate discovery and ranking
- published knowledge stabilizes reasoning but does not define the full candidate universe
- recommendation-core is fallback, hint, and minimum guardrail only
- readiness and conflicts are safety signals, not the main dialogue driver

## UI Principles

- the main product surface is a single chat page
- when recommendation exists, the rail shows a real志愿清单
- dossier summary is secondary to recommendation list
- compare stays inside chat as a native capability

## Knowledge Principles

- external discoveries may enter draft knowledge automatically
- only reviewed records may become published knowledge
- draft must never silently masquerade as published
