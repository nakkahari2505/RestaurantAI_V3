# RestaurantAI V2 — Milestone 1

This milestone introduces a safe parallel V2 semantic-planner path without removing the existing V1/RAL capabilities.

## New core grammar

Time × Store × Channel × KPI × Operation

Plus:
- conversation context
- spelling/grammar tolerance
- automatic comparison semantics for performance requests
- presentation selection hooks

## New files

- services/semantics/business_query_schema.py
- services/semantics/business_query_parser.py
- services/semantics/conversation_state.py
- services/analytics/business_query_engine.py
- services/presentation/business_query_presenter.py

## Modified file

- services/routing/message_router.py

## First target questions

- "what was my day before yesterday's sale"
- "how is my YTD performance"

The V2 path is intentionally additive: product/category/item questions and operations not yet supported by the V2 executor fall back to the existing proven RAL/V1 routes.

## Model

The V2 planner defaults to `gpt-5.4-mini` with medium reasoning and falls back to `gpt-5-mini` if needed. Override with the `RESTAURANTAI_PLANNER_MODEL` environment variable.

## Safety

No existing .env values were modified. The distributable zip intentionally excludes `.env`, runtime state, generated reports and Python caches.
