# Gaokao Assistant MVP

`gaokao-mvp` is a product-first gaokao planning assistant. The online runtime uses a typed dialogue state machine, a deterministic recommendation core, Xiaomi MiMo API compatibility for model access, and published knowledge data. Offline knowledge operations are separated from the user-facing recommendation path.

## Workspace Shape

- `apps/web`: Next.js product shell
- `services/api`: FastAPI online runtime and session state machine
- `packages/types`: shared contracts and JSON schemas
- `packages/recommendation-core`: deterministic recommendation engine
- `packages/knowledge`: published and draft knowledge data plus readers
- `tools/ingestion`: import and promotion scripts
- `docs`: architecture, contracts, governance, collaboration

## Quick Start

### Web

```powershell
cd E:\research_projects\gaokao-mvp
pnpm install
pnpm build:web
```

### API

```powershell
cd E:\research_projects\gaokao-mvp
py -m venv .venv
.\.venv\Scripts\python -m pip install --upgrade pip
.\.venv\Scripts\python -m pip install -e packages\recommendation-core -e packages\knowledge -e services\api
.\.venv\Scripts\python -m pytest services\api\tests
.\.venv\Scripts\uvicorn gaokao_api.main:app --app-dir services\api\src --reload
```

If `DATABASE_URL` is unset, the API falls back to a local SQLite file for development. The repository still treats PostgreSQL as the target runtime shape.

## Xiaomi MiMo API Configuration

The API layer is prepared for Xiaomi MiMo's OpenAI-compatible endpoint:

- base URL: `https://api.xiaomimimo.com/v1`
- chat endpoint: `https://api.xiaomimimo.com/v1/chat/completions`
- auth: either `api-key: $MIMO_API_KEY` or `Authorization: Bearer $MIMO_API_KEY`
- recommended phase-1 model default: `mimo-v2-flash`

Environment variables:

```powershell
$env:MIMO_API_KEY="your-key"
$env:MIMO_MODEL="mimo-v2-flash"
$env:MIMO_BASE_URL="https://api.xiaomimimo.com/v1"
```

## Current Scope

- single province: `henan`
- single cycle: `2026`
- dialogue-first intake with progressive dossier completion
- deterministic recommendation buckets: `reach`, `match`, `safe`
- published knowledge only in the online chain

## Not Yet Implemented

- external knowledge operations runtime
- real Xiaomi MiMo chat-completions execution
- human review console
- multi-province datasets
