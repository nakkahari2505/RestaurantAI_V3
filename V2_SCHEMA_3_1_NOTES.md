# RestaurantAI V2 — BusinessQuery v3.1

This milestone strengthens the semantic grammar without adding any question-specific handler.

## Frozen backbone

**TIME × STORE × CHANNEL × KPI × OPERATION**

The new fields are structured sub-semantics needed to preserve management meaning all the way to the deterministic engine.

## Added reusable primitives

### Selection / ranking
Captures top/bottom/highest/lowest/best/worst and N.

### KPI conditions
Captures multi-KPI conditional questions, including AND/OR, operator, measure and comparison reference.

### Contribution
Distinguishes contribution to business change from sales mix or a dimension's own growth rate.

### Intervention / control-adjusted pre-post
Captures treatment stores, control stores/remaining stores, intervention date, pre/post windows and net-of-control intent. PPNOC is treated only as business vocabulary for this generic structure, never as a dedicated handler.

### Comparison detail
Preserves richer comparison semantics while keeping the existing comparison field for compatibility.

## Blind rule remains unchanged

If a new question fails, improve a reusable primitive, semantic rule, operation, executor or presentation rule. Never add a handler for that question.
