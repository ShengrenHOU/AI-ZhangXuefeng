# Readiness Gate

## Purpose

Provide minimum safety and maturity guardrails without reducing the model to a mechanical field collector.

## When To Use

- intake flow changes
- session state transitions
- recommendation trigger logic
- follow-up prompting logic

## When Not To Use

- pure copy polish that does not affect recommendation eligibility

## Required Inputs

- current dossier
- current missing fields
- current conflicts
- current user message

## Output Expectations

- one of: ask, clarify, guide, or recommend
- explicit missing field hints when useful
- explicit conflict list when real conflicts exist
- minimum recommendation eligibility, not a full replacement for model judgment

## Gate Rules

- if key fields are missing, the system may still give directional guidance before asking one high-value follow-up
- if constraints conflict, the system should clarify before presenting a strong recommendation
- recommendation should stay reversible when new information arrives

## Minimum Recommendation Gate

Required:
- province
- target year
- rank or score
- subject combination
- at least one preference or constraint

Preference or constraint includes:
- major interests
- tuition budget
- city preference
- adjustment acceptance
- risk appetite

## Hard Constraints

- do not guarantee admission
- do not let obvious hard conflicts pass silently
- do not present a fully precise recommendation when core information is almost empty
- keep recommendation reversible when new information arrives
