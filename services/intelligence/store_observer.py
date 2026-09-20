from __future__ import annotations

from typing import Final


# =========================================================
# STORE OBSERVER CONFIGURATION
# =========================================================

# A store must differ from the company sales movement by at least
# this many percentage points before it becomes a divergence candidate.
DIVERGENCE_THRESHOLD_PCT_POINTS: Final[float] = 10.0

# This is NOT an exclusion rule.
# It only marks very small store-period bases so spectacular percentages
# can be treated cautiously rather than promoted automatically.
LOW_BASE_COMPANY_SHARE_PCT: Final[float] = 2.0

# Same materiality convention already used in Company Observer.
STABLE_THRESHOLD_PCT: Final[float] = 3.0

HORIZON_LABELS: Final[dict[str, str]] = {
    "daily": "Daily",
    "mtd": "MTD",
    "ytd": "YTD",
}


# =========================================================
# BASIC HELPERS
# =========================================================


def _safe_float(
    value,
) -> float | None:
    if value is None:
        return None

    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _pct_text(
    value: float | None,
) -> str:
    if value is None:
        return "not comparable"

    sign = "+" if value > 0 else ""

    return f"{sign}{value:.1f}%"


def _pp_text(
    value: float | None,
) -> str:
    if value is None:
        return "not comparable"

    sign = "+" if value > 0 else ""

    return f"{sign}{value:.1f} pp"


def _effective_direction(
    change_pct: float | None,
) -> str:
    if change_pct is None:
        return "not_comparable"

    if abs(change_pct) < STABLE_THRESHOLD_PCT:
        return "stable"

    return "up" if change_pct > 0 else "down"


def _period_sales_share_pct(
    store_period: dict,
    company_period: dict,
    side: str,
) -> float | None:
    """
    side must be 'current' or 'comparison'.

    Returns the store's share of company sales for that period.
    This helps distinguish a strategically meaningful store movement
    from a huge percentage generated on a tiny base.
    """
    store_raw = (
        store_period
        .get("raw_metrics", {})
        .get(side, {})
    )

    company_raw = (
        company_period
        .get("raw_metrics", {})
        .get(side, {})
    )

    store_sales = _safe_float(
        store_raw.get("sales")
    )

    company_sales = _safe_float(
        company_raw.get("sales")
    )

    if (
        store_sales is None
        or company_sales is None
        or company_sales == 0
    ):
        return None

    return (
        store_sales
        / company_sales
    ) * 100.0


# =========================================================
# ADS DRIVER INTERPRETATION
# =========================================================


def _driver_pattern(
    adt_change_pct: float | None,
    apt_change_pct: float | None,
) -> dict:
    """
    Store-level interpretation of:

        ADS = ADT x APT

    This mirrors the analytical skeleton already frozen for
    RestaurantAI.
    """
    adt_direction = _effective_direction(
        adt_change_pct
    )
    apt_direction = _effective_direction(
        apt_change_pct
    )

    if (
        adt_direction == "not_comparable"
        or apt_direction == "not_comparable"
    ):
        return {
            "pattern": "not_comparable",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": None,
        }

    if (
        adt_direction == "stable"
        and apt_direction == "stable"
    ):
        return {
            "pattern": "both_stable",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": "stable",
        }

    if (
        adt_direction == "up"
        and apt_direction == "up"
    ):
        return {
            "pattern": "adt_up_apt_up",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": "both",
        }

    if (
        adt_direction == "down"
        and apt_direction == "down"
    ):
        return {
            "pattern": "adt_down_apt_down",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": "both",
        }

    if (
        adt_direction == "up"
        and apt_direction == "down"
    ):
        return {
            "pattern": "adt_up_apt_down",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": (
                "transactions"
                if abs(adt_change_pct or 0.0)
                >= abs(apt_change_pct or 0.0)
                else "apt"
            ),
        }

    if (
        adt_direction == "down"
        and apt_direction == "up"
    ):
        return {
            "pattern": "adt_down_apt_up",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": (
                "transactions"
                if abs(adt_change_pct or 0.0)
                >= abs(apt_change_pct or 0.0)
                else "apt"
            ),
        }

    if (
        adt_direction == "up"
        and apt_direction == "stable"
    ):
        return {
            "pattern": "adt_up_apt_stable",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": "transactions",
        }

    if (
        adt_direction == "down"
        and apt_direction == "stable"
    ):
        return {
            "pattern": "adt_down_apt_stable",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": "transactions",
        }

    if (
        adt_direction == "stable"
        and apt_direction == "up"
    ):
        return {
            "pattern": "adt_stable_apt_up",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": "apt",
        }

    if (
        adt_direction == "stable"
        and apt_direction == "down"
    ):
        return {
            "pattern": "adt_stable_apt_down",
            "adt_direction": adt_direction,
            "apt_direction": apt_direction,
            "primary_driver": "apt",
        }

    return {
        "pattern": "mixed",
        "adt_direction": adt_direction,
        "apt_direction": apt_direction,
        "primary_driver": None,
    }


# =========================================================
# NARRATIVE HELPERS
# =========================================================


def _driver_sentence(
    store_sales_change: float,
    adt_change: float | None,
    apt_change: float | None,
    driver: dict,
) -> str:
    pattern = driver["pattern"]

    if pattern == "adt_down_apt_down":
        return (
            f"Both daily transactions ({_pct_text(adt_change)}) "
            f"and APT ({_pct_text(apt_change)}) weakened."
        )

    if pattern == "adt_down_apt_up":
        return (
            f"The weakness is transaction-led: daily transactions "
            f"fell {_pct_text(adt_change)}, despite APT improving "
            f"{_pct_text(apt_change)}."
        )

    if pattern == "adt_up_apt_down":
        if store_sales_change < 0:
            return (
                f"Sales declined despite higher daily transactions "
                f"({_pct_text(adt_change)}), because lower APT "
                f"({_pct_text(apt_change)}) outweighed the volume gain."
            )

        return (
            f"Higher daily transactions ({_pct_text(adt_change)}) "
            f"more than offset lower APT ({_pct_text(apt_change)})."
        )

    if pattern == "adt_down_apt_stable":
        return (
            f"The movement is mainly transaction-led, with daily "
            f"transactions at {_pct_text(adt_change)} while APT "
            f"remained broadly stable."
        )

    if pattern == "adt_stable_apt_down":
        return (
            f"The movement is mainly APT-led, with APT at "
            f"{_pct_text(apt_change)} while daily transactions "
            f"remained broadly stable."
        )

    if pattern == "adt_up_apt_stable":
        return (
            f"The movement is mainly supported by higher daily "
            f"transactions ({_pct_text(adt_change)}), while APT "
            f"remained broadly stable."
        )

    if pattern == "adt_stable_apt_up":
        return (
            f"The movement is mainly supported by higher APT "
            f"({_pct_text(apt_change)}), while daily transactions "
            f"remained broadly stable."
        )

    if pattern == "adt_up_apt_up":
        return (
            f"Both daily transactions ({_pct_text(adt_change)}) "
            f"and APT ({_pct_text(apt_change)}) improved."
        )

    return (
        f"Daily transactions moved {_pct_text(adt_change)} and "
        f"APT moved {_pct_text(apt_change)}."
    )


# =========================================================
# ONE STORE / ONE HORIZON
# =========================================================


def _observe_store_horizon(
    store_name: str,
    horizon_name: str,
    store_period: dict,
    company_period: dict,
) -> dict:
    label = HORIZON_LABELS[
        horizon_name
    ]

    if not store_period.get(
        "comparison_valid",
        False,
    ):
        return {
            "horizon": horizon_name,
            "label": label,
            "status": "not_comparable",
            "is_divergence_candidate": False,
            "priority": "none",
            "low_base_context": False,
            "observation": (
                f"{store_name} {label} comparison is not reliable "
                f"because one or both store periods are incomplete."
            ),
            "evidence": {},
        }

    vs_company = store_period.get(
        "vs_company"
    )

    metrics = store_period.get(
        "metrics"
    )

    if not vs_company or not metrics:
        return {
            "horizon": horizon_name,
            "label": label,
            "status": "not_comparable",
            "is_divergence_candidate": False,
            "priority": "none",
            "low_base_context": False,
            "observation": (
                f"{store_name} {label} comparison evidence "
                f"is unavailable."
            ),
            "evidence": {},
        }

    sales_change = _safe_float(
        metrics["sales"].get(
            "change_pct"
        )
    )

    adt_change = _safe_float(
        metrics["adt"].get(
            "change_pct"
        )
    )

    apt_change = _safe_float(
        metrics["apt"].get(
            "change_pct"
        )
    )

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

    current_share_pct = _period_sales_share_pct(
        store_period=store_period,
        company_period=company_period,
        side="current",
    )

    comparison_share_pct = _period_sales_share_pct(
        store_period=store_period,
        company_period=company_period,
        side="comparison",
    )

    max_share_pct = max(
        [
            value
            for value in (
                current_share_pct,
                comparison_share_pct,
            )
            if value is not None
        ],
        default=None,
    )

    low_base_context = (
        max_share_pct is not None
        and max_share_pct
        < LOW_BASE_COMPANY_SHARE_PCT
    )

    store_direction = _effective_direction(
        sales_change
    )

    company_direction = _effective_direction(
        company_sales_change
    )

    opposite_to_company = (
        store_direction
        in {"up", "down"}
        and company_direction
        in {"up", "down"}
        and store_direction
        != company_direction
    )

    divergence_candidate = (
        sales_gap_pp is not None
        and abs(sales_gap_pp)
        >= DIVERGENCE_THRESHOLD_PCT_POINTS
    )

    # Priority is intentionally conservative.
    # A store moving opposite to company gets highest attention,
    # especially when it is not on a tiny base.
    if (
        divergence_candidate
        and opposite_to_company
        and not low_base_context
    ):
        priority = "high"

    elif (
        divergence_candidate
        and not low_base_context
    ):
        priority = "medium"

    elif divergence_candidate:
        priority = "low_base_review"

    else:
        priority = "none"

    driver = _driver_pattern(
        adt_change_pct=adt_change,
        apt_change_pct=apt_change,
    )

    if not divergence_candidate:
        observation = (
            f"{store_name} is broadly aligned with the company "
            f"{label} sales trend."
        )

    else:
        opening = (
            f"{store_name} {label} sales moved "
            f"{_pct_text(sales_change)} versus company movement of "
            f"{_pct_text(company_sales_change)}, a divergence of "
            f"{_pp_text(sales_gap_pp)}."
        )

        driver_text = _driver_sentence(
            store_sales_change=(
                sales_change or 0.0
            ),
            adt_change=adt_change,
            apt_change=apt_change,
            driver=driver,
        )

        if low_base_context:
            observation = (
                f"{opening} {driver_text} "
                f"The percentage movement is on a relatively small "
                f"store sales base, so it should be interpreted "
                f"with caution."
            )
        else:
            observation = (
                f"{opening} {driver_text}"
            )

    return {
        "horizon": horizon_name,
        "label": label,
        "status": (
            "divergent"
            if divergence_candidate
            else "aligned"
        ),
        "is_divergence_candidate": (
            divergence_candidate
        ),
        "opposite_to_company": (
            opposite_to_company
        ),
        "priority": priority,
        "low_base_context": (
            low_base_context
        ),
        "driver_pattern": driver,
        "observation": observation,
        "evidence": {
            "store_sales_change_pct": (
                sales_change
            ),
            "company_sales_change_pct": (
                company_sales_change
            ),
            "sales_gap_pct_points": (
                sales_gap_pp
            ),
            "adt_change_pct": (
                adt_change
            ),
            "apt_change_pct": (
                apt_change
            ),
            "current_company_sales_share_pct": (
                current_share_pct
            ),
            "comparison_company_sales_share_pct": (
                comparison_share_pct
            ),
        },
    }


# =========================================================
# PUBLIC STORE OBSERVER
# =========================================================


def observe_store_performance(
    store_scan: dict,
) -> dict:
    """
    Convert Store Performance Scanner evidence into deterministic
    peer-divergence observations.

    First objective:
        Identify stores moving materially differently from the
        company trend.

    Important:
        A spectacular percentage on a tiny store base is NOT
        discarded. It is marked as low-base context and receives
        lower priority so management is not misled.

    This observer intentionally does NOT yet:
        - evaluate four-week persistence,
        - investigate channels/categories/items,
        - run product zero-sales checks,
        - call GPT,
        - decide WhatsApp delivery.
    """
    if not isinstance(
        store_scan,
        dict,
    ):
        raise ValueError(
            "store_scan must be a dictionary."
        )

    stores = store_scan.get(
        "stores",
        []
    )

    company_reference = store_scan.get(
        "company_reference",
        {}
    )

    observations: list[dict] = []
    divergence_queue: list[dict] = []

    for store_record in stores:
        store_name = str(
            store_record.get(
                "store"
            )
            or store_record.get(
                "restaurant"
            )
        )

        horizon_observations = {}

        for horizon_name in (
            "daily",
            "mtd",
            "ytd",
        ):
            observation = (
                _observe_store_horizon(
                    store_name=store_name,
                    horizon_name=horizon_name,
                    store_period=store_record[
                        horizon_name
                    ],
                    company_period=company_reference[
                        horizon_name
                    ],
                )
            )

            horizon_observations[
                horizon_name
            ] = observation

            if observation[
                "is_divergence_candidate"
            ]:
                divergence_queue.append(
                    {
                        "store": store_name,
                        "horizon": horizon_name,
                        "priority": observation[
                            "priority"
                        ],
                        "opposite_to_company": (
                            observation[
                                "opposite_to_company"
                            ]
                        ),
                        "low_base_context": (
                            observation[
                                "low_base_context"
                            ]
                        ),
                        "sales_gap_pct_points": (
                            observation[
                                "evidence"
                            ][
                                "sales_gap_pct_points"
                            ]
                        ),
                        "observation": (
                            observation[
                                "observation"
                            ]
                        ),
                    }
                )

        observations.append(
            {
                "store": store_name,
                "restaurant": (
                    store_record.get(
                        "restaurant"
                    )
                ),
                "observations": (
                    horizon_observations
                ),
            }
        )

    priority_rank = {
        "high": 0,
        "medium": 1,
        "low_base_review": 2,
        "none": 3,
    }

    divergence_queue.sort(
        key=lambda item: (
            priority_rank.get(
                item["priority"],
                99,
            ),
            -abs(
                item[
                    "sales_gap_pct_points"
                ]
                or 0.0
            ),
        )
    )

    return {
        "observation_type": (
            "store_peer_divergence"
        ),
        "as_of_date": store_scan.get(
            "as_of_date"
        ),
        "performance_through": (
            store_scan.get(
                "performance_through"
            )
        ),
        "thresholds": {
            "divergence_abs_pct_points": (
                DIVERGENCE_THRESHOLD_PCT_POINTS
            ),
            "low_base_company_share_pct": (
                LOW_BASE_COMPANY_SHARE_PCT
            ),
        },
        "store_count": len(
            observations
        ),
        "divergence_count": len(
            divergence_queue
        ),
        "divergence_queue": (
            divergence_queue
        ),
        "stores": observations,
    }
