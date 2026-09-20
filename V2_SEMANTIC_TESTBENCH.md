# RestaurantAI V2 Semantic Planner Test Bench

Purpose: test semantic understanding only, before analytics execution.

Core grammar:

TIME × STORE × CHANNEL × KPI × OPERATION

Supporting signals:
- conversation context
- comparison
- grouping
- presentation intent
- spelling/grammar tolerance
- clarification only when genuinely required

## Endpoint

GET /v2/semantic-test

Required query parameter:
- message

Optional parameters:
- conversation_id
- remember=true|false

The endpoint returns:
- previous_query
- business_query

It does not calculate any business result and does not route to a dedicated capability.

## Context testing

For a multi-turn test, use the same conversation_id and set remember=true on each successful turn. The next turn will receive the previous BusinessQuery as analytical context.

Reset a test conversation with:

POST /v2/semantic-reset?conversation_id=<id>

## Architectural rule

A failed question never creates a question-specific handler. A failure must be traced to a reusable semantic primitive, operation, context rule, execution primitive, or presentation rule.

## Domain Guardrail Torture Cases

These cases verify that the semantic planner protects the RestaurantAI business boundary before deterministic execution.

| User message | Expected domain_status | Expected behavior |
|---|---|---|
| How is the movie? | out_of_domain | Stop before analytics; return business-scope guidance |
| What's the weather today? | out_of_domain | Stop before analytics; return business-scope guidance |
| Tell me a joke | out_of_domain | Stop before analytics; return business-scope guidance |
| Thanks | conversational | Friendly acknowledgement; no analytics execution |
| Good morning | conversational | Friendly acknowledgement; no analytics execution |
| How did we do? | business_query or ambiguous depending on active context | Use context when sufficient; clarify only if genuinely needed |
| What about transactions? | business_query when prior analytical context exists | Preserve prior scope/time and modify KPI |
| Which 3 stores had the lowest APT last month? | business_query | Continue through normal BusinessQuery execution |

Product rule: RestaurantAI means **ask anything about your restaurant business**, not ask anything in the universe.



## Torture-test learnings — 2026-09-07

Frozen corrections from live semantic testing:
- Explicit KPI means explicit KPI only. Example: `How are sales?` => metrics `[sales]`, not an automatic sales/transactions/APT bundle.
- Broad business-health wording may still legitimately request a KPI bundle. Example: `How is the business doing?` may summarize sales, transactions and APT.
- No automatic same-period-last-year comparison. A comparison must be explicit, semantically implied, or inherited from genuine conversation context.
- Missing time on a valid business query defaults deterministically to MTD (`this_month`).
- The presentation must state/show the applied MTD period so the user can see the assumption.
- Regression case: `How are sales?` should resolve to business_query + this_month + metrics=[sales] + no comparison.
