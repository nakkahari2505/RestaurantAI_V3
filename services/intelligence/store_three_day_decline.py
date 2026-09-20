from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Final

import pandas as pd

from services.reports.yesterday.morning_report import IST, _prepare_sales_frame


# Three days remains the minimum threshold for raising the alert.
# The reported streak itself can be longer than three days.
MIN_DECLINE_DAYS: Final[int] = 3


def detect_three_day_store_declines(
    data: dict,
    as_of_date: date | None = None,
) -> dict:
    """Find stores currently down vs the same weekdays last week.

    RestaurantAI evaluates each store backwards from yesterday. A day extends
    the current decline streak only when:

    1. the store has positive sales on the current date,
    2. the store had positive sales on the same weekday seven days earlier,
       and
    3. current sales are lower than that comparison day's sales.

    The scan stops immediately when any one of those conditions fails. This
    means the alert represents a *current consecutive comparable-day streak
    ending yesterday*, not merely three negative observations found somewhere
    in the recent period.

    Three days is only the minimum alert threshold. If a store has been down
    for 4, 5, 6... consecutive comparable days, the complete streak is
    returned and reported.
    """
    sales = _prepare_sales_frame(data)

    today = (
        as_of_date
        if as_of_date is not None
        else datetime.now(IST).date()
    )
    performance_through = today - timedelta(days=1)

    daily = (
        sales.groupby(["Store", "Date"], as_index=False)["Sub Total"]
        .sum()
        .rename(columns={"Sub Total": "Sales"})
    )

    lookup = {
        (str(row["Store"]).strip(), row["Date"]): float(row["Sales"])
        for _, row in daily.iterrows()
    }

    stores = sorted(
        {
            str(value).strip()
            for value in sales["Store"].dropna()
            if str(value).strip()
        }
    )

    findings: list[dict] = []

    for store in stores:
        comparisons_reversed: list[dict] = []
        current_date = performance_through

        while True:
            comparison_date = current_date - timedelta(days=7)

            current_sales = lookup.get((store, current_date), 0.0)
            comparison_sales = lookup.get((store, comparison_date), 0.0)

            # A missing/closed day breaks the current comparable-day streak.
            if current_sales <= 0 or comparison_sales <= 0:
                break

            change_pct = (
                (current_sales - comparison_sales)
                / comparison_sales
            ) * 100.0

            # The first non-decline breaks the streak. Therefore a store that
            # recovered yesterday disappears from the alert immediately.
            if change_pct >= 0:
                break

            comparisons_reversed.append(
                {
                    "date": current_date.isoformat(),
                    "comparison_date": comparison_date.isoformat(),
                    "sales": current_sales,
                    "comparison_sales": comparison_sales,
                    "change_pct": change_pct,
                }
            )

            current_date -= timedelta(days=1)

        if len(comparisons_reversed) < MIN_DECLINE_DAYS:
            continue

        comparisons = list(reversed(comparisons_reversed))

        findings.append(
            {
                "store": store,
                "decline_days": len(comparisons),
                "streak_start": comparisons[0]["date"],
                "streak_end": comparisons[-1]["date"],
                "comparisons": comparisons,
            }
        )

    # Longest current decline streak first. This makes the most persistent
    # store issue appear first in the management alert.
    findings.sort(
        key=lambda item: (
            -int(item["decline_days"]),
            item["store"].casefold(),
        )
    )

    return {
        "performance_through": performance_through.isoformat(),
        "minimum_decline_days": MIN_DECLINE_DAYS,
        "findings": findings,
        "count": len(findings),
    }
