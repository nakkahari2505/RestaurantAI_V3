from datetime import date


def _indian(value: float) -> str:
    number = int(round(float(value)))
    sign = "-" if number < 0 else ""
    digits = str(abs(number))
    if len(digits) <= 3:
        return sign + digits
    last = digits[-3:]
    rest = digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return sign + ",".join(groups + [last])


def _metric_value(metric: str, value: float) -> str:
    if metric in {"sales", "apt"}:
        return "₹" + _indian(value)
    if metric in {"ads"}:
        return "₹" + _indian(value)
    if metric == "adt":
        return f"{float(value):.1f}"
    return _indian(value)


def _metric_name(metric: str) -> str:
    return {
        "sales": "Sales",
        "transactions": "Txns",
        "apt": "APT",
        "ads": "ADS",
        "adt": "ADT",
    }.get(metric, metric.upper())


def _period_label(period: dict) -> str:
    start = date.fromisoformat(period["start_date"])
    end = date.fromisoformat(period["end_date"])
    if start == end:
        return start.strftime("%d %b %Y")
    return f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"


def _growth_text(value: float | None) -> str:
    if value is None:
        return "N/A"
    sign = "+" if value > 0 else ""
    return f"{sign}{value:.1f}%"


def present_business_query(query: dict, result: dict) -> dict:
    status = result.get("status")
    if status == "clarification":
        return {"response_type": "text", "body": result["question"]}
    if status == "no_data":
        return {
            "response_type": "text",
            "body": f"I could not find sales data for {_period_label(result['period'])}.",
        }
    if status != "ok":
        return {"status": "fallback"}

    if result["result_type"] == "diagnosis":
        lines = [
            f"📊 *{_period_label(result['period'])}*",
        ]

        comparison_period = (
            result.get("comparison", {}) or {}
        ).get("period")
        if comparison_period:
            lines.append(
                f"Compared with *{_period_label(comparison_period)}*."
            )

        growth = result.get("growth_pct", {})
        current = result.get("current", {})

        lines.extend([
            "",
            f"*Sales:* {_metric_value('sales', current.get('sales', 0))} "
            f"({_growth_text(growth.get('sales'))})",
            "",
            "*Primary drivers:*",
            f"• Transactions: {_metric_value('transactions', current.get('transactions', 0))} "
            f"({_growth_text(growth.get('transactions'))})",
            f"• APT: {_metric_value('apt', current.get('apt', 0))} "
            f"({_growth_text(growth.get('apt'))})",
        ])

        declining = result.get("declining_drivers", [])
        if not declining:
            lines.extend([
                "",
                "Transactions and APT are not declining in the selected comparison, "
                "so this first-level sales diagnostic does not identify a negative "
                "driver. Product-mix analysis can be added next.",
            ])
            return {
                "response_type": "text",
                "body": "\n".join(lines),
            }

        details = result.get("driver_details", {})

        for driver in declining:
            lines.extend([
                "",
                f"*What is driving the {_metric_name(driver)} decline?*",
            ])

            for dimension in ("store", "channel"):
                contributors = (
                    details.get(driver, {}).get(dimension, [])
                )
                if not contributors:
                    continue

                label = "Stores" if dimension == "store" else "Channels"
                lines.append(f"{label}:")
                for item in contributors[:5]:
                    lines.append(
                        f"• {item['name']}: "
                        f"{_metric_value(driver, item['current'])} "
                        f"({_growth_text(item.get('growth_pct'))})"
                    )

        return {
            "response_type": "text",
            "body": "\n".join(lines),
        }

    if result["result_type"] == "ranked":
        rows = result.get("rows", [])
        dimensions = result.get("group_by", [])
        metrics = result.get("metrics", [])
        selection = result.get("selection", {}) or {}
        lines = [f"📊 *{_period_label(result['period'])}*", ""]

        comparison_period = (
            result.get("comparison", {}) or {}
        ).get("period")
        if comparison_period:
            lines.append(
                f"Compared with *{_period_label(comparison_period)}*."
            )
            lines.append("")

        if not rows:
            lines.append("No ranking results found.")
            return {
                "response_type": "text",
                "body": "\n".join(lines),
            }

        for index, row in enumerate(rows, start=1):
            label = " | ".join(
                str(row["groups"].get(dim, ""))
                for dim in dimensions
            )
            pieces = []
            for metric in metrics:
                value = row.get("metrics", {}).get(metric, 0)
                growth = row.get("growth_pct", {}).get(metric)
                piece = (
                    f"{_metric_name(metric)} "
                    f"{_metric_value(metric, value)}"
                )
                if growth is not None:
                    piece += f" ({_growth_text(growth)})"
                pieces.append(piece)

            lines.append(
                f"{index}. *{label}* — " + " · ".join(pieces)
            )

        return {
            "response_type": "text",
            "body": "\n".join(lines),
        }

    if result["result_type"] == "filtered":
        rows = result.get("rows", [])
        dimensions = result.get("group_by", [])
        metrics = result.get("metrics", [])
        lines = [f"📊 *{_period_label(result['period'])}*", ""]

        comparison_period = (result.get("comparison", {}) or {}).get("period")
        if comparison_period:
            lines.append(f"Compared with *{_period_label(comparison_period)}*.")
            lines.append("")

        if not rows:
            lines.append("No matching results found.")
            return {"response_type": "text", "body": "\n".join(lines)}

        max_rows = 12
        for index, row in enumerate(rows[:max_rows], start=1):
            label = " | ".join(str(row["groups"].get(dim, "")) for dim in dimensions)
            pieces = []
            for metric in metrics:
                value = row.get("metrics", {}).get(metric, 0)
                growth = row.get("growth_pct", {}).get(metric)
                piece = f"{_metric_name(metric)} {_metric_value(metric, value)}"
                if growth is not None:
                    piece += f" ({_growth_text(growth)})"
                pieces.append(piece)
            lines.append(f"{index}. *{label}* — " + " · ".join(pieces))

        if len(rows) > max_rows:
            lines.append(f"\nShowing {max_rows} of {len(rows)} rows.")
        return {"response_type": "text", "body": "\n".join(lines)}

    if result["result_type"] == "grouped":
        rows = result.get("rows", [])
        dimensions = result.get("group_by", [])
        metrics = result.get("metrics", [])
        lines = [f"📊 *{_period_label(result['period'])}*", ""]
        max_rows = 12
        for index, row in enumerate(rows[:max_rows], start=1):
            label = " | ".join(str(row["groups"].get(dim, "")) for dim in dimensions)
            values = " · ".join(
                f"{_metric_name(metric)} {_metric_value(metric, row['metrics'].get(metric, 0))}"
                for metric in metrics
            )
            lines.append(f"{index}. *{label}* — {values}")
        if len(rows) > max_rows:
            lines.append(f"\nShowing {max_rows} of {len(rows)} rows.")
        return {"response_type": "text", "body": "\n".join(lines)}

    lines = [f"📊 *{_period_label(result['period'])}*", ""]
    comparison = result.get("comparison", {})
    growth = comparison.get("growth_pct") or {}
    for metric, value in result["metrics"].items():
        line = f"*{_metric_name(metric)}:* {_metric_value(metric, value)}"
        if metric in growth:
            line += f"  ({_growth_text(growth[metric])})"
        lines.append(line)

    if comparison.get("period"):
        comp_name = (
            "same period last year"
            if comparison.get("type") == "same_period_last_year"
            else "previous comparable period"
        )
        lines.append(f"\nCompared with {comp_name}.")

    return {"response_type": "text", "body": "\n".join(lines)}
