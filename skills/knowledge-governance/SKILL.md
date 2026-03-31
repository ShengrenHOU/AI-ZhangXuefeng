# Knowledge Governance

## Purpose

Keep online recommendation inputs reviewable, versioned, and traceable.

## When To Use

- source collection
- normalization
- conflict review
- publication flow changes
- source metadata design

## When Not To Use

- UI-only work
- runtime recommendation formatting without source changes

## Required Inputs

- source material
- source metadata
- target knowledge layer
- publication status

## Output Expectations

- proper placement into fact, explainer, or artifact layer
- versioned records
- explicit publication state
- conflict visibility before promotion

## Layer Rules

### Official Facts
- school metadata
- program metadata
- subject requirements
- historical ranks or scores
- plans and tuition
- source URLs and fetch timestamps

### Governed Explanations
- reviewed interpretive text
- risk templates
- parent-friendly translation
- city cost and adjustment guidance

### Generated Artifacts
- recommendation outputs
- compare summaries
- family exports

## Publication Flow

- draft
- reviewed
- published

Only `published` may enter the live recommendation path.

## Hard Constraints

- never mix unreviewed data into live recommendation
- keep version and source metadata attached
- treat conflicting sources as review work, not inference work

