from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from typing import Final
from zoneinfo import ZoneInfo

import pandas as pd

from services.semantics.vocabulary.metrics import (
    calculate_apt,
    calculate_sales,
    calculate_transactions,
)


IST: Final[ZoneInfo] = ZoneInfo("Asia/Kolkata")
FINANCIAL_YEAR_START_MONTH: Final[int] = 4

METRIC_ORDER: Final[tuple[str, ...]] = (
    "sales",
    "transactions",
    "ads",
    "adt",
    "apt",
)


# =========================================================
# DATE HELPERS
# =========================================================


def _previous_month_same_elapsed_period(
    end_date: date,
) -> tuple[date, date]:
    current_month_start = end_date.replace(day=1)
    previous_month_end = current_month_start - timedelta(days=1)

    comparison_day = min(
        end_date.day,
        calendar.monthrange(
            previous_month_end.year,
            previous_month_end.month,
        )[1],
    )

    return (
        previous_month_end.replace(day=1),
        previous_month_end.replace(day=comparison_day),
    )


def _financial_year_start(
    value: date,
) -> date:
    financial_year = (
        value.year
        if value.month >= FINANCIAL_YEAR_START_MONTH
        else value.year - 1
    )

    return date(
        financial_year,
        FINANCIAL_YEAR_START_MONTH,
        1,
    )


def _safe_previous_year_date(
    value: date,
) -> date:
    """
    Move a date back one year safely.

    This matters only for 29 February.
    """
    try:
        return value.replace(
            year=value.year - 1
        )
    except ValueError:
        return value.replace(
            year=value.year - 1,
            day=28,
        )


def _number_of_days(
    start_date: date,
    end_date: date,
) -> int:
    return (
        end_date - start_date
    ).days + 1


# =========================================================
# SALES FRAME
# =========================================================


def _prepare_sales_frame(
    data: dict,
) -> pd.DataFrame:
    if not isinstance(data, dict):
        raise ValueError(
            "Workbook data must be a dictionary."
        )

    if "sales" not in data:
        raise ValueError(
            "Workbook data does not contain the sales sheet."
        )

    sales = data["sales"].copy()

    required_columns = {
        "Date",
        "Restaurant",
        "Invoice No",
        "Sub Total",
    }

    missing_columns = (
        required_columns
        - set(sales.columns)
    )

    if missing_columns:
        raise ValueError(
            "Sales data is missing required columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    sales["Date"] = pd.to_datetime(
        sales["Date"],
        errors="coerce",
        dayfirst=True,
    ).dt.date

    sales = sales[
        sales["Date"].notna()
    ].copy()

    return sales


# =========================================================
# METRIC HELPERS
# =========================================================


def _percentage_change(
    current_value: float,
    comparison_value: float,
) -> float | None:
    current = float(current_value)
    comparison = float(comparison_value)

    if comparison == 0:
        if current == 0:
            return 0.0
        return None

    return (
        (current - comparison)
        / abs(comparison)
    ) * 100.0


def _direction(
    current_value: float,
    comparison_value: float,
) -> str:
    difference = (
        float(current_value)
        - float(comparison_value)
    )

    if abs(difference) < 1e-9:
        return "flat"

    return (
        "up"
        if difference > 0
        else "down"
    )


def _slice_period(
    sales: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    return sales[
        sales["Date"].between(
            start_date,
            end_date,
            inclusive="both",
        )
    ].copy()


def _period_completeness(
    period_df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> dict:
    expected_dates = {
        value.date()
        for value in pd.date_range(
            start=start_date,
            end=end_date,
            freq="D",
        )
    }

    available_dates = {
        value
        for value in period_df["Date"].dropna()
    }

    missing_dates = sorted(
        expected_dates
        - available_dates
    )

    return {
        "complete": not missing_dates,
        "expected_days": len(expected_dates),
        "available_days": len(available_dates),
        "missing_dates": [
            value.isoformat()
            for value in missing_dates
        ],
    }


def _period_metrics(
    period_df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> dict[str, float]:
    """
    Company KPIs for one requested calendar period.

    ADS and ADT deliberately use the full requested number of
    calendar days, not merely dates that happen to exist in the
    sales file. Missing dates are separately exposed through the
    completeness evidence so RestaurantAI never hides stale data.
    """
    number_of_days = _number_of_days(
        start_date,
        end_date,
    )

    sales = float(
        calculate_sales(
            period_df
        )
    )

    transactions = float(
        calculate_transactions(
            period_df
        )
    )

    apt = float(
        calculate_apt(
            period_df
        )
    )

    ads = (
        sales / number_of_days
        if number_of_days > 0
        else 0.0
    )

    adt = (
        transactions / number_of_days
        if number_of_days > 0
        else 0.0
    )

    return {
        "sales": sales,
        "transactions": transactions,
        "ads": ads,
        "adt": adt,
        "apt": apt,
    }


def _metric_comparison(
    current_metrics: dict[str, float],
    comparison_metrics: dict[str, float],
) -> dict:
    output: dict = {}

    for metric_name in METRIC_ORDER:
        current_value = float(
            current_metrics[metric_name]
        )
        comparison_value = float(
            comparison_metrics[metric_name]
        )

        output[metric_name] = {
            "current": current_value,
            "comparison": comparison_value,
            "absolute_change": (
                current_value
                - comparison_value
            ),
            "change_pct": _percentage_change(
                current_value,
                comparison_value,
            ),
            "direction": _direction(
                current_value,
                comparison_value,
            ),
        }

    return output


# =========================================================
# PERIOD SCAN
# =========================================================


def _scan_period(
    sales: pd.DataFrame,
    current_start: date,
    current_end: date,
    comparison_start: date,
    comparison_end: date,
) -> dict:
    current_df = _slice_period(
        sales=sales,
        start_date=current_start,
        end_date=current_end,
    )

    comparison_df = _slice_period(
        sales=sales,
        start_date=comparison_start,
        end_date=comparison_end,
    )

    current_completeness = (
        _period_completeness(
            period_df=current_df,
            start_date=current_start,
            end_date=current_end,
        )
    )

    comparison_completeness = (
        _period_completeness(
            period_df=comparison_df,
            start_date=comparison_start,
            end_date=comparison_end,
        )
    )

    current_metrics = _period_metrics(
        period_df=current_df,
        start_date=current_start,
        end_date=current_end,
    )

    comparison_metrics = _period_metrics(
        period_df=comparison_df,
        start_date=comparison_start,
        end_date=comparison_end,
    )

    comparison_valid = (
        current_completeness["complete"]
        and comparison_completeness["complete"]
    )

    return {
        "current_period": {
            "start_date": current_start.isoformat(),
            "end_date": current_end.isoformat(),
            "completeness": current_completeness,
        },
        "comparison_period": {
            "start_date": comparison_start.isoformat(),
            "end_date": comparison_end.isoformat(),
            "completeness": comparison_completeness,
        },
        "comparison_valid": comparison_valid,
        "metrics": (
            _metric_comparison(
                current_metrics=current_metrics,
                comparison_metrics=comparison_metrics,
            )
            if comparison_valid
            else None
        ),
        "raw_metrics": {
            "current": current_metrics,
            "comparison": comparison_metrics,
        },
    }


# =========================================================
# PUBLIC COMPANY SCANNER
# =========================================================


def scan_company_performance(
    data: dict,
    as_of_date: date | None = None,
) -> dict:
    """
    Run RestaurantAI's first company-level daily intelligence scan.

    The scan date means "today". Performance is evaluated through
    yesterday so that only completed business days are compared.

    Horizons:
    - DAILY: yesterday vs same weekday one week earlier.
    - MTD: 1st through yesterday vs same elapsed period last month.
    - YTD: Indian financial-year start through yesterday vs the
      equivalent elapsed financial-year period one year earlier.

    This layer produces evidence only. It intentionally contains no
    anomaly thresholds, GPT narration, store drill-down or WhatsApp
    delivery logic yet.
    """
    sales = _prepare_sales_frame(
        data
    )

    today = (
        as_of_date
        if as_of_date is not None
        else datetime.now(IST).date()
    )

    yesterday = today - timedelta(days=1)

    daily_current_start = yesterday
    daily_current_end = yesterday
    daily_comparison_start = (
        yesterday - timedelta(days=7)
    )
    daily_comparison_end = (
        yesterday - timedelta(days=7)
    )

    mtd_current_start = yesterday.replace(
        day=1
    )
    mtd_current_end = yesterday
    (
        mtd_comparison_start,
        mtd_comparison_end,
    ) = _previous_month_same_elapsed_period(
        yesterday
    )

    ytd_current_start = _financial_year_start(
        yesterday
    )
    ytd_current_end = yesterday
    ytd_comparison_start = (
        ytd_current_start.replace(
            year=ytd_current_start.year - 1
        )
    )
    ytd_comparison_end = _safe_previous_year_date(
        yesterday
    )

    return {
        "scan_type": "company_performance",
        "as_of_date": today.isoformat(),
        "performance_through": yesterday.isoformat(),
        "financial_year_start_month": (
            FINANCIAL_YEAR_START_MONTH
        ),
        "metric_order": list(
            METRIC_ORDER
        ),
        "daily": _scan_period(
            sales=sales,
            current_start=daily_current_start,
            current_end=daily_current_end,
            comparison_start=daily_comparison_start,
            comparison_end=daily_comparison_end,
        ),
        "mtd": _scan_period(
            sales=sales,
            current_start=mtd_current_start,
            current_end=mtd_current_end,
            comparison_start=mtd_comparison_start,
            comparison_end=mtd_comparison_end,
        ),
        "ytd": _scan_period(
            sales=sales,
            current_start=ytd_current_start,
            current_end=ytd_current_end,
            comparison_start=ytd_comparison_start,
            comparison_end=ytd_comparison_end,
        ),
    }
