from __future__ import annotations

from typing import Final


# =========================================================
# PERSISTENCE OBSERVER CONFIGURATION
# =========================================================

# Weekly movement smaller than 3% is treated as broadly stable.
STABLE_THRESHOLD_PCT: Final[float] = 3.0

# Store must underperform company by at least 5 percentage points
# for that week to count as meaningful company-relative weakness.
COMPANY_GAP_THRESHOLD_PCT_POINTS: Final[float] = 5.0

# Severe rule: all 4 week-over-week movements are meaningful declines.
SEVERE_REQUIRED_DECLINES: Final[int] = 4

# Persistent rule: at least 3 of the last 4 movements are declines.
PERSISTENT_MIN_DECLINES: Final[int] = 3

# Persistent rule also requires the latest 2 weekly movements to be down.
PERSISTENT_LATEST_CONSECUTIVE_DECLINES: Final[int] = 2

# Latest weekly sales level must be at least 8% below the first week's
# sales level before we call the pattern persistent deterioration.
NET_EROSION_THRESHOLD_PCT: Final[float] = 8.0

# For store-specific persistent weakness, at least 2 of the 4 movements
# should materially underperform the company trend.
MIN_WEEKS_UNDERPERFORMING_COMPANY: Final[int] = 2


def _safe_float(value):
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_text(value):
    if value is None:
        return "not comparable"

    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def _effective_direction(change_pct):
    if change_pct is None:
        return "not_comparable"

    if abs(change_pct) < STABLE_THRESHOLD_PCT:
        return "stable"

    return "up" if change_pct > 0 else "down"


def _extract_four_movements(weeks):
    movements = []

    for week in weeks:
        movement = week.get("vs_previous_week")

        if movement is None:
            continue

        vs_company = week.get("vs_company")

        sales_change = _safe_float(
            movement["sales"].get("change_pct")
        )
        adt_change = _safe_float(
            movement["adt"].get("change_pct")
        )
        apt_change = _safe_float(
            movement["apt"].get("change_pct")
        )

        company_sales_change = None
        sales_gap_pp = None

        if vs_company:
            company_sales_change = _safe_float(
                vs_company["sales"].get(
                    "company_change_pct"
                )
            )
            sales_gap_pp = _safe_float(
                vs_company["sales"].get(
                    "gap_pct_points"
                )
            )

        movements.append(
            {
                "week_index": week.get("week_index"),
                "start_date": week.get("start_date"),
                "end_date": week.get("end_date"),
                "sales_change_pct": sales_change,
                "sales_direction": _effective_direction(
                    sales_change
                ),
                "company_sales_change_pct": (
                    company_sales_change
                ),
                "company_sales_direction": (
                    _effective_direction(
                        company_sales_change
                    )
                ),
                "sales_gap_pct_points": sales_gap_pp,
                "adt_change_pct": adt_change,
                "adt_direction": _effective_direction(
                    adt_change
                ),
                "apt_change_pct": apt_change,
                "apt_direction": _effective_direction(
                    apt_change
                ),
            }
        )

    return movements


def _net_sales_erosion_pct(weeks):
    if len(weeks) < 2:
        return None

    first_sales = _safe_float(
        weeks[0].get(
            "metrics",
            {},
        ).get(
            "sales"
        )
    )

    latest_sales = _safe_float(
        weeks[-1].get(
            "metrics",
            {},
        ).get(
            "sales"
        )
    )

    if (
        first_sales is None
        or latest_sales is None
        or first_sales == 0
    ):
        return None

    return (
        (latest_sales - first_sales)
        / abs(first_sales)
    ) * 100.0


def _persistent_driver(movements):
    adt_down_weeks = sum(
        1
        for movement in movements
        if movement["adt_direction"] == "down"
    )

    apt_down_weeks = sum(
        1
        for movement in movements
        if movement["apt_direction"] == "down"
    )

    if (
        adt_down_weeks >= 3
        and apt_down_weeks >= 3
    ):
        primary_driver = "both"

    elif adt_down_weeks >= 3:
        primary_driver = "transactions"

    elif apt_down_weeks >= 3:
        primary_driver = "apt"

    else:
        primary_driver = "mixed"

    return {
        "primary_driver": primary_driver,
        "adt_down_weeks": adt_down_weeks,
        "apt_down_weeks": apt_down_weeks,
    }


def _observe_store_persistence(
    store_name,
    weeks,
):
    movements = _extract_four_movements(
        weeks
    )

    if len(movements) != 4:
        return {
            "store": store_name,
            "status": "insufficient_history",
            "severity": "insufficient_history",
            "persistent_decline": False,
            "severe_continuous_decline": False,
            "store_specific": False,
            "priority": "none",
            "driver": None,
            "observation": (
                f"{store_name} does not yet have four complete "
                f"week-over-week movements for persistence analysis."
            ),
            "movements": movements,
        }

    decline_count = sum(
        1
        for movement in movements
        if movement["sales_direction"] == "down"
    )

    severe_continuous_decline = (
        decline_count
        == SEVERE_REQUIRED_DECLINES
    )

    latest_two_declining = all(
        movement["sales_direction"] == "down"
        for movement in movements[
            -PERSISTENT_LATEST_CONSECUTIVE_DECLINES:
        ]
    )

    net_erosion_pct = _net_sales_erosion_pct(
        weeks
    )

    materially_lower_than_start = (
        net_erosion_pct is not None
        and net_erosion_pct
        <= -NET_EROSION_THRESHOLD_PCT
    )

    persistent_decline = (
        severe_continuous_decline
        or (
            decline_count
            >= PERSISTENT_MIN_DECLINES
            and latest_two_declining
            and materially_lower_than_start
        )
    )

    underperform_company_count = sum(
        1
        for movement in movements
        if (
            movement["sales_gap_pct_points"] is not None
            and movement["sales_gap_pct_points"]
            <= -COMPANY_GAP_THRESHOLD_PCT_POINTS
        )
    )

    company_decline_count = sum(
        1
        for movement in movements
        if movement["company_sales_direction"] == "down"
    )

    store_specific = (
        persistent_decline
        and underperform_company_count
        >= MIN_WEEKS_UNDERPERFORMING_COMPANY
    )

    company_wide_context = (
        persistent_decline
        and company_decline_count >= 3
        and not store_specific
    )

    driver = _persistent_driver(
        movements
    )

    if severe_continuous_decline:
        severity = "severe_continuous_decline"
    elif persistent_decline:
        severity = "persistent_decline"
    else:
        severity = "no_persistent_decline"

    if store_specific:
        priority = (
            "high"
            if severe_continuous_decline
            else "medium"
        )
        status = "persistent_store_specific_decline"

        if driver["primary_driver"] == "transactions":
            driver_text = (
                f"Lower daily transactions recur in "
                f"{driver['adt_down_weeks']} of the 4 weekly "
                f"movements, making transaction volume the "
                f"main recurring area to investigate."
            )

        elif driver["primary_driver"] == "apt":
            driver_text = (
                f"Lower APT recurs in "
                f"{driver['apt_down_weeks']} of the 4 weekly "
                f"movements, making ticket value the main "
                f"recurring area to investigate."
            )

        elif driver["primary_driver"] == "both":
            driver_text = (
                "Both daily transactions and APT weaken in "
                "at least 3 of the 4 weekly movements."
            )

        else:
            driver_text = (
                "The recurring weakness is mixed between "
                "transaction volume and APT."
            )

        if severe_continuous_decline:
            pattern_text = (
                "declined in all 4 consecutive weekly movements"
            )
        else:
            pattern_text = (
                f"declined in {decline_count} of the last 4 "
                f"weekly movements, including the latest 2"
            )

        observation = (
            f"{store_name} has {pattern_text} and is "
            f"{_pct_text(net_erosion_pct)} versus the first week "
            f"of this 5-week window. It underperformed the company "
            f"trend in {underperform_company_count} of the 4 "
            f"movements. {driver_text}"
        )

    elif company_wide_context:
        priority = "medium"
        status = "persistent_company_wide_decline"

        observation = (
            f"{store_name} shows persistent weekly weakness and is "
            f"{_pct_text(net_erosion_pct)} versus the first week, "
            f"but the company also declined in "
            f"{company_decline_count} of the 4 movements. "
            f"This currently looks more like broader business "
            f"weakness than an isolated store problem."
        )

    elif persistent_decline:
        priority = "medium"
        status = (
            "persistent_decline_not_clearly_store_specific"
        )

        observation = (
            f"{store_name} shows persistent weekly weakness and is "
            f"{_pct_text(net_erosion_pct)} versus the first week, "
            f"but it has not materially underperformed the company "
            f"in enough weeks to call the issue store-specific yet."
        )

    else:
        priority = "none"
        status = "no_persistent_decline"

        observation = (
            f"{store_name} does not currently show a persistent "
            f"deterioration pattern."
        )

    return {
        "store": store_name,
        "status": status,
        "severity": severity,
        "persistent_decline": persistent_decline,
        "severe_continuous_decline": (
            severe_continuous_decline
        ),
        "store_specific": store_specific,
        "priority": priority,
        "decline_count": decline_count,
        "latest_two_declining": (
            latest_two_declining
        ),
        "net_sales_erosion_pct": (
            net_erosion_pct
        ),
        "company_decline_count": (
            company_decline_count
        ),
        "underperform_company_count": (
            underperform_company_count
        ),
        "driver": driver,
        "observation": observation,
        "movements": movements,
    }


def observe_store_weekly_trends(
    trend_scan,
):
    if not isinstance(
        trend_scan,
        dict,
    ):
        raise ValueError(
            "trend_scan must be a dictionary."
        )

    coverage = trend_scan.get(
        "dataset_coverage",
        {},
    )

    if not coverage.get(
        "complete",
        False,
    ):
        return {
            "observation_type": (
                "store_weekly_persistence"
            ),
            "status": "dataset_incomplete",
            "dataset_coverage": coverage,
            "persistent_queue": [],
            "stores": [],
        }

    stores = trend_scan.get(
        "stores",
        [],
    )

    observations = []
    persistent_queue = []

    for store_record in stores:
        store_name = str(
            store_record.get("store")
            or store_record.get("restaurant")
        )

        observation = _observe_store_persistence(
            store_name=store_name,
            weeks=store_record.get(
                "weeks",
                [],
            ),
        )

        observations.append(
            observation
        )

        if observation[
            "persistent_decline"
        ]:
            persistent_queue.append(
                {
                    "store": store_name,
                    "status": observation[
                        "status"
                    ],
                    "severity": observation[
                        "severity"
                    ],
                    "priority": observation[
                        "priority"
                    ],
                    "store_specific": (
                        observation[
                            "store_specific"
                        ]
                    ),
                    "decline_count": (
                        observation[
                            "decline_count"
                        ]
                    ),
                    "latest_two_declining": (
                        observation[
                            "latest_two_declining"
                        ]
                    ),
                    "net_sales_erosion_pct": (
                        observation[
                            "net_sales_erosion_pct"
                        ]
                    ),
                    "driver": observation[
                        "driver"
                    ],
                    "observation": (
                        observation[
                            "observation"
                        ]
                    ),
                }
            )

    priority_rank = {
        "high": 0,
        "medium": 1,
        "none": 2,
    }

    persistent_queue.sort(
        key=lambda item: (
            priority_rank.get(
                item["priority"],
                99,
            ),
            item[
                "net_sales_erosion_pct"
            ]
            if item[
                "net_sales_erosion_pct"
            ] is not None
            else 0.0,
        )
    )

    return {
        "observation_type": (
            "store_weekly_persistence"
        ),
        "status": "complete",
        "as_of_date": trend_scan.get(
            "as_of_date"
        ),
        "thresholds": {
            "stable_below_abs_pct": (
                STABLE_THRESHOLD_PCT
            ),
            "company_gap_pct_points": (
                COMPANY_GAP_THRESHOLD_PCT_POINTS
            ),
            "severe_required_declines": (
                SEVERE_REQUIRED_DECLINES
            ),
            "persistent_min_declines": (
                PERSISTENT_MIN_DECLINES
            ),
            "latest_consecutive_declines_required": (
                PERSISTENT_LATEST_CONSECUTIVE_DECLINES
            ),
            "net_erosion_threshold_pct": (
                NET_EROSION_THRESHOLD_PCT
            ),
            "min_weeks_underperforming_company": (
                MIN_WEEKS_UNDERPERFORMING_COMPANY
            ),
        },
        "dataset_coverage": coverage,
        "persistent_count": len(
            persistent_queue
        ),
        "persistent_queue": (
            persistent_queue
        ),
        "stores": observations,
    }
