from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from services.core.data_loader import load_auberry_workbook

from services.intelligence.company_performance_scanner import (
    scan_company_performance,
)
from services.intelligence.company_observer import (
    observe_company_performance,
)
from services.intelligence.store_performance_scanner import (
    scan_store_performance,
)
from services.intelligence.store_observer import (
    observe_store_performance,
)
from services.intelligence.store_trend_scanner import (
    scan_store_weekly_trends,
)
from services.intelligence.store_trend_observer import (
    observe_store_weekly_trends,
)
from services.intelligence.product_zero_sales import (
    detect_product_zero_sales,
)
from services.intelligence.performance_drilldown import (
    drilldown_performance,
)


def _priority_score(priority: str | None) -> int:
    """
    Convert existing intelligence priorities into a common
    ranking score.

    This does not redefine the underlying scanner logic.
    It only helps the orchestrator rank already-created
    observations.
    """
    priority_map = {
        "critical": 100,
        "high": 80,
        "medium": 50,
        "review": 40,
        "low": 20,
        "low_base_review": 20,
        "none": 0,
    }

    return priority_map.get(
        str(priority or "none").lower(),
        0,
    )


def _safe_list(value: Any) -> list:
    if isinstance(value, list):
        return value

    return []


def _build_completed_week_periods(
    as_of_date: date,
    weeks: int = 5,
) -> tuple[date, date]:
    """
    Store trend logic uses completed Monday-Sunday weeks.

    Example:
    If as_of_date is Wednesday 12 Aug,
    the latest completed week ended Sunday 09 Aug.
    """

    days_since_sunday = (
        as_of_date.weekday() + 1
    ) % 7

    latest_completed_sunday = (
        as_of_date
        - timedelta(days=days_since_sunday)
    )

    if latest_completed_sunday == as_of_date:
        latest_completed_sunday = (
            latest_completed_sunday
            - timedelta(days=7)
        )

    first_monday = (
        latest_completed_sunday
        - timedelta(days=(weeks * 7) - 1)
    )

    return (
        first_monday,
        latest_completed_sunday,
    )


def _build_company_summary(
    company_observation: dict,
) -> list[dict]:
    """
    Company performance is the management context, not an exception
    competing for a Top-N slot.

    Daily / MTD / YTD therefore remain visible as a dedicated section
    of the management intelligence package.
    """
    observations = (
        company_observation.get(
            "observations",
            {},
        )
    )

    output = []

    for horizon in (
        "daily",
        "mtd",
        "ytd",
    ):
        observation = observations.get(
            horizon
        )

        if not isinstance(
            observation,
            dict,
        ):
            continue

        output.append(
            {
                "horizon": horizon,
                "label": observation.get(
                    "label",
                    horizon.upper(),
                ),
                "status": observation.get(
                    "status",
                ),
                "materiality": observation.get(
                    "materiality",
                ),
                "needs_investigation": (
                    observation.get(
                        "needs_investigation",
                        False,
                    )
                ),
                "drilldown_focus": (
                    observation.get(
                        "drilldown_focus",
                    )
                ),
                "driver_pattern": (
                    observation.get(
                        "driver_pattern",
                    )
                ),
                "observation": (
                    observation.get(
                        "observation",
                        "",
                    )
                ),
                "evidence": (
                    observation.get(
                        "evidence",
                        {},
                    )
                ),
            }
        )

    return output


def _collect_store_candidates(
    store_observation: dict,
) -> list[dict]:
    """
    Store Observer exposes management-worthy peer exceptions through
    divergence_queue. Use that queue directly rather than the full
    store observation payload.
    """
    candidates = []

    divergence_queue = _safe_list(
        store_observation.get(
            "divergence_queue"
        )
    )

    for store in divergence_queue:
        priority = store.get(
            "priority",
            "none",
        )

        score = _priority_score(
            priority
        )

        if score <= 0:
            continue

        candidates.append(
            {
                "intelligence_type": (
                    "store_performance"
                ),
                "scope": "store",
                "entity": store.get(
                    "store",
                    "Unknown Store",
                ),
                "horizon": store.get(
                    "horizon",
                ),
                "priority": priority,
                "score": score,
                "observation": store.get(
                    "observation",
                    "",
                ),
                "source": store,
            }
        )

    return candidates


def _collect_store_trend_candidates(
    trend_observation: dict,
) -> list[dict]:
    candidates = []

    persistent_queue = _safe_list(
        trend_observation.get(
            "persistent_queue"
        )
    )

    for store in persistent_queue:
        priority = store.get(
            "priority",
            "medium",
        )

        # Persistence deserves a modest ranking premium because it
        # represents repeated weakness, not a one-period exception.
        score = (
            _priority_score(
                priority
            )
            + 15
        )

        candidates.append(
            {
                "intelligence_type": (
                    "store_persistent_trend"
                ),
                "scope": "store",
                "entity": store.get(
                    "store",
                    "Unknown Store",
                ),
                "priority": priority,
                "score": score,
                "observation": store.get(
                    "observation",
                    "",
                ),
                "source": store,
            }
        )

    return candidates


def _collect_product_candidates(
    product_scan: dict,
) -> list[dict]:
    """
    Product zero-sales intelligence remains available in the evidence
    package, but is currently deferred from the owner-facing selection
    until business rules are calibrated.
    """
    candidates = []

    findings = []

    for possible_key in (
        "findings",
        "alerts",
        "products",
        "anomalies",
        "results",
    ):
        possible_value = (
            product_scan.get(
                possible_key
            )
        )

        if isinstance(
            possible_value,
            list,
        ):
            findings = possible_value
            break

    for finding in findings:
        priority = finding.get(
            "priority",
            "review",
        )

        score = _priority_score(
            priority
        )

        entity_parts = [
            finding.get("store"),
            finding.get("item"),
        ]

        entity = " - ".join(
            str(part)
            for part in entity_parts
            if part
        )

        candidates.append(
            {
                "intelligence_type": (
                    "product_zero_sales"
                ),
                "scope": "product",
                "entity": (
                    entity
                    or "Product anomaly"
                ),
                "priority": priority,
                "score": score,
                "observation": finding.get(
                    "observation",
                    "",
                ),
                "source": finding,
            }
        )

    return candidates


def _deduplicate_candidates(
    candidates: list[dict],
) -> list[dict]:
    """
    Avoid saying essentially the same thing twice.

    For the first version, uniqueness is based on:
    intelligence type + entity.
    """

    best_by_key = {}

    for candidate in candidates:
        key = (
            candidate.get(
                "intelligence_type"
            ),
            candidate.get("entity"),
        )

        existing = best_by_key.get(key)

        if (
            existing is None
            or candidate.get("score", 0)
            > existing.get("score", 0)
        ):
            best_by_key[key] = candidate

    return list(best_by_key.values())


def _rank_candidates(
    candidates: list[dict],
) -> list[dict]:
    return sorted(
        candidates,
        key=lambda item: (
            item.get("score", 0),
            item.get("priority", ""),
        ),
        reverse=True,
    )


def _select_management_findings(
    ranked_candidates: list[dict],
    max_findings: int,
    include_product_zero: bool,
) -> list[dict]:
    """
    Final owner-facing exception selection.

    V1 rules:
    - Company Daily / MTD / YTD are shown separately and therefore do
      not compete for these slots.
    - Product zero-sales remains available in evidence, but is deferred
      by default until business calibration is complete.
    - Avoid allowing one intelligence family to flood the message.
    - Prefer at most one finding per store where practical.
    """
    selected = []
    used_store_entities = set()
    type_counts = {}

    type_limits = {
        "store_persistent_trend": 1,
        "store_performance": 2,
        "product_zero_sales": 1,
    }

    for candidate in ranked_candidates:
        intelligence_type = candidate.get(
            "intelligence_type"
        )

        if (
            intelligence_type
            == "product_zero_sales"
            and not include_product_zero
        ):
            continue

        current_type_count = (
            type_counts.get(
                intelligence_type,
                0,
            )
        )

        type_limit = type_limits.get(
            intelligence_type,
            max_findings,
        )

        if current_type_count >= type_limit:
            continue

        entity = candidate.get(
            "entity"
        )

        # For store-level intelligence, avoid sending two different
        # versions of essentially the same store concern in the first
        # management message.
        if (
            candidate.get("scope")
            == "store"
            and entity in used_store_entities
        ):
            continue

        selected.append(
            candidate
        )

        type_counts[
            intelligence_type
        ] = (
            current_type_count + 1
        )

        if candidate.get(
            "scope"
        ) == "store":
            used_store_entities.add(
                entity
            )

        if len(selected) >= max_findings:
            break

    return selected


def build_management_intelligence(
    as_of_date: date | None = None,
    max_findings: int = 3,
    include_product_zero: bool = False,
) -> dict:
    """
    Run the existing RestaurantAI intelligence capabilities and assemble
    the management intelligence package.

    Management structure:
        1. Company Daily / MTD / YTD context
        2. Selected management exceptions
        3. Full ranked evidence retained for debugging / future drilldown

    Product zero-sales is deliberately NOT selected for the owner-facing
    message by default until its business qualification rules are tuned.
    """

    if as_of_date is None:
        as_of_date = date.today()

    data = load_auberry_workbook()

    # These explicit week-on-week periods are retained for the next
    # performance-drilldown stage.
    current_end = (
        as_of_date
        - timedelta(days=1)
    )

    current_start = (
        current_end
        - timedelta(days=6)
    )

    comparison_end = (
        current_start
        - timedelta(days=1)
    )

    comparison_start = (
        comparison_end
        - timedelta(days=6)
    )

    trend_start, trend_end = (
        _build_completed_week_periods(
            as_of_date=as_of_date,
            weeks=5,
        )
    )

    company_scan = (
        scan_company_performance(
            data=data,
            as_of_date=as_of_date,
        )
    )

    company_observation = (
        observe_company_performance(
            company_scan
        )
    )

    company_summary = (
        _build_company_summary(
            company_observation
        )
    )

    store_scan = (
        scan_store_performance(
            data=data,
            as_of_date=as_of_date,
        )
    )

    store_observation = (
        observe_store_performance(
            store_scan
        )
    )

    trend_scan = (
        scan_store_weekly_trends(
            data=data,
            as_of_date=as_of_date,
        )
    )

    trend_observation = (
        observe_store_weekly_trends(
            trend_scan
        )
    )

    product_scan = (
        detect_product_zero_sales(
            data=data,
            as_of_date=as_of_date,
        )
    )

    candidates = []

    candidates.extend(
        _collect_store_candidates(
            store_observation
        )
    )

    candidates.extend(
        _collect_store_trend_candidates(
            trend_observation
        )
    )

    product_candidates = (
        _collect_product_candidates(
            product_scan
        )
    )

    candidates.extend(
        product_candidates
    )

    candidates = (
        _deduplicate_candidates(
            candidates
        )
    )

    ranked_candidates = (
        _rank_candidates(
            candidates
        )
    )

    selected_findings = (
        _select_management_findings(
            ranked_candidates=(
                ranked_candidates
            ),
            max_findings=max_findings,
            include_product_zero=(
                include_product_zero
            ),
        )
    )

    return {
        "intelligence_type": (
            "management_intelligence"
        ),
        "as_of_date": (
            as_of_date.isoformat()
        ),
        "performance_through": (
            company_observation.get(
                "performance_through"
            )
        ),
        "company_summary": (
            company_summary
        ),
        "analysis_period": {
            "current": {
                "start_date": (
                    current_start.isoformat()
                ),
                "end_date": (
                    current_end.isoformat()
                ),
            },
            "comparison": {
                "start_date": (
                    comparison_start.isoformat()
                ),
                "end_date": (
                    comparison_end.isoformat()
                ),
            },
            "trend_window": {
                "start_date": (
                    trend_start.isoformat()
                ),
                "end_date": (
                    trend_end.isoformat()
                ),
            },
        },
        "candidate_count": len(
            ranked_candidates
        ),
        "selected_count": len(
            selected_findings
        ),
        "selected_findings": (
            selected_findings
        ),
        "product_zero_candidate_count": (
            len(product_candidates)
        ),
        "product_zero_in_management_selection": (
            include_product_zero
        ),
        "all_ranked_candidates": (
            ranked_candidates
        ),
        "component_status": {
            "company_performance": (
                "completed"
            ),
            "store_performance": (
                "completed"
            ),
            "store_weekly_trend": (
                "completed"
            ),
            "product_zero_sales": (
                "completed_deferred_from_management_selection"
                if not include_product_zero
                else "completed_included"
            ),
            "performance_drilldown": (
                "available_for_selected_negative_findings"
            ),
        },
    }


# =========================================================
# MANAGEMENT MESSAGE
# =========================================================


def _display_date(
    iso_date: str | None,
) -> str:
    """
    Convert YYYY-MM-DD to a compact management-message date.
    """
    if not iso_date:
        return ""

    try:
        parsed = date.fromisoformat(
            iso_date
        )
    except ValueError:
        return str(
            iso_date
        )

    return parsed.strftime(
        "%d %b %Y"
    )


def format_management_message(
    intelligence: dict,
) -> str:
    """
    Convert structured management intelligence into WhatsApp-ready text.

    Important design rule:
    The business sentences are NOT recreated or hard-coded here.
    Company and exception narratives come directly from the observer
    outputs selected by the orchestrator.

    This function is presentation only.
    """

    if not isinstance(
        intelligence,
        dict,
    ):
        raise ValueError(
            "intelligence must be a dictionary."
        )

    company_summary = _safe_list(
        intelligence.get(
            "company_summary"
        )
    )

    selected_findings = _safe_list(
        intelligence.get(
            "selected_findings"
        )
    )

    performance_through = (
        intelligence.get(
            "performance_through"
        )
        or intelligence.get(
            "analysis_period",
            {},
        ).get(
            "current",
            {},
        ).get(
            "end_date"
        )
    )

    lines = [
        "*RestaurantAI – Management Intelligence*",
    ]

    display_date = _display_date(
        performance_through
    )

    if display_date:
        lines.append(
            f"_Performance through {display_date}_"
        )

    lines.extend(
        [
            "",
            "*Company Performance*",
        ]
    )

    company_lines_added = 0

    for company_item in company_summary:
        observation = str(
            company_item.get(
                "observation",
                "",
            )
        ).strip()

        if not observation:
            continue

        lines.append(
            f"• {observation}"
        )

        company_lines_added += 1

    if company_lines_added == 0:
        lines.append(
            "• No company-level observation is available."
        )

    lines.extend(
        [
            "",
            "*Management Attention*",
        ]
    )

    if selected_findings:
        for index, finding in enumerate(
            selected_findings,
            start=1,
        ):
            observation = str(
                finding.get(
                    "observation",
                    "",
                )
            ).strip()

            entity = str(
                finding.get(
                    "entity",
                    "",
                )
            ).strip()

            if observation:
                lines.append(
                    f"{index}. {observation}"
                )
            elif entity:
                lines.append(
                    f"{index}. {entity}"
                )
    else:
        lines.append(
            "No material management exceptions were selected."
        )

    lines.extend(
        [
            "",
            "_Automatically identified from the latest available sales data._",
        ]
    )

    return "\n".join(
        lines
    )


def build_management_message(
    as_of_date: date | None = None,
    max_findings: int = 3,
    include_product_zero: bool = False,
) -> str:
    """
    One-call entry point for the eventual WhatsApp intelligence message.

    Pipeline:
        scanners
        -> observers
        -> orchestrator
        -> final management selection
        -> WhatsApp-ready text
    """

    intelligence = (
        build_management_intelligence(
            as_of_date=as_of_date,
            max_findings=max_findings,
            include_product_zero=(
                include_product_zero
            ),
        )
    )

    return format_management_message(
        intelligence
    )

