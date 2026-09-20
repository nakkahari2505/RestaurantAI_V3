from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Final

import pandas as pd

from services.intelligence.company_performance_scanner import (
    IST,
    METRIC_ORDER,
    _direction,
    _percentage_change,
    _period_metrics,
    _prepare_sales_frame,
    _slice_period,
)
from services.intelligence.store_performance_scanner import (
    _prepare_store_mapping,
    _store_display_name,
)

COMPLETED_WEEKS_REQUIRED: Final[int] = 5


def _latest_completed_week(
    as_of_date: date,
) -> tuple[date, date]:
    current_week_monday = (
        as_of_date
        - timedelta(days=as_of_date.weekday())
    )

    latest_completed_sunday = (
        current_week_monday
        - timedelta(days=1)
    )

    latest_completed_monday = (
        latest_completed_sunday
        - timedelta(days=6)
    )

    return (
        latest_completed_monday,
        latest_completed_sunday,
    )


def _completed_week_windows(
    as_of_date: date,
    week_count: int = COMPLETED_WEEKS_REQUIRED,
) -> list[dict]:
    latest_start, latest_end = (
        _latest_completed_week(
            as_of_date
        )
    )

    windows: list[dict] = []

    for offset in reversed(
        range(week_count)
    ):
        start_date = (
            latest_start
            - timedelta(days=7 * offset)
        )

        end_date = (
            latest_end
            - timedelta(days=7 * offset)
        )

        windows.append(
            {
                "week_index": len(windows) + 1,
                "start_date": start_date,
                "end_date": end_date,
            }
        )

    return windows


def _week_metrics(
    sales: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> dict:
    week_df = _slice_period(
        sales=sales,
        start_date=start_date,
        end_date=end_date,
    )

    metrics = _period_metrics(
        period_df=week_df,
        start_date=start_date,
        end_date=end_date,
    )

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "metrics": metrics,
        "has_sales": float(metrics["sales"]) > 0,
    }


def _metric_movement(
    current_metrics: dict,
    previous_metrics: dict,
) -> dict:
    output: dict = {}

    for metric_name in METRIC_ORDER:
        current_value = float(
            current_metrics[
                metric_name
            ]
        )

        previous_value = float(
            previous_metrics[
                metric_name
            ]
        )

        output[
            metric_name
        ] = {
            "current": current_value,
            "previous": previous_value,
            "absolute_change": (
                current_value
                - previous_value
            ),
            "change_pct": _percentage_change(
                current_value,
                previous_value,
            ),
            "direction": _direction(
                current_value,
                previous_value,
            ),
        }

    return output


def _build_weekly_series(
    sales: pd.DataFrame,
    windows: list[dict],
) -> list[dict]:
    weekly: list[dict] = []

    for window in windows:
        week = _week_metrics(
            sales=sales,
            start_date=window[
                "start_date"
            ],
            end_date=window[
                "end_date"
            ],
        )

        weekly.append(
            {
                "week_index": window[
                    "week_index"
                ],
                **week,
            }
        )

    return weekly


def _attach_week_over_week(
    weekly: list[dict],
) -> list[dict]:
    output: list[dict] = []

    for index, week in enumerate(
        weekly
    ):
        record = dict(
            week
        )

        if index == 0:
            record[
                "vs_previous_week"
            ] = None
        else:
            record[
                "vs_previous_week"
            ] = _metric_movement(
                current_metrics=week[
                    "metrics"
                ],
                previous_metrics=weekly[
                    index - 1
                ][
                    "metrics"
                ],
            )

        output.append(
            record
        )

    return output


def _weekly_gap_vs_company(
    store_week: dict,
    company_week: dict,
) -> dict | None:
    store_movement = store_week.get(
        "vs_previous_week"
    )

    company_movement = company_week.get(
        "vs_previous_week"
    )

    if (
        store_movement is None
        or company_movement is None
    ):
        return None

    output: dict = {}

    for metric_name in METRIC_ORDER:
        store_change_pct = (
            store_movement[
                metric_name
            ].get(
                "change_pct"
            )
        )

        company_change_pct = (
            company_movement[
                metric_name
            ].get(
                "change_pct"
            )
        )

        gap_pct_points = None

        if (
            store_change_pct is not None
            and company_change_pct is not None
        ):
            gap_pct_points = (
                float(store_change_pct)
                - float(company_change_pct)
            )

        output[
            metric_name
        ] = {
            "store_change_pct": (
                store_change_pct
            ),
            "company_change_pct": (
                company_change_pct
            ),
            "gap_pct_points": (
                gap_pct_points
            ),
        }

    return output


def _dataset_week_coverage(
    sales: pd.DataFrame,
    windows: list[dict],
) -> dict:
    earliest = windows[0][
        "start_date"
    ]

    latest = windows[-1][
        "end_date"
    ]

    expected_dates = {
        value.date()
        for value in pd.date_range(
            start=earliest,
            end=latest,
            freq="D",
        )
    }

    available_dates = {
        value
        for value in sales[
            "Date"
        ].dropna()
        if earliest <= value <= latest
    }

    missing_dates = sorted(
        expected_dates
        - available_dates
    )

    return {
        "complete": not missing_dates,
        "start_date": earliest.isoformat(),
        "end_date": latest.isoformat(),
        "expected_days": len(expected_dates),
        "available_days": len(available_dates),
        "missing_dates": [
            value.isoformat()
            for value in missing_dates
        ],
    }


def scan_store_weekly_trends(
    data: dict,
    as_of_date: date | None = None,
) -> dict:
    """
    Produce evidence for persistent store deterioration.

    Uses the latest 5 fully completed Monday-Sunday weeks.
    Five weeks create 4 consecutive week-over-week movements.

    For the company and every store:
        Sales, Transactions, ADS, ADT, APT

    For weeks 2-5:
        week-over-week movement

    For each store/week:
        store movement vs company movement
        percentage-point gap vs company

    No anomaly judgement is made here.
    """
    sales = _prepare_sales_frame(
        data
    )

    today = (
        as_of_date
        if as_of_date is not None
        else datetime.now(
            IST
        ).date()
    )

    windows = _completed_week_windows(
        as_of_date=today,
        week_count=COMPLETED_WEEKS_REQUIRED,
    )

    coverage = _dataset_week_coverage(
        sales=sales,
        windows=windows,
    )

    company_weekly = _attach_week_over_week(
        _build_weekly_series(
            sales=sales,
            windows=windows,
        )
    )

    store_mapping = _prepare_store_mapping(
        data
    )

    restaurants = sorted(
        sales[
            "Restaurant"
        ]
        .dropna()
        .astype(str)
        .unique()
        .tolist()
    )

    stores: list[dict] = []

    for restaurant_name in restaurants:
        store_sales = sales[
            sales[
                "Restaurant"
            ].astype(str)
            == restaurant_name
        ].copy()

        store_weekly = _attach_week_over_week(
            _build_weekly_series(
                sales=store_sales,
                windows=windows,
            )
        )

        for index in range(
            len(store_weekly)
        ):
            store_weekly[
                index
            ][
                "vs_company"
            ] = _weekly_gap_vs_company(
                store_week=store_weekly[
                    index
                ],
                company_week=company_weekly[
                    index
                ],
            )

        stores.append(
            {
                "restaurant": restaurant_name,
                "store": _store_display_name(
                    restaurant_name,
                    store_mapping,
                ),
                "weeks": store_weekly,
            }
        )

    return {
        "scan_type": "store_weekly_trend",
        "as_of_date": today.isoformat(),
        "week_definition": (
            "Monday-Sunday completed weeks"
        ),
        "weeks_used": (
            COMPLETED_WEEKS_REQUIRED
        ),
        "week_over_week_movements": (
            COMPLETED_WEEKS_REQUIRED - 1
        ),
        "metric_order": list(
            METRIC_ORDER
        ),
        "dataset_coverage": coverage,
        "company": {
            "weeks": company_weekly,
        },
        "store_count": len(stores),
        "stores": stores,
    }
