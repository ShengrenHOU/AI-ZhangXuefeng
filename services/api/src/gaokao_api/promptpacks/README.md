# Runtime Promptpacks

This directory contains the runtime prompt assets consumed by `services/api`.

These files are not repo-constitution skills. They are the model-facing runtime
instruction layer that turns:

- user language
- dossier state
- task timeline
- retrieved context

into model-ready instructions with stable input and output contracts.

## Design Rules

- keep prompts AI-first and family-readable
- allow directional guidance before dossier completeness
- keep recommendation language non-guaranteeing
- avoid leaking internal engineering fields to end users
- prefer Chinese family context and China-first retrieval assumptions

## Layout

- `registry.json`: canonical skill registry and metadata
- `*.md`: prompt templates consumed by code
- `loader.py`: minimal runtime loader and renderer

## Current Runtime Skills

- `intent_router`
- `dossier_updater`
- `directional_guidance`
- `retrieval_planner`
- `recommendation_generator`
- `compare_generator`
- `family_summary_writer`
- `safety_style_guard`
