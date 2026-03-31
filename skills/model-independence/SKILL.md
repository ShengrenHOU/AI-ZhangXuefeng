# Model Independence

## Purpose

Ensure the system can swap foundation models without rewriting its core product logic.

## When To Use

- model provider changes
- prompt adapter changes
- response parsing changes
- architecture decisions about model coupling

## When Not To Use

- fixed business rules
- knowledge publication rules

## Required Inputs

- model capability assumptions
- current adapter boundaries
- current schemas and workflow contracts

## Output Expectations

- stable behavior when the base model changes
- clear adapter boundaries
- explicit separation between model behavior and business logic

## Stable Assets

These should survive a base-model change:
- workflow
- readiness gate
- schemas
- source governance
- recommendation core
- dossier structure

## Adapter Responsibilities

- transport and API compatibility
- response parsing
- structured output extraction
- reasoning or follow-up drafting

## Hard Constraints

- do not bind the product constitution to a single model vendor
- do not embed business rules into provider-specific prompts
- do not make recommendation eligibility depend on model temperament

