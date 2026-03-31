# Readiness Gate

## Purpose

Control when the system may continue asking questions, when it must clarify conflicts, and when it may produce recommendations.

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

- one of: ask, clarify, or recommend
- explicit missing field list
- explicit conflict list
- deterministic recommendation eligibility

## Gate Rules

- if key fields are missing, the system must ask follow-up questions
- if constraints conflict, the system must clarify before recommending
- only when the dossier is mature and conflict-free may the system recommend

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

- the model may not bypass the gate
- recommendation is never the default action
- clarification takes precedence over recommendation
- recommendation must remain reversible when new information arrives

