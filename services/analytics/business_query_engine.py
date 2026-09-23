from copy import deepcopy
from datetime import date, timedelta

import pandas as pd

from services.analytics.filter_engine import apply_ral_filters
from services.analytics.grouping_engine import calculate_grouped_metric
from services.semantics.vocabulary.metrics import calculate_metric


def _compatible_ral(query: dict, metric: str, start_date: str, end_date: str) -> dict:
    return {
        "ral_version": "2.0",
        "intent": "sales",
        "metric": metric,
        "time": {
            "type": "date_range",
            "start_date": start_date,
            "end_date": end_date,
        },
        "stores": list(query.get("stores", [])),
        "regions": [],
        "channels": list(query.get("channels", [])),
        "aggregators": [],
        "categories": [],
        "items": [],
        "grouping": {
            "enabled": bool(query.get("group_by")),
            "dimensions": list(query.get("group_by", [])),
        },
        "trend": {"enabled": False, "grain": None},
        "comparison": {
            "enabled": False,
            "from_start_date": None,
            "from_end_date": None,
            "to_start_date": None,
            "to_end_date": None,
        },
        "presentation": {"type": "text"},
        "understood_request": query.get("understood_request", "Business query"),
        "needs_clarification": False,
        "clarification_question": None,
    }


def _latest_data_date(data: dict) -> date | None:
    sales = data.get("sales")
    if sales is None or sales.empty or "Date" not in sales.columns:
        return None
    values = pd.to_datetime(sales["Date"], errors="coerce", dayfirst=True).dropna()
    if values.empty:
        return None
    return values.max().date()


def _effective_period(query: dict, data: dict) -> tuple[str, str]:
    time_value = query.get("time", {})
    start_text = time_value.get("start_date")
    end_text = time_value.get("end_date")
    if not start_text or not end_text:
        raise ValueError("I need a clear time period to run that analysis.")

    start = date.fromisoformat(start_text)
    end = date.fromisoformat(end_text)
    latest = _latest_data_date(data)

    if (
        latest is not None
        and time_value.get("type") in {"today", "this_week", "this_month", "this_quarter", "ytd"}
        and latest < end
        and latest >= start
    ):
        end = latest

    return start.isoformat(), end.isoformat()


def _comparison_period(start_text: str, end_text: str, comparison: str) -> tuple[str, str] | None:
    if comparison == "none":
        return None

    start = date.fromisoformat(start_text)
    end = date.fromisoformat(end_text)

    if comparison == "same_period_last_year":
        def shift(d: date) -> date:
            try:
                return d.replace(year=d.year - 1)
            except ValueError:
                return d.replace(year=d.year - 1, day=28)
        return shift(start).isoformat(), shift(end).isoformat()

    if comparison == "previous_period":
        span = (end - start).days + 1
        previous_end = start - timedelta(days=1)
        previous_start = previous_end - timedelta(days=span - 1)
        return previous_start.isoformat(), previous_end.isoformat()

    return None


def _resolved_comparison_period(
    query: dict,
    start_text: str,
    end_text: str,
) -> tuple[str, str] | None:
    """Prefer the semantic planner's explicit fair reference dates."""
    detail = query.get("comparison_detail", {}) or {}
    reference = detail.get("reference_period", {}) or {}
    ref_start = reference.get("start_date")
    ref_end = reference.get("end_date")
    if ref_start and ref_end:
        # If live data ends before the planner's calendar end date,
        # shorten the reference period to the same elapsed-day count.
        planned_end = (query.get("time", {}) or {}).get("end_date")
        if planned_end and str(planned_end) != str(end_text):
            effective_start = date.fromisoformat(start_text)
            effective_end = date.fromisoformat(end_text)
            elapsed_days = (effective_end - effective_start).days + 1

            reference_start = date.fromisoformat(str(ref_start))
            aligned_reference_end = (
                reference_start + timedelta(days=elapsed_days - 1)
            )
            original_reference_end = date.fromisoformat(str(ref_end))
            if aligned_reference_end < original_reference_end:
                ref_end = aligned_reference_end.isoformat()

        return str(ref_start), str(ref_end)

    return _comparison_period(
        start_text,
        end_text,
        query.get("comparison", "none"),
    )


def _condition_matches(value: float | None, operator: str, target: float) -> bool:
    if value is None:
        return False
    operators = {
        "lt": lambda a, b: a < b,
        "lte": lambda a, b: a <= b,
        "gt": lambda a, b: a > b,
        "gte": lambda a, b: a >= b,
        "eq": lambda a, b: a == b,
        "ne": lambda a, b: a != b,
    }
    fn = operators.get(str(operator).lower())
    if fn is None:
        raise ValueError(f"Unsupported condition operator: {operator}")
    return bool(fn(float(value), float(target)))


def _execute_filter(
    data: dict,
    query: dict,
    start_text: str,
    end_text: str,
) -> dict:
    dimensions = list(query.get("group_by", []))
    if not dimensions:
        raise ValueError("A filter query needs a grouping dimension such as store or channel.")

    comparison_period = _resolved_comparison_period(query, start_text, end_text)
    if comparison_period is None:
        raise ValueError("This filter needs a comparison period.")

    current_rows = _calculate_grouped_bundle(data, query, start_text, end_text)
    previous_rows = _calculate_grouped_bundle(
        data, query, comparison_period[0], comparison_period[1]
    )

    def key_for(row: dict) -> tuple:
        groups = row.get("groups", {})
        return tuple(groups.get(dim, "") for dim in dimensions)

    previous_by_key = {key_for(row): row for row in previous_rows}
    conditions = (query.get("conditions", {}) or {}).get("items", [])
    logic = str((query.get("conditions", {}) or {}).get("logic", "and")).lower()
    output_rows = []

    for current_row in current_rows:
        previous_row = previous_by_key.get(key_for(current_row))
        if previous_row is None:
            continue

        current_metrics = current_row.get("metrics", {})
        previous_metrics = previous_row.get("metrics", {})
        growth = {
            metric: _growth(current_metrics.get(metric, 0), previous_metrics.get(metric, 0))
            for metric in query.get("metrics", [])
        }

        checks = []
        for condition in conditions:
            metric = condition.get("metric")
            measure = condition.get("measure", "growth_pct")
            if measure == "growth_pct":
                observed = growth.get(metric)
            elif measure == "value":
                observed = current_metrics.get(metric)
            else:
                raise ValueError(f"Unsupported condition measure: {measure}")
            checks.append(
                _condition_matches(
                    observed,
                    condition.get("operator", "eq"),
                    condition.get("value", 0),
                )
            )

        matched = (all(checks) if logic != "or" else any(checks)) if checks else True
        if matched:
            output_rows.append({
                "groups": deepcopy(current_row.get("groups", {})),
                "metrics": deepcopy(current_metrics),
                "comparison_metrics": deepcopy(previous_metrics),
                "growth_pct": growth,
            })

    primary_metric = query.get("metrics", [None])[0]
    output_rows.sort(
        key=lambda row: (
            row.get("growth_pct", {}).get(primary_metric) is None,
            row.get("growth_pct", {}).get(primary_metric) or 0,
        )
    )

    return {
        "status": "ok",
        "result_type": "filtered",
        "period": {"start_date": start_text, "end_date": end_text},
        "comparison": {
            "type": query.get("comparison", "none"),
            "period": {
                "start_date": comparison_period[0],
                "end_date": comparison_period[1],
            },
        },
        "metrics": list(query.get("metrics", [])),
        "group_by": dimensions,
        "rows": output_rows,
    }



def _execute_rank(
    data: dict,
    query: dict,
    start_text: str,
    end_text: str,
) -> dict:
    dimensions = list(query.get("group_by", []))
    if not dimensions:
        raise ValueError("A rank query needs a grouping dimension such as store or channel.")

    selection = query.get("selection", {}) or {}
    primary_metric = query.get("metrics", [None])[0]
    if not primary_metric:
        raise ValueError("A rank query needs a metric.")

    sort_measure = str(selection.get("sort_measure", "value")).lower()
    direction = str(
        selection.get("direction")
        or selection.get("sort_direction")
        or "desc"
    ).lower()
    limit = (
        selection.get("limit")
        or selection.get("top_n")
        or selection.get("count")
        or 5
    )
    try:
        limit = max(1, int(limit))
    except (TypeError, ValueError):
        limit = 5

    current_rows = _calculate_grouped_bundle(
        data, query, start_text, end_text
    )

    comparison_period = None
    previous_by_key = {}

    if sort_measure in {"growth", "growth_pct", "change_pct", "pct_change"}:
        comparison_period = _resolved_comparison_period(
            query, start_text, end_text
        )
        if comparison_period is None:
            raise ValueError(
                "Growth ranking needs a comparison period."
            )

        previous_rows = _calculate_grouped_bundle(
            data,
            query,
            comparison_period[0],
            comparison_period[1],
        )

        def key_for(row: dict) -> tuple:
            groups = row.get("groups", {})
            return tuple(
                groups.get(dim, "")
                for dim in dimensions
            )

        previous_by_key = {
            key_for(row): row
            for row in previous_rows
        }

    ranked_rows = []

    for current_row in current_rows:
        groups = deepcopy(current_row.get("groups", {}))
        current_metrics = deepcopy(
            current_row.get("metrics", {})
        )
        current_value = current_metrics.get(
            primary_metric, 0
        )

        comparison_metrics = None
        growth_pct = None

        if comparison_period is not None:
            key = tuple(
                groups.get(dim, "")
                for dim in dimensions
            )
            previous_row = previous_by_key.get(key)
            if previous_row is None:
                continue

            comparison_metrics = deepcopy(
                previous_row.get("metrics", {})
            )
            growth_pct = _growth(
                current_value,
                comparison_metrics.get(primary_metric, 0),
            )
            sort_value = growth_pct
        else:
            sort_value = current_value

        if sort_value is None:
            continue

        ranked_rows.append({
            "groups": groups,
            "metrics": current_metrics,
            "comparison_metrics": comparison_metrics,
            "growth_pct": (
                {primary_metric: growth_pct}
                if growth_pct is not None
                else {}
            ),
            "sort_value": sort_value,
        })

    reverse = direction not in {"asc", "ascending", "bottom", "lowest"}
    ranked_rows.sort(
        key=lambda row: float(row["sort_value"]),
        reverse=reverse,
    )
    ranked_rows = ranked_rows[:limit]

    return {
        "status": "ok",
        "result_type": "ranked",
        "period": {
            "start_date": start_text,
            "end_date": end_text,
        },
        "comparison": {
            "type": query.get("comparison", "none"),
            "period": (
                {
                    "start_date": comparison_period[0],
                    "end_date": comparison_period[1],
                }
                if comparison_period
                else None
            ),
        },
        "metrics": list(query.get("metrics", [])),
        "group_by": dimensions,
        "selection": {
            "limit": limit,
            "direction": direction,
            "sort_measure": sort_measure,
        },
        "rows": ranked_rows,
    }



def _execute_diagnose(
    data: dict,
    query: dict,
    start_text: str,
    end_text: str,
) -> dict:
    """
    Diagnose a KPI movement through its business drivers.

    Current diagnostic tree for SALES:
        Sales = Transactions x APT
        -> identify whether Transactions and/or APT drove the movement
        -> for each declining driver, identify store and channel contributions

    Product-mix decomposition is intentionally deferred.
    """
    requested_metrics = list(query.get("metrics", []))
    target_metric = requested_metrics[0] if requested_metrics else "sales"

    comparison_period = _resolved_comparison_period(
        query, start_text, end_text
    )
    if comparison_period is None:
        raise ValueError(
            "Diagnosis needs a comparison period."
        )

    if target_metric != "sales":
        return {
            "status": "not_yet_executable",
            "reason": (
                "Diagnostic decomposition is currently implemented "
                "for sales."
            ),
        }

    # Sales is decomposed into its two direct commercial drivers.
    driver_query = deepcopy(query)
    driver_query["metrics"] = ["sales", "transactions", "apt"]
    driver_query["stores"] = list(query.get("stores", []))
    driver_query["channels"] = list(query.get("channels", []))
    driver_query["group_by"] = []

    current, current_rows = _calculate_metric_bundle(
        data, driver_query, start_text, end_text
    )
    previous, previous_rows = _calculate_metric_bundle(
        data,
        driver_query,
        comparison_period[0],
        comparison_period[1],
    )

    if current_rows == 0:
        return {
            "status": "no_data",
            "period": {
                "start_date": start_text,
                "end_date": end_text,
            },
        }

    overall_growth = {
        metric: _growth(
            current.get(metric, 0),
            previous.get(metric, 0),
        )
        for metric in ("sales", "transactions", "apt")
    }

    declining_drivers = [
        metric
        for metric in ("transactions", "apt")
        if overall_growth.get(metric) is not None
        and overall_growth[metric] < 0
    ]

    driver_details = {}

    for driver in declining_drivers:
        driver_details[driver] = {}

        for dimension in ("store", "channel"):
            grouped_query = deepcopy(query)
            grouped_query["metrics"] = [driver]
            grouped_query["group_by"] = [dimension]
            # To explain contribution across a dimension, remove a
            # pre-existing filter on that same dimension. Preserve the
            # other scope filters.
            if dimension == "store":
                grouped_query["stores"] = []
            else:
                grouped_query["channels"] = []

            current_grouped = _calculate_grouped_bundle(
                data,
                grouped_query,
                start_text,
                end_text,
            )
            previous_grouped = _calculate_grouped_bundle(
                data,
                grouped_query,
                comparison_period[0],
                comparison_period[1],
            )

            def group_key(row: dict):
                return (
                    row.get("groups", {}).get(dimension, "")
                )

            previous_map = {
                group_key(row): row
                for row in previous_grouped
            }

            contributors = []
            for row in current_grouped:
                name = group_key(row)
                prior = previous_map.get(name)
                if prior is None:
                    continue

                current_value = (
                    row.get("metrics", {}).get(driver, 0)
                )
                previous_value = (
                    prior.get("metrics", {}).get(driver, 0)
                )
                absolute_change = current_value - previous_value
                growth_pct = _growth(
                    current_value, previous_value
                )

                if absolute_change < 0:
                    contributors.append({
                        "name": name,
                        "current": current_value,
                        "previous": previous_value,
                        "absolute_change": absolute_change,
                        "growth_pct": growth_pct,
                    })

            # "Contributing most" means the largest absolute negative
            # contribution to the driver's fall, not merely the worst %.
            contributors.sort(
                key=lambda item: item["absolute_change"]
            )
            driver_details[driver][dimension] = contributors

    return {
        "status": "ok",
        "result_type": "diagnosis",
        "target_metric": target_metric,
        "period": {
            "start_date": start_text,
            "end_date": end_text,
        },
        "comparison": {
            "type": query.get("comparison", "none"),
            "period": {
                "start_date": comparison_period[0],
                "end_date": comparison_period[1],
            },
        },
        "current": current,
        "previous": previous,
        "growth_pct": overall_growth,
        "declining_drivers": declining_drivers,
        "driver_details": driver_details,
        "scope": {
            "stores": list(query.get("stores", [])),
            "channels": list(query.get("channels", [])),
        },
    }


def _growth(current: float, previous: float) -> float | None:
    if previous == 0:
        return None
    return (float(current) - float(previous)) / abs(float(previous)) * 100.0


def _calculate_metric_bundle(data: dict, query: dict, start_text: str, end_text: str) -> tuple[dict, int]:
    results = {}
    row_count = 0
    for metric in query["metrics"]:
        ral = _compatible_ral(query, metric, start_text, end_text)
        filtered = apply_ral_filters(data=data, ral_request=ral)
        row_count = max(row_count, len(filtered))
        results[metric] = calculate_metric(metric_name=metric, filtered_df=filtered)
    return results, row_count


def _calculate_grouped_bundle(data: dict, query: dict, start_text: str, end_text: str) -> list[dict]:
    merged: dict[tuple, dict] = {}
    dimensions = list(query.get("group_by", []))

    for metric in query["metrics"]:
        ral = _compatible_ral(query, metric, start_text, end_text)
        grouped = calculate_grouped_metric(
            filtered_sales=apply_ral_filters(data=data, ral_request=ral),
            data=data,
            ral_request=ral,
        )
        for row in grouped.get("rows", []):
            groups = row.get("groups", {})
            key = tuple(groups.get(dim, "") for dim in dimensions)
            target = merged.setdefault(key, {"groups": deepcopy(groups), "metrics": {}})
            target["metrics"][metric] = row.get("metric_value", 0)

    return list(merged.values())


def execute_business_query(data: dict, query: dict) -> dict:
    if query.get("needs_clarification"):
        return {
            "status": "clarification",
            "question": query.get("clarification_question") or "Could you clarify that request?",
        }

    if query.get("operation") not in {
        "retrieve", "compare", "summarize", "filter", "rank", "diagnose"
    }:
        return {"status": "not_yet_executable"}

    start_text, end_text = _effective_period(query, data)
    group_by = list(query.get("group_by", []))

    if query.get("operation") == "filter":
        return _execute_filter(data, query, start_text, end_text)

    if query.get("operation") == "rank":
        return _execute_rank(data, query, start_text, end_text)

    if query.get("operation") == "diagnose":
        return _execute_diagnose(data, query, start_text, end_text)

    if group_by:
        # Grouped retrieval and grouped comparison share the same deterministic
        # calculation path.  The old V3 code returned current-period rows here
        # and accidentally discarded comparison intent entirely.
        current_rows = _calculate_grouped_bundle(
            data, query, start_text, end_text
        )
        comparison_period = _resolved_comparison_period(
            query, start_text, end_text
        )

        if comparison_period is None:
            company_total, _ = _calculate_metric_bundle(
                data, query, start_text, end_text
            )
            return {
                "status": "ok",
                "result_type": "grouped",
                "period": {"start_date": start_text, "end_date": end_text},
                "metrics": list(query["metrics"]),
                "group_by": group_by,
                "rows": current_rows,
                "company_total": company_total,
                "comparison": {"type": "none", "period": None},
            }

        previous_rows = _calculate_grouped_bundle(
            data, query, comparison_period[0], comparison_period[1]
        )

        def grouped_key(row: dict) -> tuple:
            groups = row.get("groups", {})
            return tuple(groups.get(dim, "") for dim in group_by)

        previous_by_key = {
            grouped_key(row): row for row in previous_rows
        }
        combined_rows = []
        for row in current_rows:
            previous = previous_by_key.get(grouped_key(row))
            previous_metrics = (
                deepcopy(previous.get("metrics", {}))
                if previous is not None else {}
            )
            current_metrics = deepcopy(row.get("metrics", {}))
            growth = {}
            change = {}
            for metric in query["metrics"]:
                current_value = current_metrics.get(metric, 0)
                previous_value = previous_metrics.get(metric, 0)
                growth[metric] = _growth(current_value, previous_value)
                change[metric] = current_value - previous_value

            combined_rows.append({
                "groups": deepcopy(row.get("groups", {})),
                "metrics": current_metrics,
                "comparison_metrics": previous_metrics,
                "change": change,
                "growth_pct": growth,
            })

        company_total, _ = _calculate_metric_bundle(
            data, query, start_text, end_text
        )
        comparison_total, _ = _calculate_metric_bundle(
            data, query, comparison_period[0], comparison_period[1]
        )

        return {
            "status": "ok",
            "result_type": "grouped_comparison",
            "period": {"start_date": start_text, "end_date": end_text},
            "metrics": list(query["metrics"]),
            "group_by": group_by,
            "rows": combined_rows,
            "company_total": company_total,
            "comparison_total": comparison_total,
            "comparison": {
                "type": query.get("comparison", "none"),
                "period": {
                    "start_date": comparison_period[0],
                    "end_date": comparison_period[1],
                },
            },
        }

    current, row_count = _calculate_metric_bundle(data, query, start_text, end_text)
    if row_count == 0:
        return {
            "status": "no_data",
            "period": {"start_date": start_text, "end_date": end_text},
        }

    comparison_name = query.get("comparison", "none")
    comparison_period = _resolved_comparison_period(query, start_text, end_text)
    comparison_values = None
    growth = None
    if comparison_period is not None:
        comparison_values, _ = _calculate_metric_bundle(
            data, query, comparison_period[0], comparison_period[1]
        )
        growth = {
            metric: _growth(current[metric], comparison_values[metric])
            for metric in query["metrics"]
        }

    return {
        "status": "ok",
        "result_type": "summary",
        "period": {"start_date": start_text, "end_date": end_text},
        "metrics": current,
        "comparison": {
            "type": comparison_name,
            "period": (
                {"start_date": comparison_period[0], "end_date": comparison_period[1]}
                if comparison_period
                else None
            ),
            "metrics": comparison_values,
            "growth_pct": growth,
        },
    }
