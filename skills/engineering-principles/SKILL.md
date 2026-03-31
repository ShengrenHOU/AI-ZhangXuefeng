# Engineering Principles

## Purpose

Anchor the repository in minimum necessary complexity and durable product quality.

## When To Use

- before adding new services, agent layers, or orchestration abstractions
- before solving a product problem with prompt logic alone
- when deciding whether to generalize or specialize

## When Not To Use

- pure copy edits with no architectural impact
- one-off local debugging that does not change the codebase

## Required Inputs

- the problem to solve
- the current implementation shape
- the expected user-facing behavior

## Output Expectations

- the simplest change that preserves correctness
- explicit reasoning for any new abstraction
- rejection of unnecessary complexity

## Core Principles

- use Occam's razor by default
- prefer simple, elegant, testable flows over clever prompt tricks
- keep product logic outside prompts when it needs determinism
- prefer workflow clarity over agent mystique
- optimize for families actually using the product, not for demo effect

## Hard Constraints

- do not hide structural problems inside prompts
- do not add a second system when one clear system is enough
- do not make a base model responsible for business rules
- if a rule matters for correctness or safety, encode it in code or schema

