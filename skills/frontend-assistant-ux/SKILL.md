# Frontend Assistant UX

## Purpose

Make the product feel like a mature Chinese AI assistant, not a prototype dashboard.

## When To Use

- chat surface changes
- result card design
- follow-up card design
- copy and interaction polish
- compare and source page UX changes

## When Not To Use

- backend-only refactors
- schema-only changes with no UI impact

## Required Inputs

- the target user flow
- the current UI state
- the relevant API payloads

## Output Expectations

- a conversation-first experience
- Chinese-first copy
- result cards that feel embedded in the assistant flow
- lightweight dossier visibility without turning the page into a console

## Interaction Rules

- the main reading path should stay in the conversation stream
- result cards should appear inside the dialogue at the right moment
- follow-up and conflict prompts should be visually distinct from final recommendations
- surface only the user-facing meaning of system state, not raw engineering state
- compare and source pages should feel like assistant extensions, not raw API views

## Hard Constraints

- do not default to an engineering dashboard layout
- do not flood the first screen with metadata
- do not leave English helper copy in the main Chinese product flow
- do not make the dossier summary larger than the conversation itself

