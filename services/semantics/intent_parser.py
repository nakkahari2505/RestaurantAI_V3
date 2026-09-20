import json
import re
from datetime import datetime, timedelta
from typing import Literal, TypedDict
from zoneinfo import ZoneInfo

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
from services.core.data_loader import (
    load_auberry_workbook,
)
from services.core.llm_service import llm_service
from services.semantics.ral_schema import (
    RAL_JSON_SCHEMA,
    create_empty_ral_request,
    validate_ral_request,
)
from services.semantics.vocabulary.metrics import (
    METRIC_SALES,
    build_metric_vocabulary_prompt,
)
from services.semantics.vocabulary.time import (
    TIME_YESTERDAY,
    build_time_vocabulary_prompt,
    resolve_ral_time,
)


class IntentResult(TypedDict):
    """
    Temporary backward-compatible result expected by
    the current message_router.py.

    Internally, RestaurantAI now uses complete RAL.
    """

    capability: Literal[
        "yesterday_sales",
        "unsupported",
    ]

    understood_request: str


METRIC_VOCABULARY_PROMPT = (
    build_metric_vocabulary_prompt()
)

TIME_VOCABULARY_PROMPT = (
    build_time_vocabulary_prompt()
)


def _expand_supported_time_phrases(
    user_message: str,
) -> str:
    """
    Resolve a small set of common rolling-year phrases before GPT.

    This prevents a clearly understandable request such as
    "last one year, month wise" from becoming an unnecessary
    clarification loop.

    The period is the latest 365 completed calendar days in IST,
    ending yesterday.
    """
    text = str(user_message)

    rolling_year_pattern = re.compile(
        r"\b("
        r"last\s+(?:one|1)\s+year|"
        r"past\s+(?:one|1)\s+year|"
        r"last\s+12\s+months|"
        r"past\s+12\s+months|"
        r"previous\s+12\s+months"
        r")\b",
        re.IGNORECASE,
    )

    if not rolling_year_pattern.search(text):
        return text

    today_ist = datetime.now(
        ZoneInfo("Asia/Kolkata")
    ).date()

    end_date = (
        today_ist
        - timedelta(days=1)
    )

    start_date = (
        end_date
        - timedelta(days=364)
    )

    explicit_period = (
        f"from {start_date.strftime('%d %b %Y')} "
        f"to {end_date.strftime('%d %b %Y')}"
    )

    return rolling_year_pattern.sub(
        explicit_period,
        text,
    )


def _clean_message(
    user_message: str,
) -> str:
    """
    Normalize unnecessary spaces without changing
    the user's language or intended meaning.
    """
    return " ".join(
        str(user_message).strip().split()
    )


def _build_client_business_context() -> str:
    """
    Build the active client's business vocabulary from
    the client's own workbook.

    Current client-driven dimensions:

    - Stores
    - Channels
    - Aggregators
    - Categories
    - Items

    This context contains names and hierarchy only.

    It does not expose:

    - sales values,
    - quantities,
    - transaction values,
    - formulas,
    - analytics calculations.
    """
    data = load_auberry_workbook()

    store_dictionary = (
        build_store_dictionary(
            data=data
        )
    )

    channel_dictionary = (
        build_channel_dictionary(
            data=data
        )
    )

    product_dictionary = (
        build_product_dictionary(
            data=data
        )
    )

    store_context = (
        build_store_vocabulary_prompt(
            store_dictionary
        )
    )

    channel_context = (
        build_channel_vocabulary_prompt(
            channel_dictionary
        )
    )

    product_context = (
        build_product_vocabulary_prompt(
            product_dictionary
        )
    )

    return (
        f"{store_context}\n\n"
        f"{channel_context}\n\n"
        f"{product_context}"
    )


def _build_ral_instructions(
    client_business_context: str,
) -> str:
    """
    Build the complete RestaurantAI Language instructions.

    Universal business vocabulary is combined with the
    active client's dynamically built vocabulary.

    RAL 2.0 additionally teaches grouping, trend/time grain,
    and presentation intent. GPT understands structure only;
    Python remains responsible for deterministic execution.
    """
    return f"""
You are the language-understanding layer of RestaurantAI.

Your only responsibility is to translate a user's natural-
language restaurant business question into RestaurantAI
Language, called RAL.

RAL version is 2.0.

You must never:

- calculate sales,
- calculate quantities,
- calculate transactions or KPIs,
- read or interpret business numbers,
- answer the business question,
- invent business results,
- silently remove requested filters,
- silently remove requested grouping,
- silently remove requested trend instructions,
- invent stores,
- invent regions,
- invent channels,
- invent aggregators,
- invent categories,
- invent items.

The deterministic Python business engine will calculate all
business numbers later.

=========================================================
SUPPORTED BUSINESS METRICS
=========================================================

{METRIC_VOCABULARY_PROMPT}

Canonical metric rules:

- sales means monetary sales value, revenue, turnover,
  business value or collections.
- quantity means the number of individual units or items sold.
- transactions means the number of bills, invoices, receipts or orders.
- ads means Average Daily Sales.
- adt means Average Daily Transactions.
- apt means Average Per Transaction, Average Bill Value,
  Average Transaction Value, Average Ticket Size, AOV or ATV.

Always return exactly one canonical metric from the supported metric list.

Examples:

"What were yesterday's sales?" -> metric = "sales"
"How many bills were made yesterday?" -> metric = "transactions"
"How many donuts were sold yesterday?" -> metric = "quantity"
"What was our average bill value yesterday?" -> metric = "apt"
"What was ADS last month?" -> metric = "ads"
"What was average daily bill count?" -> metric = "adt"

=========================================================
SUPPORTED BUSINESS TIME TYPES
=========================================================

{TIME_VOCABULARY_PROMPT}

Canonical time rules:

1. Relative time expressions

For relative expressions, identify the correct canonical time type.
Do not calculate the actual dates. Python will resolve them later.

Examples:

"yesterday" -> time.type = "yesterday", dates null
"last week" -> time.type = "last_week", dates null
"this month" -> time.type = "this_month", dates null
"last quarter" -> time.type = "last_quarter", dates null

2. One explicit complete date

When the user clearly provides one complete calendar date, use
time.type = "specific_date" and normalize to YYYY-MM-DD.
Set start_date and end_date to the same date.

3. Explicit complete date range

When the user clearly provides both a complete start date and complete
end date, use time.type = "date_range" and normalize both dates.

4. Incomplete dates

Never invent a missing day, month or year. If the intended calendar
information is unclear, use time.type = "custom", keep dates null,
and ask one clarification question.

5. Complex business periods

Expressions such as last Sunday, this weekend, last weekend, same
weekend last month, last 7 days, rolling 30 days, first half of July,
breakfast, lunch, dinner or current shift must currently use
time.type = "custom". Preserve the full meaning in understood_request.

6. Missing time

If the user does not provide a usable time period:
time.type = "unspecified", start_date = null, end_date = null.

=========================================================
ACTIVE CLIENT BUSINESS VOCABULARY
=========================================================

{client_business_context}

=========================================================
STORE RULES
=========================================================

1. When the user mentions a valid store or known alias, return only
its canonical store name in stores.
2. Preserve multiple requested stores.
3. Never invent a store.
4. Never remove a store merely to make the request executable.
5. If store wording cannot be resolved confidently, preserve the
wording, set intent = "unsupported", set needs_clarification = true,
and ask one short clarification question.

=========================================================
RESTAURANT CHANNEL AND AGGREGATOR RULES
=========================================================

The parent restaurant channels are Delivery, Dine In, Take Away and Others.
Swiggy and Zomato are aggregators within Delivery.

General Delivery request -> channels = ["Delivery"], aggregators = []
Specific Swiggy request -> channels = ["Delivery"], aggregators = ["Swiggy"]
Specific Zomato request -> channels = ["Delivery"], aggregators = ["Zomato"]
Multiple aggregators must all be preserved.

Aggregator-wise request means a breakdown by aggregator:
channels = ["Delivery"]
aggregators = []
grouping.enabled = true
grouping.dimensions = ["aggregator"]
Never select only one aggregator for an aggregator-wise request.

Take Away expressions such as takeaway, take-away, pickup, pick-up or parcel
map to channels = ["Take Away"].
Dine In expressions such as dine-in, dining, walk-in map to
channels = ["Dine In"].
Never return Swiggy or Zomato as parent channels.

=========================================================
CATEGORY AND ITEM RULES
=========================================================

The active client product vocabulary contains Category -> Item.
Categories and items are different RAL dimensions.

Whole-category request:
"How many Donuts were sold last month?"
metric = "quantity"
categories = ["Donuts"]
items = []

Specific-item request:
Populate the canonical item name and, when known, its canonical category.

Multiple categories/items must all be preserved.
Never return a category inside items or an item as a category.
Never invent an item or category.
Never guess the category of an unmapped item.
Ordinary singular/plural wording may refer to the same canonical concept.
If wording could refer to multiple specific items and no single item is
clearly intended, do not arbitrarily choose one; ask for clarification.

=========================================================
GROUPING RULES
=========================================================

Grouping means the user wants the result split by one or more business
dimensions. Supported grouping dimensions are exactly:
store, channel, aggregator, category, item.

No grouping:
grouping.enabled = false
grouping.dimensions = []

Examples:
"Store-wise sales last month" -> ["store"]
"Category-wise quantity yesterday" -> ["category"]
"Aggregator-wise transactions last month" -> ["aggregator"]
"Item-wise sales at Nexus Mall this month" -> ["item"]

For multiple grouping dimensions preserve the requested order.
Example:
"Store-wise channel-wise sales last month"
-> grouping.dimensions = ["store", "channel"]

FILTER VERSUS GROUPING IS CRITICAL:
A filter restricts scope. Grouping splits the result.

"Category-wise sales at AMB last month"
stores = ["AMB Mall"]
categories = []
grouping = category

"Store-wise sales of Donuts last month"
categories = ["Donuts"]
stores = []
grouping = store

Words such as wise, by, breakdown, split, separately, each, across stores,
across channels, across categories and platform-wise may imply grouping.
Interpret meaning, not only exact words.

=========================================================
TREND RULES
=========================================================

Trend means the user wants the metric shown over ordered time buckets.
Supported grains are exactly: day, week, month.

No trend:
trend.enabled = false
trend.grain = null

Daily/day-wise/by day -> trend.enabled = true, grain = "day"
Weekly/week-wise/by week -> grain = "week"
Monthly/month-wise/by month -> grain = "month"

Trend and business grouping may coexist.
Example:
"Daily store-wise sales trend this month"
grouping = ["store"]
trend.grain = "day"

Example:
"Monthly category-wise sales trend"
grouping = ["category"]
trend.grain = "month"

A time grain is NOT a grouping dimension. Never put day, week or month
inside grouping.dimensions. Use trend.grain instead.

=========================================================
PRESENTATION RULES
=========================================================

Presentation describes how the user wants the result shown.
Supported types are exactly: text, table, bar_chart, line_chart.

If no explicit output format is requested -> presentation.type = "text"
"show as a table" -> "table"
"bar chart" or "bar graph" -> "bar_chart"
"line chart" or "line graph" -> "line_chart"

If the user asks to plot/graph/chart a clear daily, weekly or monthly
trend without specifying chart type, prefer line_chart.
Do not invent a chart for an ordinary grouped request.

=========================================================
CURRENT EXECUTION STATUS
=========================================================

RestaurantAI already has deterministic execution for single-result
questions using combinations of supported metric, resolved time, stores,
channels, aggregators, categories and items.

Ordinary analytical requests should use intent = "sales" even when the
metric is quantity, transactions, ADS, ADT or APT.

Grouping and trend are now understood by RAL 2.0. Preserve them completely.
Never convert a grouped or trend request into a single-result request.

Comparison requests use intent = "compare".
Unsupported or unrelated requests use intent = "unsupported".

=========================================================
COMPARISON RULES
=========================================================

When the user clearly asks to compare two periods:
comparison.enabled = true
intent = "compare"

Use comparison date fields only when two complete explicit date periods
are clearly provided. Never invent comparison dates.

=========================================================
SAFETY RULES
=========================================================

1. Understand meaning rather than matching exact words.
2. Be tolerant of ordinary spelling mistakes.
3. Never change the requested metric merely to fit an available engine.
4. Never remove requested filters.
5. Never remove grouping dimensions.
6. Never remove trend instructions.
7. Quantity requests must use metric = "quantity".
8. Bills/transactions/invoices/receipts/orders use metric = "transactions".
9. "How did we perform yesterday?" defaults to metric = "sales".
10. Never invent missing calendar information.
11. Swiggy and Zomato are never parent channels.
12. Specific aggregator requests always include channels = ["Delivery"].
13. Whole-category requests leave items empty.
14. Specific-item requests populate items and should populate category when known.
15. Never guess the category of an unmapped item.
16. No grouping -> enabled false and dimensions empty.
17. No trend -> enabled false and grain null.
18. No explicit presentation -> type = "text".
19. Clarification required -> needs_clarification true and one short question.
20. No clarification -> needs_clarification false and question null.
21. Unclear/unrelated -> intent unsupported and time unspecified.
22. understood_request must describe the COMPLETE request, including grouping,
trend and presentation when present.
23. Return only the structured RAL object required by the schema.
"""

def parse_ral_request(
    user_message: str,
) -> dict:
    """
    Translate human language into a complete, date-resolved
    RAL request.

    Flow:

        Human message
            ↓
        Dynamic client vocabulary
            ↓
        GPT proposes RAL
            ↓
        Python validates RAL structure
            ↓
        Python resolves relative time into dates
            ↓
        Python validates the final RAL again
            ↓
        Complete structured request
    """
    cleaned_message = _clean_message(
        _expand_supported_time_phrases(
            user_message
        )
    )

    if not cleaned_message:
        empty_request = (
            create_empty_ral_request()
        )

        empty_request[
            "understood_request"
        ] = "The message was empty."

        validate_ral_request(
            empty_request
        )

        return empty_request

    client_business_context = (
        _build_client_business_context()
    )

    ral_instructions = (
        _build_ral_instructions(
            client_business_context=(
                client_business_context
            )
        )
    )

    response = (
        llm_service.client.responses.create(
            model="gpt-5-mini",
            instructions=ral_instructions,
            input=cleaned_message,
            reasoning={
                "effort": "minimal",
            },
            text={
                "format": {
                    "type": "json_schema",
                    "name": (
                        "restaurantai_ral_request"
                    ),
                    "description": (
                        "A structured RestaurantAI "
                        "Language request."
                    ),
                    "schema": RAL_JSON_SCHEMA,
                    "strict": True,
                }
            },
        )
    )

    response_text = (
        response.output_text.strip()
    )

    try:
        proposed_ral_request = json.loads(
            response_text
        )

    except json.JSONDecodeError as error:
        raise ValueError(
            "The LLM returned invalid RAL JSON."
        ) from error

    # First guardrail:
    # validate exactly what GPT proposed.
    validate_ral_request(
        proposed_ral_request
    )

    # Resolve relative business time deterministically.
    resolved_ral_request = (
        resolve_ral_time(
            proposed_ral_request
        )
    )

    # Second guardrail:
    # validate the final date-resolved request.
    validate_ral_request(
        resolved_ral_request
    )

    return resolved_ral_request


def _ral_can_run_yesterday_sales(
    ral_request: dict,
) -> bool:
    """
    Decide deterministically whether the RAL request can
    safely use the existing overall Yesterday Sales engine.

    Only this exact request can execute:

    - sales metric,
    - yesterday,
    - one deterministically resolved date,
    - all stores,
    - all regions,
    - all channels,
    - all aggregators,
    - all categories,
    - all items,
    - no comparison,
    - no clarification.
    """
    if (
        ral_request["intent"]
        != "sales"
    ):
        return False

    if (
        ral_request["metric"]
        != METRIC_SALES
    ):
        return False

    if (
        ral_request["time"]["type"]
        != TIME_YESTERDAY
    ):
        return False

    start_date = ral_request[
        "time"
    ]["start_date"]

    end_date = ral_request[
        "time"
    ]["end_date"]

    if not isinstance(
        start_date,
        str,
    ):
        return False

    if not isinstance(
        end_date,
        str,
    ):
        return False

    if start_date != end_date:
        return False

    if ral_request["stores"]:
        return False

    if ral_request["regions"]:
        return False

    if ral_request["channels"]:
        return False

    if ral_request["aggregators"]:
        return False

    if ral_request["categories"]:
        return False

    if ral_request["items"]:
        return False

    if (
        ral_request["grouping"][
            "enabled"
        ]
    ):
        return False

    if (
        ral_request["trend"][
            "enabled"
        ]
    ):
        return False

    if (
        ral_request["presentation"][
            "type"
        ]
        != "text"
    ):
        return False

    if (
        ral_request["comparison"][
            "enabled"
        ]
    ):
        return False

    if ral_request[
        "needs_clarification"
    ]:
        return False

    return True


def parse_intent(
    user_message: str,
) -> IntentResult:
    """
    Backward-compatible adapter used by message_router.py.

    Internally:

        human language
            ↓
        complete date-resolved RAL
            ↓
        deterministic execution guardrail
            ↓
        old capability result

    Only unfiltered overall yesterday sales can currently
    reach the existing business engine through GPT.
    """
    ral_request = parse_ral_request(
        user_message=user_message
    )

    if _ral_can_run_yesterday_sales(
        ral_request
    ):
        capability = "yesterday_sales"

    else:
        capability = "unsupported"

    return {
        "capability": capability,
        "understood_request": (
            ral_request[
                "understood_request"
            ]
        ),
    }