from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Final

import pandas as pd

from services.intelligence.company_performance_scanner import (
    IST,
    _prepare_sales_frame,
)
from services.intelligence.store_performance_scanner import (
    _prepare_store_mapping,
    _store_display_name,
)


# =========================================================
# PRODUCT ZERO-SALES CONFIGURATION
# =========================================================

BASELINE_CALENDAR_DAYS: Final[int] = 28

# A product must have sold on at least 14 operating days
# in the baseline window...
MIN_BASELINE_SELLING_DAYS: Final[int] = 14

# ...and on at least 50% of the store's operating days.
MIN_BASELINE_SELLING_FREQUENCY_PCT: Final[float] = 50.0

# Avoid noise from extremely low-volume items.
MIN_BASELINE_TOTAL_UNITS: Final[float] = 10.0

# First V1 anomaly rule.
ZERO_SALES_OPERATING_DAYS: Final[int] = 3

# Only look back across the latest 30 calendar days, ending yesterday.
# This caps stale/renamed product history from creating very long zero-sale
# streaks while preserving the 3-operating-day minimum alert threshold.
ZERO_SALES_ROLLING_CALENDAR_DAYS: Final[int] = 30


# =========================================================
# COLUMN HELPERS
# =========================================================


def _find_first_existing_column(
    columns,
    candidates,
):
    normalized = {
        str(column).strip().lower(): column
        for column in columns
    }

    for candidate in candidates:
        key = candidate.strip().lower()

        if key in normalized:
            return normalized[key]

    return None


def _resolve_item_column(
    sales: pd.DataFrame,
):
    item_column = _find_first_existing_column(
        sales.columns,
        (
            "Item Name",
            "Item",
            "Product Name",
            "Product",
        ),
    )

    if item_column is None:
        raise ValueError(
            "Could not find an item/product column in sales data."
        )

    return item_column


def _resolve_quantity_column(
    sales: pd.DataFrame,
):
    """
    Try common POS quantity column names.

    If no quantity column exists, the detector falls back to
    counting item-line occurrences. That still allows the
    disappearance logic to work, while exposing the measure used
    in the output.
    """
    return _find_first_existing_column(
        sales.columns,
        (
            "Quantity",
            "Qty",
            "Item Qty",
            "Item Quantity",
            "QTY",
        ),
    )


def _resolve_category_column(
    sales: pd.DataFrame,
):
    return _find_first_existing_column(
        sales.columns,
        (
            "Category",
            "Item Category",
            "Category Name",
        ),
    )


# =========================================================
# SALES PREPARATION
# =========================================================


def _prepare_product_sales(
    data: dict,
) -> tuple[
    pd.DataFrame,
    str,
    str | None,
    str | None,
]:
    sales = _prepare_sales_frame(
        data
    )

    item_column = _resolve_item_column(
        sales
    )

    quantity_column = _resolve_quantity_column(
        sales
    )

    category_column = _resolve_category_column(
        sales
    )

    sales = sales[
        sales[item_column].notna()
    ].copy()

    sales[item_column] = (
        sales[item_column]
        .astype(str)
        .str.strip()
    )

    sales = sales[
        sales[item_column] != ""
    ].copy()

    if quantity_column is not None:
        sales["_ProductUnits"] = (
            pd.to_numeric(
                sales[quantity_column],
                errors="coerce",
            )
            .fillna(0.0)
            .astype(float)
        )

        # Defensive handling in case a POS export has negative
        # reversal lines. For "did this item sell?" evidence, only
        # positive units count as sale activity.
        sales["_PositiveProductUnits"] = (
            sales["_ProductUnits"]
            .clip(lower=0.0)
        )

        volume_measure = (
            f"quantity:{quantity_column}"
        )

    else:
        sales["_ProductUnits"] = 1.0
        sales["_PositiveProductUnits"] = 1.0

        volume_measure = "item_line_count"

    return (
        sales,
        item_column,
        category_column,
        volume_measure,
    )


# =========================================================
# STORE OPERATING DAYS
# =========================================================


def _store_operating_dates(
    store_sales: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> list[date]:
    """
    A store is considered operating on a date if the store has
    at least one sales row on that date.

    This prevents a closed store day from generating dozens of
    false product-zero anomalies.
    """
    period = store_sales[
        store_sales[
            "Date"
        ].between(
            start_date,
            end_date,
            inclusive="both",
        )
    ]

    # A store is operational only when its total sales for the day are
    # positive. Merely having rows in the export is not enough.
    daily_sales = (
        period.groupby("Date")["Sub Total"]
        .sum()
    )

    return sorted(
        daily_sales[
            daily_sales > 0
        ]
        .index
        .tolist()
    )


def _latest_operating_days(
    store_sales: pd.DataFrame,
    performance_through: date,
    count: int,
) -> list[date]:
    eligible = store_sales[
        store_sales["Date"] <= performance_through
    ]

    daily_sales = (
        eligible.groupby("Date")["Sub Total"]
        .sum()
    )

    dates = sorted(
        daily_sales[
            daily_sales > 0
        ]
        .index
        .tolist()
    )

    return dates[-count:]


# =========================================================
# PRODUCT BASELINE
# =========================================================


def _product_daily_units(
    store_sales: pd.DataFrame,
    item_column: str,
    item_name: str,
) -> pd.Series:
    item_sales = store_sales[
        store_sales[
            item_column
        ] == item_name
    ]

    if item_sales.empty:
        return pd.Series(
            dtype=float
        )

    return (
        item_sales
        .groupby(
            "Date"
        )[
            "_PositiveProductUnits"
        ]
        .sum()
    )


def _baseline_evidence(
    store_sales: pd.DataFrame,
    item_column: str,
    item_name: str,
    baseline_start: date,
    baseline_end: date,
) -> dict:
    operating_dates = (
        _store_operating_dates(
            store_sales=store_sales,
            start_date=baseline_start,
            end_date=baseline_end,
        )
    )

    daily_units = _product_daily_units(
        store_sales=store_sales,
        item_column=item_column,
        item_name=item_name,
    )

    baseline_units = [
        float(
            daily_units.get(
                operating_date,
                0.0,
            )
        )
        for operating_date
        in operating_dates
    ]

    selling_days = sum(
        1
        for units in baseline_units
        if units > 0
    )

    operating_day_count = len(
        operating_dates
    )

    total_units = float(
        sum(
            baseline_units
        )
    )

    selling_frequency_pct = (
        (
            selling_days
            / operating_day_count
        ) * 100.0
        if operating_day_count > 0
        else 0.0
    )

    avg_units_per_operating_day = (
        total_units
        / operating_day_count
        if operating_day_count > 0
        else 0.0
    )

    avg_units_per_selling_day = (
        total_units
        / selling_days
        if selling_days > 0
        else 0.0
    )

    qualifies_normal_seller = (
        selling_days
        >= MIN_BASELINE_SELLING_DAYS
        and selling_frequency_pct
        >= MIN_BASELINE_SELLING_FREQUENCY_PCT
        and total_units
        >= MIN_BASELINE_TOTAL_UNITS
    )

    return {
        "baseline_start": (
            baseline_start.isoformat()
        ),
        "baseline_end": (
            baseline_end.isoformat()
        ),
        "store_operating_days": (
            operating_day_count
        ),
        "selling_days": (
            selling_days
        ),
        "selling_frequency_pct": (
            selling_frequency_pct
        ),
        "total_units": (
            total_units
        ),
        "avg_units_per_operating_day": (
            avg_units_per_operating_day
        ),
        "avg_units_per_selling_day": (
            avg_units_per_selling_day
        ),
        "qualifies_normal_seller": (
            qualifies_normal_seller
        ),
    }


# =========================================================
# LAST SOLD DATE
# =========================================================


def _last_sold_date_before_window(
    store_sales: pd.DataFrame,
    item_column: str,
    item_name: str,
    anomaly_start: date,
) -> str | None:
    item_sales = store_sales[
        (
            store_sales[
                item_column
            ] == item_name
        )
        & (
            store_sales[
                "Date"
            ] < anomaly_start
        )
        & (
            store_sales[
                "_PositiveProductUnits"
            ] > 0
        )
    ]

    if item_sales.empty:
        return None

    return (
        max(
            item_sales[
                "Date"
            ]
        )
        .isoformat()
    )


# =========================================================
# OBSERVATION / PRIORITY
# =========================================================


def _priority_from_baseline(
    baseline: dict,
) -> str:
    """
    Initial prioritisation only.

    Strong-normal sellers deserve more attention than borderline
    normal sellers. We will evolve this using Auberry's real output.
    """
    frequency = float(
        baseline[
            "selling_frequency_pct"
        ]
    )

    avg_units = float(
        baseline[
            "avg_units_per_operating_day"
        ]
    )

    if (
        frequency >= 80.0
        and avg_units >= 5.0
    ):
        return "high"

    if frequency >= 65.0:
        return "medium"

    return "review"


def _build_observation(
    store_name: str,
    item_name: str,
    baseline: dict,
    zero_dates: list[date],
    last_sold_date: str | None,
) -> str:
    zero_date_text = ", ".join(
        value.strftime(
            "%d %b"
        )
        for value in zero_dates
    )

    last_sold_text = (
        last_sold_date
        if last_sold_date is not None
        else "not available"
    )

    return (
        f"{item_name} at {store_name} normally sold on "
        f"{baseline['selling_days']} of "
        f"{baseline['store_operating_days']} store operating days "
        f"in the preceding baseline period "
        f"({baseline['selling_frequency_pct']:.1f}% frequency), "
        f"but recorded zero sales on the latest "
        f"{len(zero_dates)} consecutive store operating days "
        f"({zero_date_text}). Last sold before this window: "
        f"{last_sold_text}. This is unusual versus its recent "
        f"selling pattern and may warrant an "
        f"availability/operational check."
    )


# =========================================================
# PUBLIC PRODUCT ZERO-SALES INTELLIGENCE
# =========================================================
# =========================================================
# PUBLIC PRODUCT ZERO-SALES INTELLIGENCE
# =========================================================


def _trailing_zero_sales_operating_dates(
    operating_dates: list[date],
    daily_units: pd.Series,
) -> list[date]:
    """Return the trailing zero-sales streak inside the supplied window.

    The supplied operating_dates are already restricted to the rolling
    30-calendar-day window ending yesterday. Closed/non-operating dates are
    ignored because the input list contains only store operating dates.
    """
    streak_reversed: list[date] = []

    for operating_date in reversed(operating_dates):
        units = float(daily_units.get(operating_date, 0.0))

        if units > 0:
            break

        streak_reversed.append(operating_date)

    return list(reversed(streak_reversed))


def detect_product_zero_sales(
    data: dict,
    as_of_date: date | None = None,
) -> dict:
    """
    Detect normally-selling Store x Item combinations whose current
    zero-sales streak has reached at least 3 store operating days.

    Important rule:
    - 3 operating days is only the minimum alert threshold.
    - Zero-sales history is checked only inside the latest 30 calendar days,
      ending yesterday. RestaurantAI never reaches farther back than this
      window when calculating the displayed zero-sales streak.
    - Within that 30-day window, the current consecutive zero-sales streak is
      measured on store operating days only.
    - Baseline evidence is measured in the 28 calendar days immediately
      before the zero-sales streak begins inside this rolling window.
    """
    (
        sales,
        item_column,
        category_column,
        volume_measure,
    ) = _prepare_product_sales(data)

    today = (
        as_of_date
        if as_of_date is not None
        else datetime.now(IST).date()
    )
    performance_through = today - timedelta(days=1)

    store_mapping = _prepare_store_mapping(data)

    restaurants = sorted(
        sales["Restaurant"]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    anomalies: list[dict] = []
    store_summaries: list[dict] = []

    for restaurant_name in restaurants:
        store_sales = sales[
            sales["Restaurant"].astype(str) == restaurant_name
        ].copy()

        store_name = _store_display_name(
            restaurant_name,
            store_mapping,
        )

        rolling_window_start = performance_through - timedelta(
            days=ZERO_SALES_ROLLING_CALENDAR_DAYS - 1
        )

        operating_dates = _store_operating_dates(
            store_sales=store_sales,
            start_date=rolling_window_start,
            end_date=performance_through,
        )

        if len(operating_dates) < ZERO_SALES_OPERATING_DAYS:
            store_summaries.append(
                {
                    "store": store_name,
                    "status": "insufficient_operating_history",
                    "latest_operating_days": [
                        value.isoformat()
                        for value in operating_dates[-ZERO_SALES_OPERATING_DAYS:]
                    ],
                    "anomaly_count": 0,
                }
            )
            continue

        # Consider every item that has appeared at this store, but calculate
        # its zero-sales streak only inside the rolling 30-calendar-day window.
        # Older history is deliberately ignored for the streak calculation.
        candidate_items = sorted(
            store_sales[item_column]
            .dropna()
            .astype(str)
            .unique()
            .tolist()
        )

        store_anomaly_count = 0

        for item_name in candidate_items:
            daily_units = _product_daily_units(
                store_sales=store_sales,
                item_column=item_column,
                item_name=item_name,
            )

            zero_dates = _trailing_zero_sales_operating_dates(
                operating_dates=operating_dates,
                daily_units=daily_units,
            )

            if len(zero_dates) < ZERO_SALES_OPERATING_DAYS:
                continue

            anomaly_start = zero_dates[0]
            baseline_end = anomaly_start - timedelta(days=1)
            baseline_start = baseline_end - timedelta(
                days=BASELINE_CALENDAR_DAYS - 1
            )

            baseline = _baseline_evidence(
                store_sales=store_sales,
                item_column=item_column,
                item_name=item_name,
                baseline_start=baseline_start,
                baseline_end=baseline_end,
            )

            if not baseline["qualifies_normal_seller"]:
                continue

            zero_window_units = [
                float(daily_units.get(operating_date, 0.0))
                for operating_date in zero_dates
            ]

            last_sold_date = _last_sold_date_before_window(
                store_sales=store_sales,
                item_column=item_column,
                item_name=item_name,
                anomaly_start=anomaly_start,
            )

            category = None
            if category_column is not None:
                category_rows = (
                    store_sales[
                        store_sales[item_column] == item_name
                    ][category_column]
                    .dropna()
                    .astype(str)
                    .str.strip()
                )
                if not category_rows.empty:
                    category = category_rows.iloc[-1]

            priority = _priority_from_baseline(baseline)

            observation = _build_observation(
                store_name=store_name,
                item_name=item_name,
                baseline=baseline,
                zero_dates=zero_dates,
                last_sold_date=last_sold_date,
            )

            anomalies.append(
                {
                    "store": store_name,
                    "restaurant": restaurant_name,
                    "item": item_name,
                    "category": category,
                    "priority": priority,
                    "status": "product_zero_sales_anomaly",
                    "zero_sales_operating_days": len(zero_dates),
                    "zero_sales_dates": [
                        value.isoformat()
                        for value in zero_dates
                    ],
                    "zero_window_units": zero_window_units,
                    "last_sold_date": last_sold_date,
                    "baseline": baseline,
                    "observation": observation,
                }
            )
            store_anomaly_count += 1

        store_summaries.append(
            {
                "store": store_name,
                "status": "scanned",
                "latest_operating_days": [
                    value.isoformat()
                    for value in operating_dates[-ZERO_SALES_OPERATING_DAYS:]
                ],
                "anomaly_count": store_anomaly_count,
            }
        )

    priority_rank = {
        "high": 0,
        "medium": 1,
        "review": 2,
    }

    # Longest current zero-sales streak first within each store. Store order
    # itself is alphabetical here; the morning-report formatter preserves the
    # first-seen store grouping and separately sorts each store's products by
    # streak length descending.
    anomalies.sort(
        key=lambda item: (
            item["store"].casefold(),
            -int(item["zero_sales_operating_days"]),
            priority_rank.get(item["priority"], 99),
            -float(item["baseline"]["selling_frequency_pct"]),
            -float(item["baseline"]["avg_units_per_operating_day"]),
            item["item"].casefold(),
        )
    )

    return {
        "observation_type": "product_zero_sales",
        "as_of_date": today.isoformat(),
        "performance_through": performance_through.isoformat(),
        "item_column": item_column,
        "volume_measure": volume_measure,
        "rules": {
            "baseline_calendar_days": BASELINE_CALENDAR_DAYS,
            "min_baseline_selling_days": MIN_BASELINE_SELLING_DAYS,
            "min_baseline_selling_frequency_pct": MIN_BASELINE_SELLING_FREQUENCY_PCT,
            "min_baseline_total_units": MIN_BASELINE_TOTAL_UNITS,
            "zero_sales_operating_days": ZERO_SALES_OPERATING_DAYS,
            "zero_sales_rolling_calendar_days": ZERO_SALES_ROLLING_CALENDAR_DAYS,
        },
        "store_count": len(restaurants),
        "anomaly_count": len(anomalies),
        "anomalies": anomalies,
        "stores": store_summaries,
    }
