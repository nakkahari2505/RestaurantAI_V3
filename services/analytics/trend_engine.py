from typing import Final

import pandas as pd

from services.analytics.grouping_engine import (
    calculate_grouped_metric,
)
from services.semantics.vocabulary.metrics import (
    METRIC_ADS,
    METRIC_ADT,
    METRIC_APT,
    METRIC_QUANTITY,
    METRIC_SALES,
    METRIC_TRANSACTIONS,
    calculate_metric,
)


# =========================================================
# SOURCE COLUMNS
# =========================================================

DATE_COLUMN: Final[str] = "Date"


# =========================================================
# SUPPORTED TREND GRAINS
# =========================================================

TREND_DAY: Final[str] = "day"
TREND_WEEK: Final[str] = "week"
TREND_MONTH: Final[str] = "month"


SUPPORTED_TREND_GRAINS: Final[set[str]] = {
    TREND_DAY,
    TREND_WEEK,
    TREND_MONTH,
}


# =========================================================
# INTERNAL TREND COLUMNS
# =========================================================

TREND_START_COLUMN: Final[str] = "__trend_start"
TREND_END_COLUMN: Final[str] = "__trend_end"
TREND_LABEL_COLUMN: Final[str] = "__trend_label"


# =========================================================
# DATE HELPERS
# =========================================================


def _prepare_dates(
    sales: pd.DataFrame,
) -> pd.DataFrame:
    """
    Parse the physical Date column safely.

    The Filter Engine has already restricted the required
    overall period before Trend Engine receives the rows.
    """
    if DATE_COLUMN not in sales.columns:
        raise ValueError(
            "Sales data does not contain Date column."
        )

    working_sales = sales.copy()

    working_sales[
        DATE_COLUMN
    ] = pd.to_datetime(
        working_sales[
            DATE_COLUMN
        ],
        errors="coerce",
        dayfirst=True,
    )

    working_sales = (
        working_sales.loc[
            working_sales[
                DATE_COLUMN
            ].notna()
        ]
        .copy()
    )

    working_sales[
        DATE_COLUMN
    ] = (
        working_sales[
            DATE_COLUMN
        ].dt.normalize()
    )

    return working_sales


# =========================================================
# DAILY GRAIN
# =========================================================


def _add_daily_trend_columns(
    sales: pd.DataFrame,
) -> pd.DataFrame:

    working_sales = sales.copy()

    working_sales[
        TREND_START_COLUMN
    ] = working_sales[
        DATE_COLUMN
    ]

    working_sales[
        TREND_END_COLUMN
    ] = working_sales[
        DATE_COLUMN
    ]

    working_sales[
        TREND_LABEL_COLUMN
    ] = (
        working_sales[
            DATE_COLUMN
        ].dt.strftime(
            "%d %b %Y"
        )
    )

    return working_sales


# =========================================================
# WEEKLY GRAIN
# =========================================================


def _add_weekly_trend_columns(
    sales: pd.DataFrame,
) -> pd.DataFrame:
    """
    RestaurantAI week definition:

        Monday -> Sunday

    This matches the existing time engine behaviour.
    """
    working_sales = sales.copy()

    weekday_number = (
        working_sales[
            DATE_COLUMN
        ].dt.weekday
    )

    working_sales[
        TREND_START_COLUMN
    ] = (
        working_sales[
            DATE_COLUMN
        ]
        - pd.to_timedelta(
            weekday_number,
            unit="D",
        )
    )

    working_sales[
        TREND_END_COLUMN
    ] = (
        working_sales[
            TREND_START_COLUMN
        ]
        + pd.Timedelta(
            days=6
        )
    )

    working_sales[
        TREND_LABEL_COLUMN
    ] = (
        working_sales[
            TREND_START_COLUMN
        ].dt.strftime(
            "%d %b"
        )
        + " to "
        + working_sales[
            TREND_END_COLUMN
        ].dt.strftime(
            "%d %b %Y"
        )
    )

    return working_sales


# =========================================================
# MONTHLY GRAIN
# =========================================================


def _add_monthly_trend_columns(
    sales: pd.DataFrame,
) -> pd.DataFrame:

    working_sales = sales.copy()

    month_period = (
        working_sales[
            DATE_COLUMN
        ].dt.to_period(
            "M"
        )
    )

    working_sales[
        TREND_START_COLUMN
    ] = (
        month_period
        .dt.start_time
        .dt.normalize()
    )

    working_sales[
        TREND_END_COLUMN
    ] = (
        month_period
        .dt.end_time
        .dt.normalize()
    )

    working_sales[
        TREND_LABEL_COLUMN
    ] = (
        working_sales[
            TREND_START_COLUMN
        ].dt.strftime(
            "%b %Y"
        )
    )

    return working_sales


# =========================================================
# TREND COLUMN PREPARATION
# =========================================================


def _prepare_trend_columns(
    sales: pd.DataFrame,
    grain: str,
) -> pd.DataFrame:

    normalized_grain = (
        str(
            grain
        )
        .strip()
        .lower()
    )

    if (
        normalized_grain
        not in SUPPORTED_TREND_GRAINS
    ):
        raise ValueError(
            "Unsupported trend grain: "
            f"{grain}"
        )

    working_sales = (
        _prepare_dates(
            sales=sales
        )
    )

    if normalized_grain == TREND_DAY:
        return _add_daily_trend_columns(
            working_sales
        )

    if normalized_grain == TREND_WEEK:
        return _add_weekly_trend_columns(
            working_sales
        )

    if normalized_grain == TREND_MONTH:
        return _add_monthly_trend_columns(
            working_sales
        )

    raise ValueError(
        "Unsupported trend grain."
    )


# =========================================================
# METRIC VALIDATION
# =========================================================


def _validate_metric(
    metric_name: str,
) -> str:

    normalized_metric = (
        str(
            metric_name
        )
        .strip()
        .lower()
    )

    if normalized_metric not in {
        METRIC_SALES,
        METRIC_QUANTITY,
        METRIC_TRANSACTIONS,
        METRIC_ADS,
        METRIC_ADT,
        METRIC_APT,
    }:
        raise ValueError(
            "Unsupported trend metric: "
            f"{metric_name}"
        )

    return normalized_metric


# =========================================================
# NON-GROUPED TREND
# =========================================================


def _calculate_plain_trend(
    working_sales: pd.DataFrame,
    metric_name: str,
) -> list[dict]:
    """
    Example:

        Daily sales trend

    returns:

        01 Aug -> Sales
        02 Aug -> Sales
        03 Aug -> Sales
    """
    result_rows: list[dict] = []

    grouped_periods = (
        working_sales.groupby(
            TREND_START_COLUMN,
            sort=True,
            dropna=False,
        )
    )

    for (
        _,
        period_df,
    ) in grouped_periods:

        first_row = (
            period_df.iloc[0]
        )

        metric_value = (
            calculate_metric(
                metric_name=metric_name,
                filtered_df=period_df,
            )
        )

        result_rows.append(
            {
                "period_start": (
                    first_row[
                        TREND_START_COLUMN
                    ].strftime(
                        "%Y-%m-%d"
                    )
                ),

                "period_end": (
                    first_row[
                        TREND_END_COLUMN
                    ].strftime(
                        "%Y-%m-%d"
                    )
                ),

                "period_label": (
                    str(
                        first_row[
                            TREND_LABEL_COLUMN
                        ]
                    )
                ),

                "metric_value": (
                    float(
                        metric_value
                    )
                ),

                "matching_rows": (
                    len(
                        period_df
                    )
                ),
            }
        )

    return result_rows


# =========================================================
# GROUPED TREND
# =========================================================


def _calculate_grouped_trend(
    working_sales: pd.DataFrame,
    data: dict,
    ral_request: dict,
) -> list[dict]:
    """
    Support combinations such as:

        Daily store-wise sales trend
        Weekly category-wise quantity
        Monthly store + channel sales

    Trend Engine owns the time bucket.

    Grouping Engine owns the business-dimension split.
    """
    result_rows: list[dict] = []

    grouped_periods = (
        working_sales.groupby(
            TREND_START_COLUMN,
            sort=True,
            dropna=False,
        )
    )

    for (
        _,
        period_df,
    ) in grouped_periods:

        first_row = (
            period_df.iloc[0]
        )

        grouped_result = (
            calculate_grouped_metric(
                filtered_sales=period_df,
                data=data,
                ral_request=ral_request,
            )
        )

        result_rows.append(
            {
                "period_start": (
                    first_row[
                        TREND_START_COLUMN
                    ].strftime(
                        "%Y-%m-%d"
                    )
                ),

                "period_end": (
                    first_row[
                        TREND_END_COLUMN
                    ].strftime(
                        "%Y-%m-%d"
                    )
                ),

                "period_label": (
                    str(
                        first_row[
                            TREND_LABEL_COLUMN
                        ]
                    )
                ),

                "grouped_result": (
                    grouped_result
                ),
            }
        )

    return result_rows


# =========================================================
# PUBLIC TREND ENGINE
# =========================================================


def calculate_trend(
    filtered_sales: pd.DataFrame,
    data: dict,
    ral_request: dict,
) -> dict:
    """
    Execute a RestaurantAI trend request.

    Supported:

        Daily
        Weekly
        Monthly

    Also supports Trend + Grouping together.

    Examples:

        Daily sales trend

        Weekly transactions trend

        Monthly quantity trend

        Daily store-wise sales trend

        Weekly category-wise quantity trend

        Monthly store-wise channel-wise sales trend
    """

    # =====================================================
    # TREND CONFIGURATION
    # =====================================================

    trend = ral_request.get(
        "trend",
        {},
    )

    if not trend.get(
        "enabled",
        False,
    ):
        raise ValueError(
            "Trend is not enabled in this RAL request."
        )

    grain = trend.get(
        "grain"
    )

    if grain is None:
        raise ValueError(
            "Trend grain is required."
        )

    normalized_grain = (
        str(
            grain
        )
        .strip()
        .lower()
    )

    if (
        normalized_grain
        not in SUPPORTED_TREND_GRAINS
    ):
        raise ValueError(
            "Unsupported trend grain: "
            f"{grain}"
        )

    # =====================================================
    # METRIC
    # =====================================================

    metric_name = (
        _validate_metric(
            ral_request.get(
                "metric",
                ""
            )
        )
    )

    # =====================================================
    # PREPARE TIME BUCKETS
    # =====================================================

    working_sales = (
        _prepare_trend_columns(
            sales=filtered_sales,
            grain=normalized_grain,
        )
    )

    # =====================================================
    # OPTIONAL BUSINESS GROUPING
    # =====================================================

    grouping = ral_request.get(
        "grouping",
        {},
    )

    grouping_enabled = (
        bool(
            grouping.get(
                "enabled",
                False,
            )
        )
    )

    if grouping_enabled:

        rows = (
            _calculate_grouped_trend(
                working_sales=working_sales,
                data=data,
                ral_request=ral_request,
            )
        )

    else:

        rows = (
            _calculate_plain_trend(
                working_sales=working_sales,
                metric_name=metric_name,
            )
        )

    # =====================================================
    # FINAL RESULT
    # =====================================================

    return {
        "metric": metric_name,

        "grain": (
            normalized_grain
        ),

        "grouping_enabled": (
            grouping_enabled
        ),

        "grouping_dimensions": (
            grouping.get(
                "dimensions",
                [],
            )
            if grouping_enabled
            else []
        ),

        "point_count": len(
            rows
        ),

        "rows": rows,
    }