from __future__ import annotations

from datetime import date

import pandas as pd

from services.intelligence.company_performance_scanner import (
    METRIC_ORDER,
    _prepare_sales_frame,
    scan_company_performance,
    _scan_period,
)


# =========================================================
# STORE HELPERS
# =========================================================


def _prepare_store_mapping(
    data: dict,
) -> dict[str, str]:
    """
    Build Restaurant -> Store short-name mapping.

    If store_info or the expected mapping columns are unavailable,
    the scanner will simply fall back to Restaurant name.
    """
    if "store_info" not in data:
        return {}

    store_info = data["store_info"].copy()

    required_columns = {
        "Restaurant",
        "Store",
    }

    if not required_columns.issubset(
        set(store_info.columns)
    ):
        return {}

    mapping_df = (
        store_info[
            ["Restaurant", "Store"]
        ]
        .dropna()
        .drop_duplicates(
            subset=["Restaurant"]
        )
    )

    return dict(
        zip(
            mapping_df["Restaurant"],
            mapping_df["Store"],
        )
    )


def _store_display_name(
    restaurant_name: str,
    store_mapping: dict[str, str],
) -> str:
    return str(
        store_mapping.get(
            restaurant_name,
            restaurant_name,
        )
    )


# =========================================================
# STORE PERIOD SCAN
# =========================================================


def _scan_store_period(
    store_sales: pd.DataFrame,
    company_period: dict,
) -> dict:
    """
    Scan one store using exactly the same period boundaries
    already established by the company scanner.
    """
    current_period = company_period[
        "current_period"
    ]

    comparison_period = company_period[
        "comparison_period"
    ]

    current_start = date.fromisoformat(
        current_period["start_date"]
    )

    current_end = date.fromisoformat(
        current_period["end_date"]
    )

    comparison_start = date.fromisoformat(
        comparison_period["start_date"]
    )

    comparison_end = date.fromisoformat(
        comparison_period["end_date"]
    )

    return _scan_period(
        sales=store_sales,
        current_start=current_start,
        current_end=current_end,
        comparison_start=comparison_start,
        comparison_end=comparison_end,
    )


# =========================================================
# COMPANY MOVEMENT
# =========================================================


def _company_change_pct(
    company_period: dict,
    metric_name: str,
) -> float | None:
    metrics = company_period.get(
        "metrics"
    )

    if not metrics:
        return None

    metric = metrics.get(
        metric_name
    )

    if not metric:
        return None

    return metric.get(
        "change_pct"
    )


# =========================================================
# STORE VS COMPANY
# =========================================================


def _store_vs_company(
    store_period: dict,
    company_period: dict,
) -> dict | None:
    """
    Compare the store's KPI movement with the overall
    company KPI movement.

    This is evidence only.

    We are deliberately NOT deciding here whether a store
    is anomalous. Thresholds and business interpretation
    belong to the observer layer.
    """
    if not store_period.get(
        "comparison_valid"
    ):
        return None

    if not company_period.get(
        "comparison_valid"
    ):
        return None

    store_metrics = store_period.get(
        "metrics"
    )

    company_metrics = company_period.get(
        "metrics"
    )

    if not store_metrics or not company_metrics:
        return None

    output: dict = {}

    for metric_name in METRIC_ORDER:
        store_change_pct = (
            store_metrics[
                metric_name
            ].get(
                "change_pct"
            )
        )

        company_change_pct = (
            company_metrics[
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

        output[metric_name] = {
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


# =========================================================
# PUBLIC STORE PERFORMANCE SCANNER
# =========================================================


def scan_store_performance(
    data: dict,
    as_of_date: date | None = None,
) -> dict:
    """
    Scan every store across Daily, MTD and YTD.

    Design principle:

        Company movement establishes the business trend.

        Each store is then evaluated using the exact same
        periods and KPI definitions.

        Finally, the store's percentage movement is compared
        against the company's percentage movement.

    This scanner intentionally produces evidence only.

    It does NOT yet decide:
    - which store is anomalous,
    - which store needs investigation,
    - whether divergence is material,
    - why the store moved,
    - what should be pushed to WhatsApp.

    Those decisions belong to the Store Observer layer.
    """

    sales = _prepare_sales_frame(
        data
    )

    company_scan = (
        scan_company_performance(
            data=data,
            as_of_date=as_of_date,
        )
    )

    store_mapping = (
        _prepare_store_mapping(
            data
        )
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
            sales["Restaurant"].astype(str)
            == restaurant_name
        ].copy()

        daily = _scan_store_period(
            store_sales=store_sales,
            company_period=company_scan[
                "daily"
            ],
        )

        mtd = _scan_store_period(
            store_sales=store_sales,
            company_period=company_scan[
                "mtd"
            ],
        )

        ytd = _scan_store_period(
            store_sales=store_sales,
            company_period=company_scan[
                "ytd"
            ],
        )

        daily[
            "vs_company"
        ] = _store_vs_company(
            store_period=daily,
            company_period=company_scan[
                "daily"
            ],
        )

        mtd[
            "vs_company"
        ] = _store_vs_company(
            store_period=mtd,
            company_period=company_scan[
                "mtd"
            ],
        )

        ytd[
            "vs_company"
        ] = _store_vs_company(
            store_period=ytd,
            company_period=company_scan[
                "ytd"
            ],
        )

        stores.append(
            {
                "restaurant": (
                    restaurant_name
                ),
                "store": (
                    _store_display_name(
                        restaurant_name,
                        store_mapping,
                    )
                ),
                "daily": daily,
                "mtd": mtd,
                "ytd": ytd,
            }
        )

    return {
        "scan_type": (
            "store_performance"
        ),
        "as_of_date": (
            company_scan[
                "as_of_date"
            ]
        ),
        "performance_through": (
            company_scan[
                "performance_through"
            ]
        ),
        "metric_order": list(
            METRIC_ORDER
        ),
        "company_reference": {
            "daily": (
                company_scan[
                    "daily"
                ]
            ),
            "mtd": (
                company_scan[
                    "mtd"
                ]
            ),
            "ytd": (
                company_scan[
                    "ytd"
                ]
            ),
        },
        "store_count": len(
            stores
        ),
        "stores": stores,
    }