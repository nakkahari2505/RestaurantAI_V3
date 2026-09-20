from __future__ import annotations

from typing import Final


# =========================================================
# MATERIALITY CONFIGURATION
# =========================================================

STABLE_THRESHOLD_PCT: Final[float] = 3.0
STRONG_THRESHOLD_PCT: Final[float] = 10.0

HORIZON_LABELS: Final[dict[str, str]] = {
    "daily": "Daily",
    "mtd": "MTD",
    "ytd": "YTD",
}


# =========================================================
# BASIC HELPERS
# =========================================================


def _safe_pct(
    metric: dict | None,
) -> float | None:
    if not metric:
        return None

    value = metric.get(
        "change_pct"
    )

    if value is None:
        return None

    return float(
        value
    )


def _pct_text(
    value: float | None,
) -> str:
    if value is None:
        return "not comparable"

    sign = (
        "+"
        if value > 0
        else ""
    )

    return (
        f"{sign}{value:.1f}%"
    )


def _movement_bucket(
    change_pct: float | None,
) -> str:
    """
    Classify the materiality of one percentage movement.

    < 3% absolute change  -> stable
    3% to < 10%          -> meaningful
    >= 10%               -> strong
    """
    if change_pct is None:
        return "not_comparable"

    magnitude = abs(
        change_pct
    )

    if magnitude < STABLE_THRESHOLD_PCT:
        return "stable"

    if magnitude < STRONG_THRESHOLD_PCT:
        return "meaningful"

    return "strong"


def _effective_direction(
    change_pct: float | None,
) -> str:
    """
    Treat movements below the materiality threshold as stable.

    This prevents RestaurantAI from narrating tiny fluctuations
    such as +0.4% or -0.8% as meaningful business movement.
    """
    if change_pct is None:
        return "not_comparable"

    if abs(change_pct) < STABLE_THRESHOLD_PCT:
        return "stable"

    return (
        "up"
        if change_pct > 0
        else "down"
    )


# =========================================================
# ADS DRIVER INTERPRETATION
# =========================================================


def _driver_pattern(
    adt_change_pct: float | None,
    apt_change_pct: float | None,
) -> dict:
    """
    Interpret the two components of ADS:

        ADS = ADT x APT

    ADT = Average Daily Transactions
    APT = Average Per Transaction

    The returned pattern is deterministic evidence used by the
    company observer. No GPT reasoning is involved here.
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
# DETERMINISTIC NARRATIVE
# =========================================================


def _stable_observation(
    horizon_label: str,
    sales_change_pct: float,
    ads_change_pct: float,
) -> str:
    return (
        f"{horizon_label} company performance is broadly stable. "
        f"Sales moved {_pct_text(sales_change_pct)} and "
        f"ADS moved {_pct_text(ads_change_pct)} versus the "
        f"comparable period."
    )


def _positive_observation(
    horizon_label: str,
    sales_change_pct: float,
    ads_change_pct: float,
    adt_change_pct: float,
    apt_change_pct: float,
    pattern: str,
) -> str:
    opening = (
        f"{horizon_label} company sales are up "
        f"{_pct_text(sales_change_pct)}. "
        f"ADS is {_pct_text(ads_change_pct)}"
    )

    if pattern == "adt_up_apt_up":
        return (
            f"{opening}, supported by both higher daily "
            f"transactions ({_pct_text(adt_change_pct)}) and "
            f"higher APT ({_pct_text(apt_change_pct)})."
        )

    if pattern == "adt_up_apt_down":
        return (
            f"{opening}, driven by higher daily transactions "
            f"({_pct_text(adt_change_pct)}), which more than "
            f"offset lower APT ({_pct_text(apt_change_pct)})."
        )

    if pattern == "adt_down_apt_up":
        return (
            f"{opening}, driven by higher APT "
            f"({_pct_text(apt_change_pct)}), which more than "
            f"offset lower daily transactions "
            f"({_pct_text(adt_change_pct)})."
        )

    if pattern == "adt_up_apt_stable":
        return (
            f"{opening}, mainly driven by higher daily "
            f"transactions ({_pct_text(adt_change_pct)}), "
            f"while APT remained broadly stable."
        )

    if pattern == "adt_stable_apt_up":
        return (
            f"{opening}, mainly driven by higher APT "
            f"({_pct_text(apt_change_pct)}), while daily "
            f"transactions remained broadly stable."
        )

    if pattern == "adt_down_apt_down":
        return (
            f"{opening}. Despite the positive topline movement, "
            f"both daily transactions ({_pct_text(adt_change_pct)}) "
            f"and APT ({_pct_text(apt_change_pct)}) are weaker; "
            f"this combination should be reviewed before drawing "
            f"a conclusion."
        )

    return (
        f"{opening}. Daily transactions moved "
        f"{_pct_text(adt_change_pct)} and APT moved "
        f"{_pct_text(apt_change_pct)}."
    )


def _negative_observation(
    horizon_label: str,
    sales_change_pct: float,
    ads_change_pct: float,
    adt_change_pct: float,
    apt_change_pct: float,
    pattern: str,
) -> tuple[str, str]:
    """
    Returns:
        observation text,
        suggested next drill-down focus
    """
    opening = (
        f"{horizon_label} company sales are down "
        f"{_pct_text(sales_change_pct)}. "
        f"ADS is {_pct_text(ads_change_pct)}"
    )

    if pattern == "adt_down_apt_down":
        return (
            (
                f"{opening}, with weakness in both daily "
                f"transactions ({_pct_text(adt_change_pct)}) and "
                f"APT ({_pct_text(apt_change_pct)})."
            ),
            "both",
        )

    if pattern == "adt_down_apt_up":
        return (
            (
                f"{opening}, primarily due to lower daily "
                f"transactions ({_pct_text(adt_change_pct)}), "
                f"despite stronger APT "
                f"({_pct_text(apt_change_pct)})."
            ),
            "transactions",
        )

    if pattern == "adt_up_apt_down":
        return (
            (
                f"{opening}, despite higher daily transactions "
                f"({_pct_text(adt_change_pct)}). The decline is "
                f"being driven by lower APT "
                f"({_pct_text(apt_change_pct)})."
            ),
            "apt",
        )

    if pattern == "adt_down_apt_stable":
        return (
            (
                f"{opening}, driven mainly by lower daily "
                f"transactions ({_pct_text(adt_change_pct)}), "
                f"while APT remained broadly stable."
            ),
            "transactions",
        )

    if pattern == "adt_stable_apt_down":
        return (
            (
                f"{opening}, driven mainly by lower APT "
                f"({_pct_text(apt_change_pct)}), while daily "
                f"transactions remained broadly stable."
            ),
            "apt",
        )

    if pattern == "adt_up_apt_up":
        return (
            (
                f"{opening}. Both daily transactions "
                f"({_pct_text(adt_change_pct)}) and APT "
                f"({_pct_text(apt_change_pct)}) are stronger, "
                f"so the movement requires a period/data "
                f"comparability check before deeper diagnosis."
            ),
            "comparability_check",
        )

    return (
        (
            f"{opening}. Daily transactions moved "
            f"{_pct_text(adt_change_pct)} and APT moved "
            f"{_pct_text(apt_change_pct)}."
        ),
        "mixed",
    )


# =========================================================
# ONE HORIZON OBSERVER
# =========================================================


def _observe_horizon(
    horizon_name: str,
    horizon_scan: dict,
) -> dict:
    horizon_label = HORIZON_LABELS[
        horizon_name
    ]

    if not horizon_scan.get(
        "comparison_valid",
        False,
    ):
        return {
            "horizon": horizon_name,
            "label": horizon_label,
            "status": "not_comparable",
            "materiality": "not_comparable",
            "needs_investigation": False,
            "drilldown_focus": None,
            "observation": (
                f"{horizon_label} comparison is not reliable "
                f"because one or both periods have incomplete "
                f"sales data."
            ),
            "evidence": {
                "current_period": horizon_scan.get(
                    "current_period"
                ),
                "comparison_period": horizon_scan.get(
                    "comparison_period"
                ),
            },
        }

    metrics = horizon_scan.get(
        "metrics"
    )

    if not metrics:
        return {
            "horizon": horizon_name,
            "label": horizon_label,
            "status": "not_comparable",
            "materiality": "not_comparable",
            "needs_investigation": False,
            "drilldown_focus": None,
            "observation": (
                f"{horizon_label} comparison metrics are "
                f"not available."
            ),
            "evidence": {},
        }

    sales_change_pct = _safe_pct(
        metrics.get("sales")
    )
    transactions_change_pct = _safe_pct(
        metrics.get("transactions")
    )
    ads_change_pct = _safe_pct(
        metrics.get("ads")
    )
    adt_change_pct = _safe_pct(
        metrics.get("adt")
    )
    apt_change_pct = _safe_pct(
        metrics.get("apt")
    )

    sales_direction = _effective_direction(
        sales_change_pct
    )
    materiality = _movement_bucket(
        sales_change_pct
    )

    driver = _driver_pattern(
        adt_change_pct=adt_change_pct,
        apt_change_pct=apt_change_pct,
    )

    needs_investigation = False
    drilldown_focus = None

    if sales_direction == "stable":
        observation = _stable_observation(
            horizon_label=horizon_label,
            sales_change_pct=sales_change_pct or 0.0,
            ads_change_pct=ads_change_pct or 0.0,
        )
        status = "stable"

    elif sales_direction == "up":
        observation = _positive_observation(
            horizon_label=horizon_label,
            sales_change_pct=sales_change_pct or 0.0,
            ads_change_pct=ads_change_pct or 0.0,
            adt_change_pct=adt_change_pct or 0.0,
            apt_change_pct=apt_change_pct or 0.0,
            pattern=driver["pattern"],
        )
        status = "positive"

    elif sales_direction == "down":
        (
            observation,
            drilldown_focus,
        ) = _negative_observation(
            horizon_label=horizon_label,
            sales_change_pct=sales_change_pct or 0.0,
            ads_change_pct=ads_change_pct or 0.0,
            adt_change_pct=adt_change_pct or 0.0,
            apt_change_pct=apt_change_pct or 0.0,
            pattern=driver["pattern"],
        )
        status = "negative"

        needs_investigation = (
            materiality
            in {
                "meaningful",
                "strong",
            }
        )

    else:
        observation = (
            f"{horizon_label} company performance cannot be "
            f"reliably interpreted because the comparison "
            f"percentage is unavailable."
        )
        status = "not_comparable"

    return {
        "horizon": horizon_name,
        "label": horizon_label,
        "status": status,
        "materiality": materiality,
        "needs_investigation": needs_investigation,
        "drilldown_focus": drilldown_focus,
        "driver_pattern": driver,
        "observation": observation,
        "evidence": {
            "sales_change_pct": sales_change_pct,
            "transactions_change_pct": (
                transactions_change_pct
            ),
            "ads_change_pct": ads_change_pct,
            "adt_change_pct": adt_change_pct,
            "apt_change_pct": apt_change_pct,
            "current_period": horizon_scan.get(
                "current_period"
            ),
            "comparison_period": horizon_scan.get(
                "comparison_period"
            ),
        },
    }


# =========================================================
# PUBLIC COMPANY OBSERVER
# =========================================================


def observe_company_performance(
    company_scan: dict,
) -> dict:
    """
    Convert Company Performance Scanner evidence into the first
    deterministic RestaurantAI business observations.

    Input:
        Output of scan_company_performance(...)

    Output:
        Daily / MTD / YTD observations with:
        - materiality
        - positive / negative / stable status
        - ADS decomposition through ADT and APT
        - investigation flag for meaningful negative movement
        - suggested next drill-down focus

    This layer intentionally does NOT:
        - call GPT,
        - analyse stores,
        - analyse channels/categories/items,
        - send WhatsApp messages,
        - decide alert/push frequency.
    """
    if not isinstance(
        company_scan,
        dict,
    ):
        raise ValueError(
            "company_scan must be a dictionary."
        )

    required_horizons = {
        "daily",
        "mtd",
        "ytd",
    }

    missing_horizons = (
        required_horizons
        - set(company_scan)
    )

    if missing_horizons:
        raise ValueError(
            "Company scan is missing required horizons: "
            + ", ".join(
                sorted(
                    missing_horizons
                )
            )
        )

    observations = {
        horizon_name: _observe_horizon(
            horizon_name=horizon_name,
            horizon_scan=company_scan[
                horizon_name
            ],
        )
        for horizon_name in (
            "daily",
            "mtd",
            "ytd",
        )
    }

    investigation_queue = [
        {
            "horizon": horizon_name,
            "materiality": observation[
                "materiality"
            ],
            "drilldown_focus": observation[
                "drilldown_focus"
            ],
            "observation": observation[
                "observation"
            ],
        }
        for (
            horizon_name,
            observation,
        ) in observations.items()
        if observation[
            "needs_investigation"
        ]
    ]

    return {
        "observation_type": (
            "company_performance_observation"
        ),
        "as_of_date": company_scan.get(
            "as_of_date"
        ),
        "performance_through": (
            company_scan.get(
                "performance_through"
            )
        ),
        "thresholds": {
            "stable_below_abs_pct": (
                STABLE_THRESHOLD_PCT
            ),
            "strong_from_abs_pct": (
                STRONG_THRESHOLD_PCT
            ),
        },
        "observations": observations,
        "investigation_queue": (
            investigation_queue
        ),
    }
