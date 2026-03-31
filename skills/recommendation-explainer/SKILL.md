# Recommendation Explainer

## Purpose

Translate deterministic recommendation results into family-readable language without changing the underlying decision.

## When To Use

- recommendation card copy
- compare summaries
- family summary export
- explanation prompt or adapter changes

## When Not To Use

- core candidate filtering
- bucket classification
- source governance

## Required Inputs

- Recommendation Core output
- source IDs
- risk warnings
- user or family context when available

## Output Expectations

- clear fit reasons
- clear risk warnings
- plain-language summary for family discussion
- source-aware wording

## Hard Constraints

- do not add schools or programs that the core did not output
- do not rewrite risk away
- do not explain without source anchors
- do not convert probabilistic guidance into certainty language

