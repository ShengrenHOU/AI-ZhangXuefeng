# Knowledge Governance

## Goal

Define how source material becomes governed product context without polluting
the online runtime with unstable or unreviewed knowledge.

## Runtime Rule

- new source material starts in `draft`
- only reviewed records can be promoted to `published`
- published knowledge must record source URL, source type, year, fetch time, and version
- conflicts are tracked before promotion
- the online runtime trusts only published knowledge as governed memory
- open-web retrieval may enrich candidate discovery and explanation, but does not silently overwrite the published layer

## Target Data Shape

The target knowledge shape is a single layered knowledge database.

The logical layers are:

- sources
- parsed records
- reviewed records
- published knowledge
- source chunks
- review tasks
- publish versions

## Promotion Flow

1. collect raw source
2. normalize into repository or database-ready shape
3. inspect conflicts and missing fields
4. mark as `reviewed`
5. promote to `published`

## Transition Rule

During MVP:

- file-based knowledge may continue to exist as ingestion input
- publication logic should remain compatible with later database-backed reads
- online contracts must not depend on whether published knowledge came from files or the future database
- automatic draft writeback is allowed, but automatic publish is not
