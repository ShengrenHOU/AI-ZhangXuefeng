# Recommendation Explainer

## Purpose

Translate recommendation outputs into family-readable language without flattening risk or inventing unsupported certainty.

## When To Use

- recommendation card copy
- compare summaries
- family summary export
- explanation promptpack or adapter changes

## When Not To Use

- source governance
- hard safety guardrails

## Required Inputs

- recommendation output
- risk warnings
- user or family context when available

## Output Expectations

- clear fit reasons
- clear risk warnings
- plain-language summary for family discussion
- source-aware wording

## Hard Constraints

- do not rewrite risk away
- do not convert probabilistic guidance into certainty language
- do not expose internal source IDs or trace fields in default UI language
