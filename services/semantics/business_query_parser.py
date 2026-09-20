import json
from copy import deepcopy
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from services.core.data_loader import load_auberry_workbook
from services.core.llm_service import llm_service
from services.semantics.builders.channel_builder import (
    build_channel_dictionary,
    build_channel_vocabulary_prompt,
)
from services.semantics.builders.product_builder import (
    build_product_dictionary,
    build_product_vocabulary_prompt,
)
from services.semantics.builders.store_builder import (
    build_store_dictionary,
    build_store_vocabulary_prompt,
)
from services.semantics.business_query_schema import BUSINESS_QUERY_JSON_SCHEMA

DEFAULT_TIMEZONE = "Asia/Kolkata"


def _client_context() -> str:
    data = load_auberry_workbook()
    stores = build_store_dictionary(data=data)
    channels = build_channel_dictionary(data=data)
    products = build_product_dictionary(data=data)
    return (
        build_store_vocabulary_prompt(stores)
        + "\n\n"
        + build_channel_vocabulary_prompt(channels)
        + "\n\n"
        + build_product_vocabulary_prompt(products)
    )


def _instructions(client_context: str, previous_query: dict | None) -> str:
    previous_text = (
        json.dumps(previous_query, ensure_ascii=False)
        if previous_query
        else "No active analytical context."
    )

    return f"""
You are the semantic planning layer of RestaurantAI V2.
Your job is NOT to answer the business question and NOT to calculate numbers.
Translate the manager's natural WhatsApp language into one complete BusinessQuery.

RestaurantAI V2 core analytical grammar:
TIME × STORE × CHANNEL × KPI × OPERATION.

The five factors remain the backbone. Rich management questions may require structured
sub-semantics inside those factors (for example ranking direction/limit, KPI conditions,
contribution, or treatment/control pre-post analysis). Never create or imply a dedicated
question-specific capability.

The model must tolerate spelling mistakes, shorthand, missing punctuation,
casual grammar, abbreviations and fragments typical of WhatsApp.
Interpret meaning, not exact wording.

ACTIVE CLIENT VOCABULARY
{client_context}

CURRENT ANALYTICAL CONTEXT
{previous_text}

DOMAIN GATE — CLASSIFY BEFORE ANALYTICAL EXECUTION
- domain_status=business_query when the message is a restaurant/F&B business-data or management question,
  OR when it is a meaningful analytical follow-up to CURRENT ANALYTICAL CONTEXT.
- domain_status=conversational for harmless social turns such as thanks, hello, good morning, okay, got it,
  or similar acknowledgements that do not ask for business analysis.
- domain_status=ambiguous only when the message may plausibly concern the restaurant business but a competent
  human analyst cannot determine the intended business request even after considering CURRENT ANALYTICAL CONTEXT.
- domain_status=out_of_domain when the user is clearly asking about an unrelated subject such as movies, weather,
  politics, sports, travel, general knowledge, jokes, coding, or another non-restaurant topic.
- NEVER force an out-of-domain or conversational message into TIME × STORE × CHANNEL × KPI × OPERATION semantics.
- RestaurantAI's promise is "ask anything about your restaurant business", not general-purpose chat.
- For conversational or out_of_domain messages, still return a schema-valid BusinessQuery using neutral defaults:
  time.type=unspecified; dates=null; stores=[]; channels=[]; metrics=[]; operation=retrieve; comparison=none;
  comparison_detail.mode=none with null reference dates; group_by=[]; selection disabled; no conditions;
  contribution disabled; intervention disabled; contains_product_dimension=false; presentation=text.
- For out_of_domain, needs_clarification=false and clarification_question=null. Do not interrogate the user.
- For conversational, needs_clarification=false and clarification_question=null.

CONTEXT RULES
- context_relation=new when the new message is self-contained or starts another analysis.
- context_relation=continue when it is a direct follow-up that keeps the analytical frame.
- context_relation=modify when it changes one or more elements of the active frame.
- context_relation=ambiguous only when a competent human analyst would genuinely need clarification.
- Current explicit words override previous context.
- Previous context overrides business defaults.
- Never carry an old store, channel, KPI or period into a clearly self-contained new question.
- Return a COMPLETE resolved semantic query, not only the fields changed by a follow-up.

CORE KPI RULES
- Supported KPIs: sales, transactions, apt, ads, adt.
- Broad business-health/performance language such as "How is the business doing?" may mean metrics=[sales, transactions, apt].
- This is a semantic KPI-bundle rule, not a dedicated question or handler.
- EXPLICIT KPI OVERRIDES BUNDLES: when the user names one or more KPIs, include only those explicitly requested KPIs unless active context clearly makes the turn a follow-up that retains others. Never silently add transactions or APT to an explicit sales-only question.
- A direct "sales/revenue/turnover" value question means metrics=[sales]. The generic word "business" is broad performance language, not a synonym that forces sales-only.
- "bills/orders/transactions" means transactions.
- "average bill/ticket/ATV/AOV/APT" means apt.

TIME RULES
- RestaurantAI operates in an Indian business context. Distinguish BUSINESS/FINANCIAL-YEAR language from CALENDAR-YEAR language instead of treating all year expressions as the same concept.
- BUSINESS / FINANCIAL YEAR: April 1 through March 31.
  - "YTD", "financial YTD", "FYTD", "this financial year so far", and an unqualified business "year to date" mean financial-year-to-date: April 1 of the current financial year through the current date.
  - FY labels use the year in which the financial year ENDS. Example: FY27 = 2026-04-01 through 2027-03-31; FY26 = 2025-04-01 through 2026-03-31.
  - Financial quarters follow the Indian financial year: Q1=Apr-Jun, Q2=Jul-Sep, Q3=Oct-Dec, Q4=Jan-Mar.
  - Explicit expressions such as "Q1 FY27", "FY26", "last financial year", or "current FY" must be resolved according to this financial-year calendar. Use date_range with explicit YYYY-MM-DD dates when the schema has no dedicated relative type for the requested FY/quarter expression.
- CALENDAR YEAR: January 1 through December 31, but only when the user's wording clearly asks for calendar-year semantics.
  - Examples: "this calendar year", "calendar YTD", "CY26", "2026 calendar year", "Jan to date", or equivalent explicit wording.
  - Calendar-year-to-date means January 1 of that calendar year through the current date (or through the explicitly requested as-of date).
  - Use date_range with explicit YYYY-MM-DD dates for calendar-year periods because time.type=ytd is reserved for Indian financial YTD.
- "this year" by itself is business-context language and should normally mean the current financial year / financial YTD, unless the wording clearly indicates a calendar year.
- Preserve the SAME calendar basis in comparisons. Examples:
  - "YTD vs last year" => current financial YTD versus the equivalent elapsed dates of the previous financial year.
  - "this calendar year vs last calendar year same period" => Jan 1 through the current date versus Jan 1 through the equivalent date one year earlier.
  - Never silently switch from financial-year semantics to calendar-year semantics, or vice versa, inside a comparison.
- Recognize today, yesterday, day before yesterday, WTD/this week, last week,
  MTD/this month, last month, QTD/this quarter, last quarter, financial YTD,
  explicit financial-year/quarter expressions, explicit calendar-year expressions,
  explicit dates and explicit date ranges.
- For relative time types leave start_date/end_date null. Python resolves them.
- For a specific explicit date normalize both dates to YYYY-MM-DD.
- For an explicit date range normalize both dates to YYYY-MM-DD.
- Never invent incomplete calendar details.
- DEFAULT TIME RULE: for a new business query with no explicit time and no inherited time from active context, use MTD (time.type=this_month). This is a deliberate RestaurantAI product default, not a guess. Python resolves it to month-start through the current available date.
- Because an omitted time is defaulted to MTD, the eventual answer/presentation must make the applied MTD period visible to the user.
- CALENDAR-POSITION SELECTORS are first-class time concepts, not special question patterns. Understand expressions such as first/second/third/last Sunday, first Monday, second Saturday, last Friday, etc. as selectors that identify concrete calendar dates inside a stated or inherited period. Resolve an unambiguous selector to its actual YYYY-MM-DD date.
- When two calendar-position selectors are compared inside one period, represent the subject date as time.type=specific_date and the comparison date as comparison_detail.mode=custom_period with reference_period populated. Example concept: "second Sunday against first Sunday of this month" means compare the concrete second-Sunday date with the concrete first-Sunday date; do NOT flatten the request to the whole month.
- Calendar-position selectors compose with ordinary period language. "second Sunday of last month", "last Friday of Q1 FY27", and similar expressions should be reasoned from the requested calendar first and then resolved to concrete dates.
- Repetition is a separate concept from selection. A request such as "first Saturday vs second Saturday for each of the last six months" asks for the same selector relationship repeated independently inside each month. Never flatten that into one continuous six-month date range. If the current BusinessQuery schema cannot faithfully encode the repeated series, preserve that limitation rather than inventing a different time meaning.

PRODUCT BOUNDARY
- This V2 milestone intentionally executes only the core Time/Store/Channel/KPI/Operation layer.
- If the user mentions or filters a menu category or item, set contains_product_dimension=true.
- Do not drop that product meaning. The legacy product-aware RAL path will handle it.
- Otherwise set contains_product_dimension=false.

STORE / CHANNEL SEMANTICS
- STORE is an analytical dimension, not merely an entity lookup. Understand requests about one store, several stores, all stores, store-wise breakdowns, store-to-store comparisons, ranking across stores, and filtering stores by KPI conditions.
- If no store is specified, stores=[] means company/all stores. When the question asks "which stores", "stores that", "by store", "store-wise", "across stores", top/bottom stores, or otherwise requires evaluating the store population, keep stores=[] and use group_by=[store] so execution evaluates stores individually.
- If no channel is specified, channels=[] means all channels.
- NEVER invent a store or channel. Every populated value in stores[] or channels[] MUST be a canonical name from ACTIVE CLIENT VOCABULARY.
- Fuzzy resolution is allowed for spelling mistakes, shorthand, omitted words, phonetic variants and casual typing only when the intended canonical entity is sufficiently clear from ACTIVE CLIENT VOCABULARY. Example principle: a close shorthand may resolve to one uniquely plausible canonical store.
- If a user supplies a store/channel name that cannot be confidently resolved to exactly one canonical vocabulary entry, do NOT copy the user's unknown text into stores[]/channels[] and do NOT hallucinate a new entity. Leave that dimension unresolved, set needs_clarification=true, and ask which valid store/channel they meant.
- A valid restaurant business question with an unresolved store/channel remains domain_status=business_query; entity-resolution failure is not out_of_domain.
- If multiple canonical candidates are genuinely plausible, ask for clarification rather than choosing arbitrarily.
- Two or more explicitly named stores can be compared directly within the same time period. In that case operation=compare may be correct while comparison=none, because comparison/comparison_detail represent a REFERENCE-PERIOD comparison, not the fact that two store scopes are being compared.
- When no KPI is named in a broad store-performance comparison, metrics=[sales, transactions, apt] is a sensible performance bundle. When a KPI is explicitly named, preserve only the requested KPI(s).

OPERATION RULES
- retrieve: direct value/request ("how much"/"what is the value").
- compare: explicit comparison between periods OR analytical scopes such as Store A vs Store B.
- rank: best/worst/top/bottom/most/least ranking across a dimension.
- trend: movement over time.
- contribution: asks what is driving/contributing to a change.
- diagnose: asks why performance changed/what caused weakness or strength.
- filter: asks WHICH stores/channels satisfy one or more conditions. "Which" questions must preserve the population dimension and conditions needed to return matching entities, not merely retrieve an aggregate.
- summarize: asks for a concise overall summary.
- RestaurantAI must support analytical questions beyond "how much": WHO/WHICH/WHAT scope questions, rankings, filters, comparisons and multi-condition discovery should be represented compositionally using STORE/CHANNEL + KPI + TIME + OPERATION rather than question-specific handlers.

SELECTION / RANKING RULES
- Use selection.enabled=true whenever words such as highest, lowest, best, worst, top N, bottom N, grew the most, fell the most, improved most or deteriorated most require ordered selection from grouped results.
- highest/best/top/grew most/improved most => direction=top. lowest/worst/bottom/fell most/deteriorated most => direction=bottom.
- Explicit N => limit=N. Singular highest/lowest/best/worst => limit=1.
- Ranking stores requires group_by=[store]; ranking channels requires group_by=[channel].
- sort_metric is the KPI being ranked. sort_measure=value for absolute-level ranking; use the schema's growth/change measure when the wording ranks improvement, decline, growth or deterioration.
- A growth/decline ranking semantically requires an appropriate reference period even when "versus" is omitted. Use the fair comparison rules below.
- Otherwise selection.enabled=false, direction=none, limit=null, sort_metric=null, sort_measure=value.

CONDITIONAL FILTER RULES
- Preserve every requested KPI condition explicitly in conditions.items.
- "Which stores are degrowing this month" is a store-population filter: stores=[], group_by=[store], metric=sales unless another KPI is explicitly named, operation=filter, and a negative sales growth/change condition against the fair previous-period benchmark.
- "Which stores grew this month" similarly means positive sales growth/change by store against the fair previous-period benchmark.
- Example: "sales increased but transactions fell vs last month" means two conditions joined by AND:
  sales growth_pct > 0 versus comparison_period AND transactions growth_pct < 0 versus comparison_period.
- For "which stores have sales growing but transactions falling this month", preserve BOTH metrics, group_by=[store], operation=filter, conditions.logic=and, and two independent conditions: sales growth > 0 AND transactions growth < 0 against the same fair reference period.
- Never collapse multiple KPI conditions into a derived KPI even when mathematically related.
- Growth/degrowth/improved/fell language implies change relative to an appropriate benchmark even if the user does not literally say "compare".
- Use conditions.logic=none and items=[] when no conditional filtering is requested.

CONTRIBUTION RULES
- Contribution means contribution to a CHANGE, not ordinary sales mix and not the contributor's own growth rate.
- For "which channel contributed most to sales growth", set operation=contribution,
  contribution.enabled=true, target_metric=sales, group_dimension=channel,
  basis=absolute_change; use comparison to identify the reference period.
- Selection carries words such as "most", "least", top N or bottom N.
- When contribution is not requested, contribution.enabled=false, target_metric=null,
  group_dimension=none, basis=absolute_change.

INTERVENTION / CONTROL-ADJUSTED PRE-POST RULES
- Business interventions include promotions, product launches, channel launches, pricing changes,
  refurbishments or other initiatives. PPNOC is an F&B/retail term for pre/post net of control.
- This is NOT a dedicated PPNOC question handler. Represent it generically as treatment/control cohorts
  plus pre/post periods inside the five-factor grammar.
- When an intervention analysis is requested, set intervention.enabled=true.
- treatment_stores are the stores exposed to the intervention.
- "remaining/other stores" => control_store_mode=remaining_stores and control_stores=[].
- Explicit control stores => control_store_mode=explicit_stores and preserve those stores.
- Preserve intervention_date when explicit.
- Preserve requested before/after window lengths as window_days_before/window_days_after.
- net_of_control=true when the user asks against/control-adjusted/net of/versus unaffected stores or PPNOC.
- Python will deterministically resolve pre_period and post_period from the intervention date/window when possible.
- Otherwise intervention.enabled=false and all optional intervention values must be null/empty/default.


COMPARISON RULES
- First distinguish RETRIEVAL from EVALUATION using the meaning of the whole request, not individual trigger words.
- RETRIEVAL asks for values/facts (for example sales YTD, transactions yesterday, APT at a store). Do NOT add a benchmark merely to make the answer richer: comparison=none and comparison_detail.mode=none unless comparison is explicitly requested or genuinely inherited from context.
- EVALUATION asks for a judgment about performance/health/doing well or poorly. When that judgment would be materially more meaningful with a fair benchmark, infer the comparison even if the user did not literally say "compare" or "versus".
- Do NOT turn every occurrence of "how", "doing", or "performance" into a comparison. Judge specificity and analytical intent. A sufficiently specific operational question can be answered directly when a benchmark is not necessary to satisfy the request.
- For a broad/generic evaluative current-period request, prefer a fair like-for-like benchmark: current MTD vs previous month same elapsed calendar days; current WTD vs previous week same elapsed weekday span; current QTD vs previous financial quarter same elapsed calendar position; current financial YTD vs previous financial year same elapsed period. Preserve calendar-year semantics when the user explicitly asks for calendar-year analysis.
- When an inferred evaluative comparison is year-over-year, set comparison=same_period_last_year and comparison_detail.mode=same_period_last_year. When it is against the corresponding immediately previous period, set comparison=previous_period and comparison_detail.mode=previous_period.
- Explicit "vs last year/YoY" => comparison=same_period_last_year and comparison_detail.mode=same_period_last_year.
- Explicit "vs previous period/previous month/previous week" => comparison=previous_period and comparison_detail.mode=previous_period.
- Explicit custom comparison dates => comparison=none and comparison_detail.mode=custom_period with reference_period populated. This includes comparisons between two resolved calendar-position selectors such as second Sunday vs first Sunday.
- FAIR PARTIAL-PERIOD COMPARISON: align equivalent elapsed calendar positions unless the user explicitly asks for the full prior period or a rolling immediately-preceding window. Examples: Sep 1-14 vs last month => Aug 1-14; current financial YTD vs prior FY => Apr 1 through the equivalent as-of date; calendar YTD vs prior calendar year => Jan 1 through the equivalent as-of date. This is a comparison-alignment concept, not a keyword rule.
- Pre/post intervention => comparison_detail.mode=pre_post. The intervention object carries the actual windows/cohorts.


GROUPING RULES
- "store-wise", "by store", "across stores", "which stores", "stores that", and store ranking/filtering require group_by=[store].
- "channel-wise", "by channel", "across channels", "which channels", and channel ranking/filtering require group_by=[channel].
- stores=[] together with group_by=[store] means evaluate the full store population individually; it does NOT mean return only a company aggregate.
- Explicitly naming two stores for direct comparison does not itself require group_by=[store] if the execution semantics already compare the two scopes, but grouping is valid when a side-by-side store breakdown is required.
- Preserve requested order for combined grouping.

PRESENTATION
- Use auto unless the user explicitly asks for a chart/image.
- image_table is appropriate for dense store/channel breakdowns.
- text is appropriate for short answers.
- chart is appropriate for explicit trend/plot requests.

CLARIFICATION
Ask only when the missing/ambiguous information materially changes the answer and cannot be safely
resolved by explicit wording, context or standard defaults. Do not reject a valid core F&B question
merely because it is phrased differently from examples.
An unresolved explicitly named store/channel DOES materially change the answer. If it cannot be
confidently mapped to one canonical ACTIVE CLIENT VOCABULARY entry, never fabricate the entity:
leave the corresponding canonical list empty, set needs_clarification=true, and ask which valid
store/channel the user meant.

Return only the structured BusinessQuery required by the schema.
"""


def _today() -> date:
    return datetime.now(ZoneInfo(DEFAULT_TIMEZONE)).date()


def _start_of_week(d: date) -> date:
    return d - timedelta(days=d.weekday())


def _previous_month(d: date) -> tuple[date, date]:
    first = d.replace(day=1)
    end = first - timedelta(days=1)
    return end.replace(day=1), end


def _quarter_start(d: date) -> date:
    month = ((d.month - 1) // 3) * 3 + 1
    return date(d.year, month, 1)


def _resolve_time(query: dict) -> dict:
    resolved = deepcopy(query)
    time_value = resolved["time"]
    kind = time_value["type"]
    now = _today()

    start = end = None
    if kind == "today":
        start = end = now
    elif kind == "yesterday":
        start = end = now - timedelta(days=1)
    elif kind == "day_before_yesterday":
        start = end = now - timedelta(days=2)
    elif kind == "this_week":
        start, end = _start_of_week(now), now
    elif kind == "last_week":
        end = _start_of_week(now) - timedelta(days=1)
        start = end - timedelta(days=6)
    elif kind == "this_month":
        start, end = now.replace(day=1), now
    elif kind == "last_month":
        start, end = _previous_month(now)
    elif kind == "this_quarter":
        start, end = _quarter_start(now), now
    elif kind == "last_quarter":
        current_q_start = _quarter_start(now)
        end = current_q_start - timedelta(days=1)
        start = _quarter_start(end)
    elif kind == "ytd":
        # Indian business/financial YTD: April 1 through today.
        # If today is Jan-Mar, the current financial year started on Apr 1 of the previous calendar year.
        fy_start_year = now.year if now.month >= 4 else now.year - 1
        start, end = date(fy_start_year, 4, 1), now
    elif kind in {"specific_date", "date_range"}:
        return resolved
    elif kind == "unspecified":
        return resolved

    if start is not None and end is not None:
        time_value["start_date"] = start.isoformat()
        time_value["end_date"] = end.isoformat()
    return resolved




def _resolve_comparison(query: dict) -> dict:
    """Resolve fair reference dates after semantic comparison intent is chosen."""
    resolved = deepcopy(query)
    detail = resolved.get("comparison_detail") or {}
    mode = detail.get("mode")
    if mode not in {"same_period_last_year", "previous_period"}:
        return resolved

    time_value = resolved.get("time") or {}
    start_text = time_value.get("start_date")
    end_text = time_value.get("end_date")
    if not start_text or not end_text:
        return resolved

    try:
        start = date.fromisoformat(start_text)
        end = date.fromisoformat(end_text)
    except (TypeError, ValueError):
        return resolved

    kind = time_value.get("type")
    ref_start = ref_end = None

    if mode == "same_period_last_year":
        try:
            ref_start = start.replace(year=start.year - 1)
        except ValueError:
            ref_start = start.replace(year=start.year - 1, day=28)
        try:
            ref_end = end.replace(year=end.year - 1)
        except ValueError:
            ref_end = end.replace(year=end.year - 1, day=28)

    elif mode == "previous_period":
        if kind == "this_month":
            prev_start, prev_full_end = _previous_month(start)
            elapsed_days = (end - start).days
            ref_start = prev_start
            ref_end = min(prev_start + timedelta(days=elapsed_days), prev_full_end)
        elif kind == "this_week":
            ref_start = start - timedelta(days=7)
            ref_end = end - timedelta(days=7)
        elif kind == "this_quarter":
            previous_q_end = start - timedelta(days=1)
            previous_q_start = _quarter_start(previous_q_end)
            elapsed_days = (end - start).days
            ref_start = previous_q_start
            ref_end = min(previous_q_start + timedelta(days=elapsed_days), previous_q_end)
        else:
            span = (end - start).days + 1
            ref_end = start - timedelta(days=1)
            ref_start = ref_end - timedelta(days=span - 1)

    if ref_start is not None and ref_end is not None:
        detail["reference_period"] = {
            "start_date": ref_start.isoformat(),
            "end_date": ref_end.isoformat(),
        }
        resolved["comparison_detail"] = detail

    return resolved


def _resolve_intervention(query: dict) -> dict:
    resolved = deepcopy(query)
    intervention = resolved.get("intervention", {})
    if not isinstance(intervention, dict) or not intervention.get("enabled"):
        return resolved

    date_text = intervention.get("intervention_date")
    before = intervention.get("window_days_before")
    after = intervention.get("window_days_after")
    if not date_text or not isinstance(before, int) or not isinstance(after, int):
        return resolved

    try:
        boundary = date.fromisoformat(date_text)
    except ValueError:
        return resolved

    # Convention: intervention date is Day 1 of post period.
    pre_end = boundary - timedelta(days=1)
    pre_start = pre_end - timedelta(days=before - 1)
    post_start = boundary
    post_end = post_start + timedelta(days=after - 1)

    intervention["pre_period"] = {
        "start_date": pre_start.isoformat(),
        "end_date": pre_end.isoformat(),
    }
    intervention["post_period"] = {
        "start_date": post_start.isoformat(),
        "end_date": post_end.isoformat(),
    }
    return resolved


def parse_business_query(user_message: str, previous_query: dict | None = None) -> dict:
    message = " ".join(str(user_message).strip().split())
    if not message:
        raise ValueError("The user message is empty.")

    instructions = _instructions(_client_context(), previous_query)

    models = [
        __import__("os").getenv("RESTAURANTAI_PLANNER_MODEL", "gpt-5.4-mini"),
        "gpt-5-mini",
    ]
    last_error = None
    response = None
    for model in dict.fromkeys(models):
        try:
            response = llm_service.client.responses.create(
                model=model,
                instructions=instructions,
                input=message,
                reasoning={"effort": "medium"},
                text={
                    "format": {
                        "type": "json_schema",
                        "name": "restaurantai_business_query_v31",
                        "description": "RestaurantAI V2 BusinessQuery v3.1 structured analytical request.",
                        "schema": BUSINESS_QUERY_JSON_SCHEMA,
                        "strict": True,
                    }
                },
            )
            break
        except Exception as error:
            last_error = error
            response = None

    if response is None:
        raise RuntimeError("Business query planner failed.") from last_error

    query = json.loads(response.output_text.strip())

    # Product rule: a valid business question with no stated/inherited time defaults to MTD.
    # Keep this deterministic so the planner cannot drift between MTD/YTD/unspecified.
    if query.get("domain_status") == "business_query":
        time_value = query.get("time") or {}
        if time_value.get("type") == "unspecified":
            time_value["type"] = "this_month"
            time_value["start_date"] = None
            time_value["end_date"] = None
            query["time"] = time_value

    query = _resolve_time(query)
    query = _resolve_comparison(query)
    return _resolve_intervention(query)
