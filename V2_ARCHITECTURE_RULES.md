# RestaurantAI V2 — Frozen Architecture Rules

## Blind rule
No business question, report, dashboard, wording pattern, or client request gets a dedicated program merely because that request appeared.

Every core management request must be composed from:

**TIME × STORE × CHANNEL × KPI × OPERATION**

Conversation context, language/spelling tolerance, comparison, grouping, and presentation are supporting semantics around that grammar.

## Failure rule
When a new question fails, do not add a handler for that question. Identify which reusable primitive, semantic rule, operation, executor, or presentation rule is missing and improve that general layer.

## Semantic planner
GPT translates natural WhatsApp language into a complete structured BusinessQuery. It does not calculate business numbers.

## Deterministic engine
Python/data logic calculates all metrics and comparisons. GPT is never the numerical source of truth.

## Existing V1 code
Existing dedicated V1 handlers may remain temporarily as compatibility fallbacks. No new question-specific handlers are to be added. They should gradually become renderers/executors behind the generic planner where useful.

## Examples are tests, not capabilities
Phrases such as “day before yesterday sales” or “YTD performance” are evaluation cases only. They must succeed because the general grammar resolves their Time/KPI/Operation/etc., never because a dedicated route exists.

## BusinessQuery v3.1 semantic primitives
The five-factor backbone remains unchanged. Rich analytical meaning is preserved through generic sub-semantics for selection/ranking, KPI conditions, contribution and treatment/control pre-post analysis. PPNOC is vocabulary for the generic intervention structure, not a dedicated capability.
