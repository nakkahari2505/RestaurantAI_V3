from __future__ import annotations

from datetime import date
from typing import Final

import pandas as pd

from services.intelligence.company_performance_scanner import (
    _period_metrics,
    _prepare_sales_frame,
    _slice_period,
)
from services.analytics.grouping_engine import (
    DERIVED_CATEGORY_COLUMN,
    DERIVED_CHANNEL_COLUMN,
    DERIVED_ITEM_COLUMN,
    DERIVED_STORE_COLUMN,
    _prepare_grouping_dataframe,
)
from services.semantics.vocabulary.metrics import (
    calculate_sales,
    calculate_transactions,
)


# =========================================================
# PERFORMANCE DRILL-DOWN CONFIGURATION
# =========================================================

STABLE_THRESHOLD_PCT: Final[float] = 3.0

# Limit the evidence package so the eventual narrative layer gets
# the most important contributors rather than hundreds of rows.
TOP_CONTRIBUTORS: Final[int] = 5


# =========================================================
# BASIC HELPERS
# =========================================================


def _safe_pct_change(
    current: float,
    comparison: float,
) -> float | None:
    current = float(current)
    comparison = float(comparison)

    if comparison == 0:
        if current == 0:
            return 0.0

        return None

    return (
        (current - comparison)
        / abs(comparison)
    ) * 100.0


def _direction(
    change_pct: float | None,
) -> str:
    if change_pct is None:
        return "not_comparable"

    if abs(change_pct) < STABLE_THRESHOLD_PCT:
        return "stable"

    return (
        "up"
        if change_pct > 0
        else "down"
    )


def _round_or_none(
    value: float | None,
    digits: int = 2,
) -> float | None:
    if value is None:
        return None

    return round(
        float(value),
        digits,
    )


# =========================================================
# PERIOD / STORE PREPARATION
# =========================================================


def _prepare_period_frames(
    data: dict,
    current_start: date,
    current_end: date,
    comparison_start: date,
    comparison_end: date,
    store: str | None = None,
) -> tuple[
    pd.DataFrame,
    pd.DataFrame,
]:
    """
    Prepare the current and comparison DataFrames using the same
    canonical Store / Channel / Category / Item dimensions already
    used by RestaurantAI's grouping engine.
    """
    sales = _prepare_sales_frame(
        data
    )

    prepared = _prepare_grouping_dataframe(
        filtered_sales=sales,
        data=data,
    )

    if store is not None:
        normalized_store = (
            str(store)
            .strip()
            .lower()
        )

        store_series = (
            prepared[
                DERIVED_STORE_COLUMN
            ]
            .fillna("")
            .astype(str)
            .str.strip()
            .str.lower()
        )

        prepared = prepared[
            store_series
            == normalized_store
        ].copy()

    current_df = _slice_period(
        sales=prepared,
        start_date=current_start,
        end_date=current_end,
    )

    comparison_df = _slice_period(
        sales=prepared,
        start_date=comparison_start,
        end_date=comparison_end,
    )

    return (
        current_df,
        comparison_df,
    )


# =========================================================
# ADS -> ADT x APT DECOMPOSITION
# =========================================================


def _decompose_ads(
    current_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    current_start: date,
    current_end: date,
    comparison_start: date,
    comparison_end: date,
) -> dict:
    current = _period_metrics(
        period_df=current_df,
        start_date=current_start,
        end_date=current_end,
    )

    comparison = _period_metrics(
        period_df=comparison_df,
        start_date=comparison_start,
        end_date=comparison_end,
    )

    ads_change_pct = _safe_pct_change(
        current["ads"],
        comparison["ads"],
    )

    adt_change_pct = _safe_pct_change(
        current["adt"],
        comparison["adt"],
    )

    apt_change_pct = _safe_pct_change(
        current["apt"],
        comparison["apt"],
    )

    adt_direction = _direction(
        adt_change_pct
    )

    apt_direction = _direction(
        apt_change_pct
    )

    # This is the frozen RestaurantAI decision skeleton.
    if (
        adt_direction == "down"
        and apt_direction == "down"
    ):
        driver = "both"

    elif (
        adt_direction == "down"
        and apt_direction in {
            "up",
            "stable",
        }
    ):
        driver = "transactions"

    elif (
        apt_direction == "down"
        and adt_direction in {
            "up",
            "stable",
        }
    ):
        driver = "apt"

    elif (
        adt_direction == "up"
        and apt_direction == "up"
    ):
        driver = "both_positive"

    elif (
        adt_direction == "up"
        and apt_direction == "down"
    ):
        driver = (
            "transactions"
            if abs(
                adt_change_pct or 0.0
            )
            >= abs(
                apt_change_pct or 0.0
            )
            else "apt"
        )

    elif (
        adt_direction == "down"
        and apt_direction == "up"
    ):
        driver = (
            "transactions"
            if abs(
                adt_change_pct or 0.0
            )
            >= abs(
                apt_change_pct or 0.0
            )
            else "apt"
        )

    else:
        driver = "stable_or_mixed"

    return {
        "current": {
            key: _round_or_none(
                value
            )
            for (
                key,
                value,
            ) in current.items()
        },
        "comparison": {
            key: _round_or_none(
                value
            )
            for (
                key,
                value,
            ) in comparison.items()
        },
        "movement": {
            "sales_change_pct": (
                _round_or_none(
                    _safe_pct_change(
                        current["sales"],
                        comparison["sales"],
                    )
                )
            ),
            "transactions_change_pct": (
                _round_or_none(
                    _safe_pct_change(
                        current[
                            "transactions"
                        ],
                        comparison[
                            "transactions"
                        ],
                    )
                )
            ),
            "ads_change_pct": (
                _round_or_none(
                    ads_change_pct
                )
            ),
            "adt_change_pct": (
                _round_or_none(
                    adt_change_pct
                )
            ),
            "apt_change_pct": (
                _round_or_none(
                    apt_change_pct
                )
            ),
            "adt_direction": (
                adt_direction
            ),
            "apt_direction": (
                apt_direction
            ),
            "primary_driver": (
                driver
            ),
        },
    }


# =========================================================
# DIMENSION CONTRIBUTION ENGINE
# =========================================================


DIMENSION_COLUMNS: Final[
    dict[str, str]
] = {
    "channel": (
        DERIVED_CHANNEL_COLUMN
    ),
    "category": (
        DERIVED_CATEGORY_COLUMN
    ),
    "item": (
        DERIVED_ITEM_COLUMN
    ),
}


def _dimension_values(
    current_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    dimension_column: str,
) -> list[str]:
    values = set()

    for frame in (
        current_df,
        comparison_df,
    ):
        if dimension_column not in frame.columns:
            continue

        values.update(
            frame[
                dimension_column
            ]
            .fillna("Unspecified")
            .astype(str)
            .str.strip()
            .replace(
                "",
                "Unspecified",
            )
            .tolist()
        )

    return sorted(
        values
    )


def _dimension_frame(
    frame: pd.DataFrame,
    dimension_column: str,
    dimension_value: str,
) -> pd.DataFrame:
    series = (
        frame[
            dimension_column
        ]
        .fillna("Unspecified")
        .astype(str)
        .str.strip()
        .replace(
            "",
            "Unspecified",
        )
    )

    return frame[
        series
        == dimension_value
    ].copy()


def _dimension_contribution(
    current_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
    dimension: str,
) -> list[dict]:
    """
    Calculate deterministic contribution evidence.

    SALES is additive across Channel/Category/Item.

    For transactions:
      - Channel transaction counts are normally additive because an
        order belongs to one channel.
      - Category/Item transaction counts mean "transactions containing
        this category/item". They are NOT additive because one bill can
        contain multiple categories/items.

    We expose that distinction explicitly rather than pretending all
    grouped transaction counts reconcile to total transactions.
    """
    dimension_column = (
        DIMENSION_COLUMNS[
            dimension
        ]
    )

    values = _dimension_values(
        current_df=current_df,
        comparison_df=comparison_df,
        dimension_column=dimension_column,
    )

    rows: list[dict] = []

    for value in values:
        current_group = _dimension_frame(
            frame=current_df,
            dimension_column=(
                dimension_column
            ),
            dimension_value=value,
        )

        comparison_group = (
            _dimension_frame(
                frame=comparison_df,
                dimension_column=(
                    dimension_column
                ),
                dimension_value=value,
            )
        )

        current_sales = float(
            calculate_sales(
                current_group
            )
        )

        comparison_sales = float(
            calculate_sales(
                comparison_group
            )
        )

        current_transactions = float(
            calculate_transactions(
                current_group
            )
        )

        comparison_transactions = float(
            calculate_transactions(
                comparison_group
            )
        )

        sales_delta = (
            current_sales
            - comparison_sales
        )

        transaction_delta = (
            current_transactions
            - comparison_transactions
        )

        current_apt = (
            current_sales
            / current_transactions
            if current_transactions > 0
            else 0.0
        )

        comparison_apt = (
            comparison_sales
            / comparison_transactions
            if comparison_transactions > 0
            else 0.0
        )

        rows.append(
            {
                "dimension": (
                    dimension
                ),
                "value": value,
                "current_sales": (
                    round(
                        current_sales,
                        2,
                    )
                ),
                "comparison_sales": (
                    round(
                        comparison_sales,
                        2,
                    )
                ),
                "sales_delta": (
                    round(
                        sales_delta,
                        2,
                    )
                ),
                "sales_change_pct": (
                    _round_or_none(
                        _safe_pct_change(
                            current_sales,
                            comparison_sales,
                        )
                    )
                ),
                "current_transactions": (
                    round(
                        current_transactions,
                        2,
                    )
                ),
                "comparison_transactions": (
                    round(
                        comparison_transactions,
                        2,
                    )
                ),
                "transaction_delta": (
                    round(
                        transaction_delta,
                        2,
                    )
                ),
                "transactions_change_pct": (
                    _round_or_none(
                        _safe_pct_change(
                            current_transactions,
                            comparison_transactions,
                        )
                    )
                ),
                "current_apt": (
                    round(
                        current_apt,
                        2,
                    )
                ),
                "comparison_apt": (
                    round(
                        comparison_apt,
                        2,
                    )
                ),
                "apt_change_pct": (
                    _round_or_none(
                        _safe_pct_change(
                            current_apt,
                            comparison_apt,
                        )
                    )
                ),
                "transaction_measure": (
                    "unique_transactions"
                    if dimension == "channel"
                    else (
                        "transactions_containing_"
                        + dimension
                    )
                ),
                "transaction_additive": (
                    dimension
                    == "channel"
                ),
            }
        )

    return rows


# =========================================================
# CONTRIBUTOR RANKING
# =========================================================


def _rank_negative_contributors(
    rows: list[dict],
    field: str,
    limit: int = TOP_CONTRIBUTORS,
) -> list[dict]:
    negative_rows = [
        row
        for row in rows
        if float(
            row.get(
                field,
                0.0,
            )
            or 0.0
        ) < 0
    ]

    negative_rows.sort(
        key=lambda row: float(
            row.get(
                field,
                0.0,
            )
            or 0.0
        )
    )

    return negative_rows[
        :limit
    ]


def _rank_positive_contributors(
    rows: list[dict],
    field: str,
    limit: int = TOP_CONTRIBUTORS,
) -> list[dict]:
    positive_rows = [
        row
        for row in rows
        if float(
            row.get(
                field,
                0.0,
            )
            or 0.0
        ) > 0
    ]

    positive_rows.sort(
        key=lambda row: float(
            row.get(
                field,
                0.0,
            )
            or 0.0
        ),
        reverse=True,
    )

    return positive_rows[
        :limit
    ]


# =========================================================
# ADT / TRANSACTION-LOSS BRANCH
# =========================================================


def _transaction_drilldown(
    current_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
) -> dict:
    """
    Investigate transaction weakness.

    Channel is the strongest transaction decomposition because
    channel transaction counts are normally additive.

    Category and Item are included as transaction-participation
    evidence, not as additive transaction totals.
    """
    channel_rows = (
        _dimension_contribution(
            current_df=current_df,
            comparison_df=comparison_df,
            dimension="channel",
        )
    )

    category_rows = (
        _dimension_contribution(
            current_df=current_df,
            comparison_df=comparison_df,
            dimension="category",
        )
    )

    item_rows = (
        _dimension_contribution(
            current_df=current_df,
            comparison_df=comparison_df,
            dimension="item",
        )
    )

    return {
        "branch": "transactions",
        "channel": {
            "largest_transaction_losses": (
                _rank_negative_contributors(
                    channel_rows,
                    field=(
                        "transaction_delta"
                    ),
                )
            ),
            "largest_transaction_gains": (
                _rank_positive_contributors(
                    channel_rows,
                    field=(
                        "transaction_delta"
                    ),
                )
            ),
            "all_rows": channel_rows,
        },
        "category": {
            "largest_participation_losses": (
                _rank_negative_contributors(
                    category_rows,
                    field=(
                        "transaction_delta"
                    ),
                )
            ),
            "all_rows": category_rows,
            "note": (
                "Category transaction counts are transactions "
                "containing the category and are not additive."
            ),
        },
        "item": {
            "largest_participation_losses": (
                _rank_negative_contributors(
                    item_rows,
                    field=(
                        "transaction_delta"
                    ),
                )
            ),
            "all_rows": item_rows,
            "note": (
                "Item transaction counts are transactions containing "
                "the item and are not additive."
            ),
        },
    }


# =========================================================
# APT / TICKET-VALUE BRANCH
# =========================================================


def _apt_drilldown(
    current_df: pd.DataFrame,
    comparison_df: pd.DataFrame,
) -> dict:
    """
    Investigate APT deterioration.

    We initially inspect:
      - Channel APT movement
      - Category sales/mix + category-level ticket participation
      - Item sales/mix + item-level ticket participation

    This gives deterministic evidence for the next refinement of
    ticket/basket intelligence without pretending POS sales alone
    proves a behavioral cause.
    """
    channel_rows = (
        _dimension_contribution(
            current_df=current_df,
            comparison_df=comparison_df,
            dimension="channel",
        )
    )

    category_rows = (
        _dimension_contribution(
            current_df=current_df,
            comparison_df=comparison_df,
            dimension="category",
        )
    )

    item_rows = (
        _dimension_contribution(
            current_df=current_df,
            comparison_df=comparison_df,
            dimension="item",
        )
    )

    return {
        "branch": "apt",
        "channel": {
            "largest_sales_losses": (
                _rank_negative_contributors(
                    channel_rows,
                    field="sales_delta",
                )
            ),
            "all_rows": channel_rows,
        },
        "category": {
            "largest_sales_losses": (
                _rank_negative_contributors(
                    category_rows,
                    field="sales_delta",
                )
            ),
            "largest_sales_gains": (
                _rank_positive_contributors(
                    category_rows,
                    field="sales_delta",
                )
            ),
            "all_rows": category_rows,
        },
        "item": {
            "largest_sales_losses": (
                _rank_negative_contributors(
                    item_rows,
                    field="sales_delta",
                )
            ),
            "largest_sales_gains": (
                _rank_positive_contributors(
                    item_rows,
                    field="sales_delta",
                )
            ),
            "all_rows": item_rows,
        },
    }


# =========================================================
# PUBLIC PERFORMANCE DRILL-DOWN
# =========================================================


def drilldown_performance(
    data: dict,
    current_start: date,
    current_end: date,
    comparison_start: date,
    comparison_end: date,
    store: str | None = None,
) -> dict:
    """
    RestaurantAI deterministic WHY engine.

    Scope:
        company, or one canonical store.

    Flow:
        1. Calculate Sales / Txns / ADS / ADT / APT.
        2. Decompose ADS through ADT and APT.
        3. Choose the relevant investigation branch.
        4. Rank contributors by ABSOLUTE business impact,
           not spectacular percentage movement.

    Driver rules:
        ADT down, APT stable/up -> transaction branch
        APT down, ADT stable/up -> APT branch
        both down               -> run both branches
        positive/stable         -> evidence remains available,
                                   but no deep negative investigation
                                   is forced.

    This layer intentionally does NOT:
        - call GPT,
        - claim causality,
        - decide WhatsApp delivery,
        - override anomaly/persistence rules.
    """
    if current_end < current_start:
        raise ValueError(
            "Current period end date cannot be before start date."
        )

    if comparison_end < comparison_start:
        raise ValueError(
            "Comparison period end date cannot be before start date."
        )

    (
        current_df,
        comparison_df,
    ) = _prepare_period_frames(
        data=data,
        current_start=current_start,
        current_end=current_end,
        comparison_start=(
            comparison_start
        ),
        comparison_end=(
            comparison_end
        ),
        store=store,
    )

    decomposition = _decompose_ads(
        current_df=current_df,
        comparison_df=comparison_df,
        current_start=current_start,
        current_end=current_end,
        comparison_start=(
            comparison_start
        ),
        comparison_end=(
            comparison_end
        ),
    )

    primary_driver = (
        decomposition[
            "movement"
        ][
            "primary_driver"
        ]
    )

    sales_change_pct = (
        decomposition[
            "movement"
        ][
            "sales_change_pct"
        ]
    )

    negative_sales = (
        sales_change_pct is not None
        and sales_change_pct
        <= -STABLE_THRESHOLD_PCT
    )

    branches: dict = {}

    if negative_sales:
        if primary_driver in {
            "transactions",
            "both",
        }:
            branches[
                "transactions"
            ] = _transaction_drilldown(
                current_df=current_df,
                comparison_df=(
                    comparison_df
                ),
            )

        if primary_driver in {
            "apt",
            "both",
        }:
            branches[
                "apt"
            ] = _apt_drilldown(
                current_df=current_df,
                comparison_df=(
                    comparison_df
                ),
            )

    return {
        "analysis_type": (
            "performance_drilldown"
        ),
        "scope": {
            "level": (
                "store"
                if store is not None
                else "company"
            ),
            "store": store,
        },
        "current_period": {
            "start_date": (
                current_start.isoformat()
            ),
            "end_date": (
                current_end.isoformat()
            ),
        },
        "comparison_period": {
            "start_date": (
                comparison_start.isoformat()
            ),
            "end_date": (
                comparison_end.isoformat()
            ),
        },
        "decomposition": decomposition,
        "negative_sales_investigation": (
            negative_sales
        ),
        "branches_run": list(
            branches.keys()
        ),
        "evidence": branches,
    }
