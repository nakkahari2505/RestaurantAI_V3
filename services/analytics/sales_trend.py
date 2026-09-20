from __future__ import annotations

import re
from datetime import datetime
from difflib import SequenceMatcher
from zoneinfo import ZoneInfo

import pandas as pd

from services.semantics.builders.store_builder import (
    build_store_dictionary,
)
from services.semantics.vocabulary.metrics import (
    calculate_metric,
)


IST = ZoneInfo("Asia/Kolkata")

DATE_COLUMN = "Date"
SOURCE_STORE_COLUMN = "Restaurant"

SUPPORTED_METRICS = {
    "sales": {
        "display_name": "Sales",
        "aliases": (
            "sales",
            "sale",
            "revenue",
            "business",
        ),
    },
    "transactions": {
        "display_name": "Transactions",
        "aliases": (
            "transactions",
            "transaction",
            "txns",
            "txn",
            "bills",
            "orders",
        ),
    },
    "ads": {
        "display_name": "ADS",
        "aliases": (
            "ads",
            "average daily sales",
            "daily average sales",
        ),
    },
    "adt": {
        "display_name": "ADT",
        "aliases": (
            "adt",
            "average daily transactions",
            "daily average transactions",
        ),
    },
    "apt": {
        "display_name": "APT",
        "aliases": (
            "apt",
            "average per transaction",
            "average bill value",
            "average transaction value",
        ),
    },
}

TREND_WORDS = (
    "trend",
    "trends",
    "plot",
    "graph",
    "chart",
)

NUMBER_WORDS = {
    "one": 1,
    "two": 2,
    "three": 3,
    "four": 4,
    "five": 5,
    "six": 6,
}


def _normalize(value: object) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        " ",
        str(value).casefold(),
    ).strip()


def _ratio(a: str, b: str) -> float:
    return SequenceMatcher(
        None,
        _normalize(a),
        _normalize(b),
    ).ratio()


def _word_windows(
    text: str,
    min_size: int = 1,
    max_size: int = 4,
) -> list[str]:
    tokens = _normalize(text).split()
    windows: list[str] = []

    for size in range(
        min_size,
        max_size + 1,
    ):
        for index in range(
            len(tokens) - size + 1
        ):
            windows.append(
                " ".join(
                    tokens[
                        index:index + size
                    ]
                )
            )

    return windows


def _contains_fuzzy_term(
    message: str,
    terms: tuple[str, ...],
    threshold: float = 0.76,
) -> bool:
    normalized_message = _normalize(
        message
    )

    for term in terms:
        if re.search(
            rf"\b{re.escape(_normalize(term))}\b",
            normalized_message,
        ):
            return True

    windows = _word_windows(
        normalized_message
    )

    for window in windows:
        for term in terms:
            normalized_term = _normalize(
                term
            )

            if (
                abs(
                    len(window.split())
                    - len(
                        normalized_term.split()
                    )
                )
                > 1
            ):
                continue

            if _ratio(
                window,
                normalized_term,
            ) >= threshold:
                return True

    return False


def _extract_metric(
    message: str,
) -> str | None:
    normalized_message = _normalize(
        message
    )

    # Short KPI acronyms get exact/fuzzy priority so they are
    # not accidentally swallowed by longer business wording.
    for metric_name in (
        "ads",
        "adt",
        "apt",
    ):
        aliases = SUPPORTED_METRICS[
            metric_name
        ]["aliases"]

        if _contains_fuzzy_term(
            normalized_message,
            aliases,
            threshold=0.78,
        ):
            return metric_name

    for metric_name in (
        "transactions",
        "sales",
    ):
        aliases = SUPPORTED_METRICS[
            metric_name
        ]["aliases"]

        if _contains_fuzzy_term(
            normalized_message,
            aliases,
            threshold=0.76,
        ):
            return metric_name

    return None


def _extract_month_count(
    message: str,
) -> int | None:
    text = _normalize(
        message
    )

    direct = re.search(
        r"\blast\s+([1-9]\d*|one|two|three|four|five|six)\s+months?\b",
        text,
    )

    if direct:
        raw_count = direct.group(1)

        if raw_count.isdigit():
            return int(
                raw_count
            )

        return NUMBER_WORDS.get(
            raw_count
        )

    # Spelling-tolerant fallback for examples such as:
    # "last 4 mnths", "lst four months".
    tokens = text.split()

    for index, token in enumerate(
        tokens
    ):
        if _ratio(
            token,
            "last",
        ) < 0.72:
            continue

        if index + 1 >= len(
            tokens
        ):
            continue

        raw_count = tokens[
            index + 1
        ]

        if raw_count.isdigit():
            count = int(
                raw_count
            )
        else:
            count = None

            for word, number in NUMBER_WORDS.items():
                if _ratio(
                    raw_count,
                    word,
                ) >= 0.76:
                    count = number
                    break

        if count is None:
            continue

        if index + 2 >= len(
            tokens
        ):
            continue

        month_token = tokens[
            index + 2
        ]

        if max(
            _ratio(
                month_token,
                "month",
            ),
            _ratio(
                month_token,
                "months",
            ),
        ) >= 0.70:
            return count

    return None


def is_sales_trend_question(
    message: str,
) -> bool:
    """
    Fast deterministic guard used by the router.

    This capability activates only when the message contains:
    - a trend/plot/graph/chart idea,
    - one supported metric,
    - and a 'last N months' period.
    """
    if not str(
        message
    ).strip():
        return False

    has_trend_word = (
        _contains_fuzzy_term(
            message,
            TREND_WORDS,
            threshold=0.72,
        )
    )

    if not has_trend_word:
        return False

    if _extract_metric(
        message
    ) is None:
        return False

    return (
        _extract_month_count(
            message
        )
        is not None
    )


def _resolve_store(
    data: dict,
    message: str,
) -> tuple[str, set[str]] | None:
    """
    Resolve one store with light spelling tolerance.

    Returns:
        (canonical store name, normalized raw aliases)

    Returns None for company-level requests.
    """
    normalized_message = _normalize(
        message
    )

    company_terms = (
        "company",
        "overall",
        "all stores",
        "company wide",
        "companywide",
        "total company",
    )

    if any(
        term in normalized_message
        for term in company_terms
    ):
        return None

    store_dictionary = (
        build_store_dictionary(
            data=data
        )
    )

    message_tokens = (
        normalized_message.split()
    )

    best_canonical = None
    best_score = 0.0

    for (
        canonical_name,
        definition,
    ) in store_dictionary.items():
        aliases = list(
            definition.get(
                "aliases",
                [],
            )
        )

        aliases.append(
            canonical_name
        )

        for alias in aliases:
            normalized_alias = _normalize(
                alias
            )

            if not normalized_alias:
                continue

            alias_token_count = len(
                normalized_alias.split()
            )

            min_size = max(
                1,
                alias_token_count - 1,
            )

            max_size = min(
                len(message_tokens),
                alias_token_count + 1,
            )

            for size in range(
                min_size,
                max_size + 1,
            ):
                for index in range(
                    len(message_tokens)
                    - size
                    + 1
                ):
                    window = " ".join(
                        message_tokens[
                            index:index + size
                        ]
                    )

                    score = _ratio(
                        window,
                        normalized_alias,
                    )

                    if (
                        normalized_alias
                        in normalized_message
                    ):
                        score = max(
                            score,
                            0.99,
                        )

                    if score > best_score:
                        best_score = score
                        best_canonical = (
                            canonical_name
                        )

    # Conservative enough to avoid inventing a store, while
    # still accepting small typos such as "AMB mal".
    if (
        best_canonical is None
        or best_score < 0.78
    ):
        return None

    definition = store_dictionary[
        best_canonical
    ]

    accepted_aliases = {
        _normalize(
            alias
        )
        for alias in definition.get(
            "aliases",
            [],
        )
        if _normalize(
            alias
        )
    }

    accepted_aliases.add(
        _normalize(
            best_canonical
        )
    )

    return (
        best_canonical,
        accepted_aliases,
    )


def _completed_calendar_month_range(
    month_count: int,
    today=None,
) -> tuple[pd.Timestamp, pd.Timestamp]:
    if today is None:
        today = datetime.now(
            IST
        ).date()

    current_month_start = pd.Timestamp(
        year=today.year,
        month=today.month,
        day=1,
    )

    start_date = (
        current_month_start
        - pd.DateOffset(
            months=month_count
        )
    )

    end_date = (
        current_month_start
        - pd.Timedelta(
            days=1
        )
    )

    return (
        start_date.normalize(),
        end_date.normalize(),
    )


def get_sales_trend_report(
    data: dict,
    message: str,
    today=None,
) -> dict:
    """
    Build the bounded RestaurantAI monthly trend report.

    Supported:
        Sales, Transactions, ADS, ADT, APT
        Company or one store
        Last 1-6 completed calendar months

    Example on 18-Aug-2026:
        last 4 months -> Apr, May, Jun, Jul 2026
    """
    metric = _extract_metric(
        message
    )

    if metric is None:
        raise ValueError(
            "Please ask for a Sales, Transactions, ADS, ADT or APT trend."
        )

    month_count = _extract_month_count(
        message
    )

    if month_count is None:
        raise ValueError(
            "Please specify the period as last 1 to 6 months."
        )

    if not 1 <= month_count <= 6:
        raise ValueError(
            "Trend reports currently support only the last 1 to 6 completed calendar months."
        )

    if "sales" not in data:
        raise ValueError(
            "Sales data is not available."
        )

    sales = data[
        "sales"
    ].copy()

    if DATE_COLUMN not in sales.columns:
        raise ValueError(
            "Sales data does not contain Date column."
        )

    sales[
        "__trend_date"
    ] = pd.to_datetime(
        sales[
            DATE_COLUMN
        ],
        errors="coerce",
        dayfirst=True,
    ).dt.normalize()

    sales = sales.loc[
        sales[
            "__trend_date"
        ].notna()
    ].copy()

    store_result = _resolve_store(
        data=data,
        message=message,
    )

    if store_result is None:
        scope_name = "Company"
        filtered_sales = sales
    else:
        (
            scope_name,
            accepted_aliases,
        ) = store_result

        if SOURCE_STORE_COLUMN not in sales.columns:
            raise ValueError(
                "Sales data does not contain Restaurant column."
            )

        normalized_stores = (
            sales[
                SOURCE_STORE_COLUMN
            ]
            .fillna("")
            .map(
                _normalize
            )
        )

        filtered_sales = sales.loc[
            normalized_stores.isin(
                accepted_aliases
            )
        ].copy()

    (
        start_date,
        end_date,
    ) = _completed_calendar_month_range(
        month_count=month_count,
        today=today,
    )

    filtered_sales = filtered_sales.loc[
        filtered_sales[
            "__trend_date"
        ].between(
            start_date,
            end_date,
            inclusive="both",
        )
    ].copy()

    month_starts = pd.date_range(
        start=start_date,
        periods=month_count,
        freq="MS",
    )

    points: list[dict] = []

    for month_start in month_starts:
        next_month_start = (
            month_start
            + pd.DateOffset(
                months=1
            )
        )

        month_rows = filtered_sales.loc[
            (
                filtered_sales[
                    "__trend_date"
                ]
                >= month_start
            )
            & (
                filtered_sales[
                    "__trend_date"
                ]
                < next_month_start
            )
        ].copy()

        metric_value = calculate_metric(
            metric_name=metric,
            filtered_df=month_rows,
        )

        points.append(
            {
                "month": (
                    month_start.strftime(
                        "%b %Y"
                    )
                ),
                "value": float(
                    metric_value
                ),
            }
        )

    metric_display = (
        SUPPORTED_METRICS[
            metric
        ]["display_name"]
    )

    return {
        "metric": metric,
        "metric_display": metric_display,
        "scope": scope_name,
        "month_count": month_count,
        "start_date": start_date.strftime(
            "%Y-%m-%d"
        ),
        "end_date": end_date.strftime(
            "%Y-%m-%d"
        ),
        "points": points,
        "title": (
            f"{scope_name} {metric_display} Trend – "
            f"Last {month_count} "
            f"{'Month' if month_count == 1 else 'Months'}"
        ),
        "subtitle": (
            f"{start_date.strftime('%b %Y')} to "
            f"{end_date.strftime('%b %Y')} | "
            "Completed calendar months"
        ),
    }
