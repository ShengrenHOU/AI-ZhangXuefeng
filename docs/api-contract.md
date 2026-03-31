# API Contract

## Endpoints

- `POST /api/session/start`
- `POST /api/session/{thread_id}/message`
- `GET /api/session/{thread_id}/dossier`
- `POST /api/recommendation/run`
- `POST /api/recommendation/compare`
- `GET /api/sources/{source_id}`
- `POST /api/export/family-summary`
- `POST /api/feedback`

## Response Guarantees

- chat responses always include `thread_id`, `dossier`, and `state`
- recommendation responses always include `items`, `trace_id`, `rules_version`, and `knowledge_version`
- source lookups expose source type, year, publication status, and fetch metadata

