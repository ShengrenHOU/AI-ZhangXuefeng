# Gaokao Assistant MVP

`gaokao-mvp` is a product-first gaokao planning assistant. The online runtime uses a typed dialogue state machine, a deterministic recommendation core, Ark Coding Plan's OpenAI-compatible endpoint for model access, and published knowledge data. Offline knowledge operations are separated from the user-facing recommendation path.

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

## Ark Coding Plan Configuration

The API layer is prepared for Ark Coding Plan's OpenAI-compatible coding endpoint:

- base URL: `https://ark.cn-beijing.volces.com/api/coding/v3`
- use the Coding Plan endpoint, not `https://ark.cn-beijing.volces.com/api/v3`
- auth: Ark API Key from Volcano Engine console
- current default model: `minimax-m2.5`

Environment variables:

```powershell
$env:ARK_API_KEY="your-key"
$env:ARK_MODEL="minimax-m2.5"
$env:ARK_BASE_URL="https://ark.cn-beijing.volces.com/api/coding/v3"
```

## Current Scope

- single province: `henan`
- single cycle: `2026`
- dialogue-first intake with progressive dossier completion
- deterministic recommendation buckets: `reach`, `match`, `safe`
- published knowledge only in the online chain

## Not Yet Implemented

- external knowledge operations runtime
- real Ark Coding Plan live execution
- human review console
- multi-province datasets
