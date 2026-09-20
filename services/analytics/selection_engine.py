from __future__ import annotations

from copy import deepcopy
from datetime import date, datetime, timedelta
import re
from typing import Any, Final
from zoneinfo import ZoneInfo

from services.analytics.grouping_engine import (
    calculate_grouped_metric,
)
from services.analytics.trend_engine import (
    calculate_trend,
)


# =========================================================
# PURPOSE
# =========================================================
#
# Selection Engine answers ONE "which / what / when" extreme
# question after RestaurantAI has already understood filters.
#
# Examples:
#   Which store had the highest Delivery sales?
#   Which store sold the most Water Bottles last month?
#   On which date were sales highest this year?
#   Which product had the highest sales?
#   Which product was highest by Qty and by Sales?
#
# It deliberately reuses the existing deterministic:
#   Filter Engine
#   Grouping Engine
#   Trend Engine
#   Metric Engine
#
# It does NOT create a second analytics stack.
# =========================================================


IST: Final[ZoneInfo] = ZoneInfo(
    "Asia/Kolkata"
)

SUPPORTED_SELECTION_DIMENSIONS: Final[set[str]] = {
    "store",
    "channel",
    "aggregator",
    "category",
    "item",
    "date",
}

SUPPORTED_SELECTION_METRICS: Final[set[str]] = {
    "sales",
    "quantity",
    "transactions",
    "ads",
    "adt",
    "apt",
}


# =========================================================
# DETECTION
# =========================================================


EXTREME_MAX_PATTERNS: Final[tuple[str, ...]] = (
    r"\bhighest\b",
    r"\bmaximum\b",
    r"\bmax\b",
    r"\bmost\b",
    r"\btop\b",
    r"\bbest[\s-]*selling\b",
    r"\btop[\s-]*selling\b",
    r"\blargest\b",
)

EXTREME_MIN_PATTERNS: Final[tuple[str, ...]] = (
    r"\blowest\b",
    r"\bminimum\b",
    r"\bmin\b",
    r"\bleast\b",
    r"\bbottom\b",
    r"\bsmallest\b",
)


def _normalized_message(
    user_message: str,
) -> str:
    return " ".join(
        str(user_message)
        .strip()
        .lower()
        .split()
    )


def _matches_any(
    text: str,
    patterns: tuple[str, ...],
) -> bool:
    return any(
        re.search(
            pattern,
            text,
            flags=re.IGNORECASE,
        )
        for pattern in patterns
    )


NUMBER_WORDS: Final[dict[str, int]] = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
    "seven": 7,
    "eight": 8,
    "nine": 9,
    "ten": 10,
    "eleven": 11,
    "twelve": 12,
    "thirteen": 13,
    "fourteen": 14,
    "fifteen": 15,
    "sixteen": 16,
    "seventeen": 17,
    "eighteen": 18,
    "nineteen": 19,
    "twenty": 20,
}


def _parse_count_token(
    token: str,
) -> int | None:
    cleaned = str(token).strip().lower()

    if cleaned.isdigit():
        return max(
            1,
            int(cleaned),
        )

    return NUMBER_WORDS.get(
        cleaned
    )


def _detect_selection_count(
    text: str,
) -> int:
    """
    Detect requested Top/Bottom N from natural business
    language.

    Supported examples:

        top 3 stores
        bottom 5 items
        highest 10 stores
        lowest 4 products
        3 stores with lowest APT
        three stores with lowest ADT

    If no explicit count is present, default to 1 so all
    existing Highest/Lowest questions remain unchanged.
    """
    number_token = (
        r"(\d+|one|two|three|four|five|six|seven|eight|nine|ten|"
        r"eleven|twelve|thirteen|fourteen|fifteen|sixteen|"
        r"seventeen|eighteen|nineteen|twenty)"
    )

    # Direction followed by count:
    # top 3, bottom three, highest 5, lowest 4.
    direction_first_pattern = (
        rf"\b(?:top|bottom|highest|lowest|maximum|minimum)\s+"
        rf"{number_token}\b"
    )

    match = re.search(
        direction_first_pattern,
        text,
        flags=re.IGNORECASE,
    )

    if match:
        parsed = _parse_count_token(
            match.group(1)
        )

        if parsed is not None:
            return parsed

    # Count followed by a supported entity:
    # 3 stores with lowest APT
    # three products by highest sales
    entity_pattern = (
        rf"\b{number_token}\s+"
        r"(?:stores?|outlets?|locations?|products?|items?|skus?|"
        r"categories?|channels?|aggregators?|dates?|days?)\b"
    )

    match = re.search(
        entity_pattern,
        text,
        flags=re.IGNORECASE,
    )

    if match:
        parsed = _parse_count_token(
            match.group(1)
        )

        if parsed is not None:
            return parsed

    return 1



def _detect_direction(
    text: str,
) -> str | None:
    if _matches_any(
        text,
        EXTREME_MIN_PATTERNS,
    ):
        return "min"

    if _matches_any(
        text,
        EXTREME_MAX_PATTERNS,
    ):
        return "max"

    return None


def _detect_dimension(
    text: str,
) -> str | None:
    """
    Deterministically identify the entity/date that must be
    ranked.

    Singular and plural business language are both accepted.
    """
    # Date/when must be checked first.
    if (
        re.search(
            r"\bwhen\b",
            text,
        )
        or re.search(
            r"\bwhich\s+(?:date|day)\b",
            text,
        )
        or re.search(
            r"\bon\s+which\s+(?:date|day)\b",
            text,
        )
        or re.search(
            r"\b(?:dates|days)\b",
            text,
        )
    ):
        return "date"

    if re.search(
        r"\b(?:store|stores|outlet|outlets|location|locations)\b",
        text,
    ):
        return "store"

    if re.search(
        r"\b(?:aggregator|aggregators|platform|platforms)\b",
        text,
    ):
        return "aggregator"

    if re.search(
        r"\b(?:channel|channels)\b",
        text,
    ):
        return "channel"

    if re.search(
        r"\b(?:category|categories)\b",
        text,
    ):
        return "category"

    if re.search(
        r"\b(?:product|products|item|items|sku|skus)\b",
        text,
    ):
        return "item"

    return None



def _detect_metrics(
    text: str,
    fallback_metric: str,
) -> list[str]:
    """
    Unlike ordinary RAL, one selection question may ask for
    more than one winner, e.g. "by Qty and by Sales".

    We keep the existing top-level RAL metric untouched and
    only expand metrics inside this Selection Engine.
    """
    metrics: list[str] = []

    def add_metric(metric_name: str) -> None:
        if metric_name not in metrics:
            metrics.append(metric_name)

    if re.search(
        r"\b(?:qty|quantity|units?|pieces?)\b",
        text,
    ):
        add_metric("quantity")

    if re.search(
        r"\b(?:sales?|revenue|turnover|value)\b",
        text,
    ):
        add_metric("sales")

    if re.search(
        r"\b(?:transactions?|txns?|bills?|orders?|invoices?|receipts?)\b",
        text,
    ):
        add_metric("transactions")

    if re.search(
        r"\bads\b|average\s+daily\s+sales",
        text,
    ):
        add_metric("ads")

    if re.search(
        r"\badt\b|average\s+daily\s+(?:transactions?|bills?)",
        text,
    ):
        add_metric("adt")

    if re.search(
        r"\bapt\b|average\s+(?:bill|ticket|transaction)|\baov\b|\batv\b",
        text,
    ):
        add_metric("apt")

    normalized_fallback = (
        str(fallback_metric)
        .strip()
        .lower()
    )

    if (
        not metrics
        and normalized_fallback
        in SUPPORTED_SELECTION_METRICS
    ):
        metrics.append(
            normalized_fallback
        )

    if not metrics:
        metrics.append(
            "sales"
        )

    return metrics


def detect_selection_plan(
    user_message: str,
    ral_request: dict,
) -> dict | None:
    """
    Return a deterministic selection plan or None when this
    is not a top-one/bottom-one question.
    """
    text = _normalized_message(
        user_message
    )

    selection_count = _detect_selection_count(
        text
    )

    direction = _detect_direction(
        text
    )

    if direction is None:
        return None

    dimension = _detect_dimension(
        text
    )

    if dimension is None:
        return None

    metrics = _detect_metrics(
        text=text,
        fallback_metric=ral_request.get(
            "metric",
            "sales",
        ),
    )

    return {
        "enabled": True,
        "direction": direction,
        "dimension": dimension,
        "metrics": metrics,
        "selection_count": selection_count,
    }


# =========================================================
# TIME HANDLING
# =========================================================


def _iso(
    value: date,
) -> str:
    return value.isoformat()


def _last_month_range(
    today: date,
) -> tuple[date, date]:
    first_this_month = today.replace(
        day=1
    )

    last_previous_month = (
        first_this_month
        - timedelta(days=1)
    )

    first_previous_month = (
        last_previous_month.replace(
            day=1
        )
    )

    return (
        first_previous_month,
        last_previous_month,
    )


def _this_year_range(
    today: date,
) -> tuple[date, date]:
    return (
        date(
            today.year,
            1,
            1,
        ),
        today,
    )


def _last_year_range(
    today: date,
) -> tuple[date, date]:
    year = today.year - 1

    return (
        date(
            year,
            1,
            1,
        ),
        date(
            year,
            12,
            31,
        ),
    )


def prepare_selection_ral(
    user_message: str,
    ral_request: dict,
) -> tuple[dict, dict]:
    """
    Prepare a copy of ordinary RAL for Selection execution.

    Critical user rule:
        If a Selection question contains no usable time,
        default to LAST MONTH and explicitly mark that fact so
        the formatter can say the period was assumed.

    Selection also recognizes "this year" / "last year" even
    if the current generic RAL time vocabulary has not yet
    promoted those phrases to first-class relative types.
    """
    prepared = deepcopy(
        ral_request
    )

    text = _normalized_message(
        user_message
    )

    today = datetime.now(
        IST
    ).date()

    default_time_applied = False
    time_label: str | None = None

    # Explicit annual period support for this capability.
    if re.search(
        r"\bthis\s+year\b|\bcurrent\s+year\b",
        text,
    ):
        start_date, end_date = (
            _this_year_range(
                today
            )
        )

        prepared["time"] = {
            "type": "date_range",
            "start_date": _iso(
                start_date
            ),
            "end_date": _iso(
                end_date
            ),
        }

        time_label = "This year"

        # The generic RAL parser may have called this period
        # custom. It is deterministic here, so no clarification
        # is required for time.
        prepared[
            "needs_clarification"
        ] = False
        prepared[
            "clarification_question"
        ] = None

    elif re.search(
        r"\blast\s+year\b|\bprevious\s+year\b",
        text,
    ):
        start_date, end_date = (
            _last_year_range(
                today
            )
        )

        prepared["time"] = {
            "type": "date_range",
            "start_date": _iso(
                start_date
            ),
            "end_date": _iso(
                end_date
            ),
        }

        time_label = "Last year"
        prepared[
            "needs_clarification"
        ] = False
        prepared[
            "clarification_question"
        ] = None

    else:
        time_value = prepared.get(
            "time",
            {},
        )

        time_type = (
            str(
                time_value.get(
                    "type",
                    "unspecified",
                )
            )
            .strip()
            .lower()
            if isinstance(
                time_value,
                dict,
            )
            else "unspecified"
        )

        start_date = (
            time_value.get(
                "start_date"
            )
            if isinstance(
                time_value,
                dict,
            )
            else None
        )

        end_date = (
            time_value.get(
                "end_date"
            )
            if isinstance(
                time_value,
                dict,
            )
            else None
        )

        if (
            time_type == "unspecified"
            or not start_date
            or not end_date
        ):
            # Do NOT override genuine custom-time ambiguity.
            # Only unspecified/no-time selection questions get
            # the Last Month default.
            if time_type == "unspecified":
                start, end = (
                    _last_month_range(
                        today
                    )
                )

                prepared["time"] = {
                    "type": "date_range",
                    "start_date": _iso(
                        start
                    ),
                    "end_date": _iso(
                        end
                    ),
                }

                default_time_applied = True
                time_label = "Last month"

                prepared[
                    "needs_clarification"
                ] = False
                prepared[
                    "clarification_question"
                ] = None

    meta = {
        "default_time_applied": (
            default_time_applied
        ),
        "time_label": time_label,
    }

    return (
        prepared,
        meta,
    )


# =========================================================
# EXECUTION
# =========================================================


def _numeric_value(
    row: dict,
) -> float:
    return float(
        row.get(
            "metric_value",
            0,
        )
    )


def _select_ranked_rows(
    rows: list[dict],
    direction: str,
    selection_count: int,
) -> list[dict]:
    """
    Return Top/Bottom N rows while preserving ties at the
    cutoff value.

    Example:
        values = [100, 90, 80, 80, 70]
        top 3 -> returns 100, 90, 80, 80

    This avoids arbitrarily dropping a business entity that is
    tied exactly at the requested rank.
    """
    if not rows:
        return []

    requested_count = max(
        1,
        int(selection_count),
    )

    reverse = (
        direction == "max"
    )

    sorted_rows = sorted(
        rows,
        key=_numeric_value,
        reverse=reverse,
    )

    if requested_count >= len(
        sorted_rows
    ):
        return sorted_rows

    cutoff_row = sorted_rows[
        requested_count - 1
    ]

    cutoff_value = _numeric_value(
        cutoff_row
    )

    if direction == "max":
        return [
            row
            for row in sorted_rows
            if _numeric_value(row)
            >= cutoff_value
        ]

    return [
        row
        for row in sorted_rows
        if _numeric_value(row)
        <= cutoff_value
    ]


def _business_dimension_result(
    filtered_sales,
    data: dict,
    base_ral: dict,
    metric_name: str,
    dimension: str,
    direction: str,
    selection_count: int,
) -> dict:
    execution_ral = deepcopy(
        base_ral
    )

    execution_ral[
        "metric"
    ] = metric_name

    execution_ral[
        "grouping"
    ] = {
        "enabled": True,
        "dimensions": [
            dimension,
        ],
    }

    execution_ral[
        "trend"
    ] = {
        "enabled": False,
        "grain": None,
    }

    grouped_result = (
        calculate_grouped_metric(
            filtered_sales=(
                filtered_sales
            ),
            data=data,
            ral_request=(
                execution_ral
            ),
        )
    )

    winners = _select_ranked_rows(
        rows=grouped_result.get(
            "rows",
            [],
        ),
        direction=direction,
        selection_count=(
            selection_count
        ),
    )

    return {
        "metric": metric_name,
        "dimension": dimension,
        "winners": [
            {
                "label": str(
                    row.get(
                        "groups",
                        {},
                    ).get(
                        dimension,
                        "Unspecified",
                    )
                ),
                "metric_value": (
                    row.get(
                        "metric_value",
                        0,
                    )
                ),
            }
            for row in winners
        ],
    }


def _date_dimension_result(
    filtered_sales,
    data: dict,
    base_ral: dict,
    metric_name: str,
    direction: str,
    selection_count: int,
) -> dict:
    execution_ral = deepcopy(
        base_ral
    )

    execution_ral[
        "metric"
    ] = metric_name

    execution_ral[
        "grouping"
    ] = {
        "enabled": False,
        "dimensions": [],
    }

    execution_ral[
        "trend"
    ] = {
        "enabled": True,
        "grain": "day",
    }

    trend_result = calculate_trend(
        filtered_sales=filtered_sales,
        data=data,
        ral_request=execution_ral,
    )

    winners = _select_ranked_rows(
        rows=trend_result.get(
            "rows",
            [],
        ),
        direction=direction,
        selection_count=(
            selection_count
        ),
    )

    return {
        "metric": metric_name,
        "dimension": "date",
        "winners": [
            {
                "label": str(
                    row.get(
                        "period_label",
                        row.get(
                            "period_start",
                            "Unspecified",
                        ),
                    )
                ),
                "metric_value": (
                    row.get(
                        "metric_value",
                        0,
                    )
                ),
            }
            for row in winners
        ],
    }


def execute_selection(
    filtered_sales,
    data: dict,
    ral_request: dict,
    plan: dict,
    time_meta: dict,
) -> dict:
    """
    Execute one extreme-selection question.

    Selection is a layer ABOVE grouping/trend, not a duplicate
    replacement for them.
    """
    dimension = str(
        plan.get(
            "dimension",
            "",
        )
    ).strip().lower()

    direction = str(
        plan.get(
            "direction",
            "max",
        )
    ).strip().lower()

    metrics = [
        str(metric)
        .strip()
        .lower()
        for metric in plan.get(
            "metrics",
            [],
        )
    ]

    selection_count = max(
        1,
        int(
            plan.get(
                "selection_count",
                1,
            )
        ),
    )

    if dimension not in (
        SUPPORTED_SELECTION_DIMENSIONS
    ):
        raise ValueError(
            "Unsupported selection dimension."
        )

    if direction not in {
        "max",
        "min",
    }:
        raise ValueError(
            "Unsupported selection direction."
        )

    if not metrics:
        metrics = [
            "sales",
        ]

    invalid_metrics = [
        metric
        for metric in metrics
        if metric
        not in SUPPORTED_SELECTION_METRICS
    ]

    if invalid_metrics:
        raise ValueError(
            "Unsupported selection metrics: "
            + ", ".join(
                invalid_metrics
            )
        )

    results = []

    for metric_name in metrics:
        if dimension == "date":
            metric_result = (
                _date_dimension_result(
                    filtered_sales=(
                        filtered_sales
                    ),
                    data=data,
                    base_ral=ral_request,
                    metric_name=metric_name,
                    direction=direction,
                    selection_count=(
                        selection_count
                    ),
                )
            )
        else:
            metric_result = (
                _business_dimension_result(
                    filtered_sales=(
                        filtered_sales
                    ),
                    data=data,
                    base_ral=ral_request,
                    metric_name=metric_name,
                    dimension=dimension,
                    direction=direction,
                    selection_count=(
                        selection_count
                    ),
                )
            )

        results.append(
            metric_result
        )

    return {
        "result_type": "selection",
        "direction": direction,
        "dimension": dimension,
        "selection_count": selection_count,
        "results": results,
        "time": deepcopy(
            ral_request.get(
                "time",
                {},
            )
        ),
        "default_time_applied": bool(
            time_meta.get(
                "default_time_applied",
                False,
            )
        ),
        "time_label": (
            time_meta.get(
                "time_label"
            )
        ),
        "filters": {
            "stores": deepcopy(
                ral_request.get(
                    "stores",
                    [],
                )
            ),
            "channels": deepcopy(
                ral_request.get(
                    "channels",
                    [],
                )
            ),
            "aggregators": deepcopy(
                ral_request.get(
                    "aggregators",
                    [],
                )
            ),
            "categories": deepcopy(
                ral_request.get(
                    "categories",
                    [],
                )
            ),
            "items": deepcopy(
                ral_request.get(
                    "items",
                    [],
                )
            ),
        },
    }


# =========================================================
# PRESENTATION
# =========================================================


METRIC_LABELS: Final[dict[str, str]] = {
    "sales": "Sales",
    "quantity": "Quantity",
    "transactions": "Transactions",
    "ads": "ADS",
    "adt": "ADT",
    "apt": "APT",
}

DIMENSION_LABELS: Final[dict[str, str]] = {
    "store": "Store",
    "channel": "Channel",
    "aggregator": "Aggregator",
    "category": "Category",
    "item": "Product",
    "date": "Date",
}


def _format_indian_number(
    value: float,
) -> str:
    number = int(
        round(
            float(value)
        )
    )

    sign = "-" if number < 0 else ""
    digits = str(abs(number))

    if len(digits) <= 3:
        return sign + digits

    last_three = digits[-3:]
    remaining = digits[:-3]
    groups = []

    while len(remaining) > 2:
        groups.insert(
            0,
            remaining[-2:],
        )
        remaining = remaining[:-2]

    if remaining:
        groups.insert(
            0,
            remaining,
        )

    return (
        sign
        + ",".join(
            groups
            + [
                last_three,
            ]
        )
    )


def _format_value(
    metric_name: str,
    value: float,
) -> str:
    normalized_metric = (
        str(metric_name)
        .strip()
        .lower()
    )

    if normalized_metric == "sales":
        return (
            "₹"
            + _format_indian_number(
                value
            )
        )

    if normalized_metric in {
        "apt",
    }:
        return (
            "₹"
            + _format_indian_number(
                value
            )
        )

    if normalized_metric in {
        "ads",
    }:
        return (
            "₹"
            + _format_indian_number(
                value
            )
        )

    if normalized_metric == "adt":
        numeric = float(value)
        return (
            str(int(numeric))
            if numeric.is_integer()
            else f"{numeric:.1f}"
        )

    return _format_indian_number(
        value
    )


def _display_iso_date(
    value: str,
) -> str:
    try:
        return datetime.strptime(
            value,
            "%Y-%m-%d",
        ).strftime(
            "%d %b %Y"
        )
    except Exception:
        return str(value)


def _period_line(
    selection_result: dict,
) -> str:
    time_value = selection_result.get(
        "time",
        {},
    )

    start_date = time_value.get(
        "start_date"
    )
    end_date = time_value.get(
        "end_date"
    )

    if not start_date or not end_date:
        return ""

    start_display = _display_iso_date(
        start_date
    )
    end_display = _display_iso_date(
        end_date
    )

    if start_date == end_date:
        period_display = start_display
    else:
        period_display = (
            f"{start_display} to "
            f"{end_display}"
        )

    if selection_result.get(
        "default_time_applied",
        False,
    ):
        return (
            "🗓️ *Period assumed:* Last month "
            f"({period_display})"
        )

    time_label = selection_result.get(
        "time_label"
    )

    if time_label:
        return (
            f"🗓️ *Period:* {time_label} "
            f"({period_display})"
        )

    return (
        f"🗓️ *Period:* {period_display}"
    )


def _scope_lines(
    filters: dict,
) -> list[str]:
    labels = (
        ("Store", "stores"),
        ("Channel", "channels"),
        ("Aggregator", "aggregators"),
        ("Category", "categories"),
        ("Product", "items"),
    )

    lines: list[str] = []

    for label, key in labels:
        values = filters.get(
            key,
            [],
        )

        if values:
            lines.append(
                f"• {label}: "
                + ", ".join(
                    str(value)
                    for value in values
                )
            )

    return lines


def _pluralize_dimension_label(
    dimension_label: str,
) -> str:
    irregular = {
        "Category": "Categories",
    }

    if dimension_label in irregular:
        return irregular[
            dimension_label
        ]

    if dimension_label.endswith("s"):
        return dimension_label

    return dimension_label + "s"


def format_selection_result(
    selection_result: dict,
) -> str:
    direction = selection_result.get(
        "direction",
        "max",
    )

    dimension = selection_result.get(
        "dimension",
        "item",
    )

    results = selection_result.get(
        "results",
        [],
    )

    selection_count = max(
        1,
        int(
            selection_result.get(
                "selection_count",
                1,
            )
        ),
    )

    direction_label = (
        "Highest"
        if direction == "max"
        else "Lowest"
    )

    dimension_label = DIMENSION_LABELS.get(
        dimension,
        str(dimension).title(),
    )

    if selection_count == 1:
        heading = (
            f"🏆 *{direction_label} {dimension_label}*"
        )
    else:
        list_direction = (
            "Top"
            if direction == "max"
            else "Bottom"
        )

        heading = (
            f"🏆 *{list_direction} {selection_count} "
            f"{_pluralize_dimension_label(dimension_label)}*"
        )

    lines = [
        heading,
    ]

    period_line = _period_line(
        selection_result
    )

    if period_line:
        lines.extend(
            [
                "",
                period_line,
            ]
        )

    scope = _scope_lines(
        selection_result.get(
            "filters",
            {},
        )
    )

    if scope:
        lines.extend(
            [
                "",
                "*Scope:*",
                *scope,
            ]
        )

    lines.append("")

    for metric_result in results:
        metric_name = metric_result.get(
            "metric",
            "sales",
        )

        metric_label = METRIC_LABELS.get(
            metric_name,
            str(metric_name).title(),
        )

        winners = metric_result.get(
            "winners",
            [],
        )

        if not winners:
            lines.append(
                f"*By {metric_label}:* No result"
            )
            continue

        if len(results) > 1:
            prefix = f"*By {metric_label}:* "
        else:
            prefix = ""

        winner_parts = [
            (
                f"{winner.get('label', 'Unspecified')} — "
                f"*{_format_value(metric_name, winner.get('metric_value', 0))}*"
            )
            for winner in winners
        ]

        if selection_count == 1:
            if len(winner_parts) == 1:
                lines.append(
                    prefix
                    + winner_parts[0]
                )
            else:
                lines.append(
                    prefix
                    + "Tie"
                )

                for winner_part in winner_parts:
                    lines.append(
                        f"• {winner_part}"
                    )

            continue

        if len(results) > 1:
            lines.append(
                f"*By {metric_label}:*"
            )

        # Rank by distinct metric value so cutoff ties share
        # the same rank number.
        rank = 0
        previous_value = None

        for index, winner in enumerate(
            winners,
            start=1,
        ):
            current_value = float(
                winner.get(
                    "metric_value",
                    0,
                )
            )

            if (
                previous_value is None
                or current_value != previous_value
            ):
                rank = index
                previous_value = current_value

            lines.append(
                f"{rank}. "
                f"{winner.get('label', 'Unspecified')} — "
                f"*{_format_value(metric_name, current_value)}*"
            )

        if len(results) > 1:
            lines.append("")

    return "\n".join(
        lines
    )
