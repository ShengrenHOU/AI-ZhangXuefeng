# Workflow Orchestration

## Purpose

Keep development work structured, reviewable, and proportionate to the problem.

## When To Use

- implementing new features
- refactoring existing modules
- planning tests
- coordinating execution and review roles

## When Not To Use

- broad product strategy debates without concrete implementation impact
- casual note-taking that does not affect repo behavior

## Required Inputs

- the current user request
- the relevant repo area
- existing contracts and docs for that area

## Output Expectations

- a clear write scope
- a clear validation scope
- explicit separation between implementation work and review work

## Development Role Contract

### Executor
- owns edits, commands, local verification, and result collection
- works from the smallest viable change outward
- reports what changed, what was validated, and what remains risky

### Reviewer
- owns criticism, regression risk, missing tests, and mismatch with repo constitution
- reviews behavior before style
- calls out missing validation and hidden complexity

## Hard Constraints

- multi-agent collaboration is for development workflow, not for the live recommendation path
- do not expand into extra roles unless the problem genuinely requires it
- validate before claiming readiness
- keep the implementation and the review perspective distinct

