from datetime import date
from pathlib import Path
from uuid import uuid4

from openpyxl import Workbook
from openpyxl.styles import Font, Alignment
from PIL import Image, ImageDraw, ImageFont

PROJECT_ROOT = Path(__file__).resolve().parents[2]
STATIC_REPORTS = PROJECT_ROOT / "static" / "reports"


def _indian(value: float) -> str:
    number = int(round(float(value)))
    sign = "-" if number < 0 else ""
    digits = str(abs(number))
    if len(digits) <= 3:
        return sign + digits
    last, rest = digits[-3:], digits[:-3]
    groups = []
    while len(rest) > 2:
        groups.insert(0, rest[-2:])
        rest = rest[:-2]
    if rest:
        groups.insert(0, rest)
    return sign + ",".join(groups + [last])


def _metric_value(metric: str, value: float) -> str:
    if metric in {"sales", "apt", "ads"}:
        return "₹" + _indian(value)
    if metric == "adt":
        return f"{float(value):.1f}"
    return _indian(value)


def _metric_name(metric: str) -> str:
    return {"sales": "Sales", "transactions": "Txns", "apt": "APT", "ads": "ADS", "adt": "ADT"}.get(metric, metric.upper())


def _period_label(period: dict) -> str:
    start = date.fromisoformat(period["start_date"])
    end = date.fromisoformat(period["end_date"])
    return start.strftime("%d %b %Y") if start == end else f"{start.strftime('%d %b %Y')} to {end.strftime('%d %b %Y')}"


def _growth_text(value: float | None) -> str:
    if value is None:
        return "N/A"
    return f"{'+' if value > 0 else ''}{value:.1f}%"


def _font(size: int, bold: bool = False):
    candidates = [
        PROJECT_ROOT / "assets" / "fonts" / ("DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
        Path("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf" if bold else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    ]
    for path in candidates:
        if path.exists():
            return ImageFont.truetype(str(path), size=size)
    return ImageFont.load_default()


def _tabular_rows(result: dict) -> tuple[list[str], list[list[str]]]:
    metrics = result.get("metrics", [])
    dimensions = result.get("group_by", [])
    result_type = result.get("result_type")
    headers = [d.title() for d in dimensions]
    rows_out = []

    if result_type == "grouped_comparison":
        current_label = _period_label(result["period"])
        previous_label = _period_label(result["comparison"]["period"])
        for metric in metrics:
            headers += [f"{_metric_name(metric)} {current_label}", f"{_metric_name(metric)} {previous_label}", "Change %"]
        for row in result.get("rows", []):
            values = [str(row.get("groups", {}).get(d, "")) for d in dimensions]
            for metric in metrics:
                values += [
                    _metric_value(metric, row.get("metrics", {}).get(metric, 0)),
                    _metric_value(metric, row.get("comparison_metrics", {}).get(metric, 0)),
                    _growth_text(row.get("growth_pct", {}).get(metric)),
                ]
            rows_out.append(values)
        return headers, rows_out

    for metric in metrics:
        headers.append(_metric_name(metric))
    include_growth = result_type in {"filtered", "ranked"} and any(r.get("growth_pct") for r in result.get("rows", []))
    if include_growth:
        headers.append("Change %")
    for row in result.get("rows", []):
        values = [str(row.get("groups", {}).get(d, "")) for d in dimensions]
        values += [_metric_value(m, row.get("metrics", {}).get(m, 0)) for m in metrics]
        if include_growth:
            primary = metrics[0] if metrics else "sales"
            values.append(_growth_text(row.get("growth_pct", {}).get(primary)))
        rows_out.append(values)
    return headers, rows_out


def _make_table_image(result: dict) -> str:
    STATIC_REPORTS.mkdir(parents=True, exist_ok=True)
    headers, rows = _tabular_rows(result)
    title = _period_label(result["period"])
    if result.get("comparison", {}).get("period"):
        title += "  vs  " + _period_label(result["comparison"]["period"])
    font = _font(24)
    bold = _font(24, True)
    title_font = _font(30, True)
    padding, row_h = 18, 52
    widths = []
    scratch = ImageDraw.Draw(Image.new("RGB", (10, 10)))
    for i, header in enumerate(headers):
        candidates = [header] + [str(r[i]) for r in rows]
        widths.append(min(330, max(125, max(scratch.textbbox((0, 0), t, font=bold if t == header else font)[2] for t in candidates) + 2 * padding)))
    width = max(900, sum(widths) + 40)
    height = 100 + row_h * (len(rows) + 1) + 30
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    draw.text((20, 20), title, font=title_font, fill="black")
    y = 80
    x0 = 20
    for ridx, row in enumerate([headers] + rows):
        x = x0
        for cidx, text in enumerate(row):
            draw.rectangle((x, y, x + widths[cidx], y + row_h), outline="#C9CED6", fill="#F2F4F7" if ridx == 0 else "white")
            draw.text((x + padding, y + 13), str(text), font=bold if ridx == 0 else font, fill="black")
            x += widths[cidx]
        y += row_h
    filename = f"business_query_{uuid4().hex}.png"
    image.save(STATIC_REPORTS / filename)
    return f"/static/reports/{filename}"


def _make_excel(result: dict) -> str:
    STATIC_REPORTS.mkdir(parents=True, exist_ok=True)
    headers, rows = _tabular_rows(result)
    wb = Workbook()
    ws = wb.active
    ws.title = "RestaurantAI"
    ws.append([_period_label(result["period"])])
    if result.get("comparison", {}).get("period"):
        ws.append(["Compared with", _period_label(result["comparison"]["period"])])
    ws.append([])
    ws.append(headers)
    for cell in ws[ws.max_row]:
        cell.font = Font(bold=True)
        cell.alignment = Alignment(horizontal="center")
    for row in rows:
        ws.append(row)
    for column in ws.columns:
        letter = column[0].column_letter
        ws.column_dimensions[letter].width = min(40, max(12, max(len(str(c.value or "")) for c in column) + 2))
    filename = f"restaurantai_{uuid4().hex}.xlsx"
    wb.save(STATIC_REPORTS / filename)
    return f"/static/reports/{filename}"


def _make_bar_chart(result: dict) -> str | None:
    rows = result.get("rows", [])
    metrics = result.get("metrics", [])
    dimensions = result.get("group_by", [])
    if not rows or not metrics or not dimensions:
        return None
    metric = metrics[0]
    labels = [" | ".join(str(r.get("groups", {}).get(d, "")) for d in dimensions) for r in rows]
    values = [float(r.get("metrics", {}).get(metric, 0)) for r in rows]
    STATIC_REPORTS.mkdir(parents=True, exist_ok=True)
    width, height = 1200, max(650, 95 * len(rows) + 180)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)
    title_font, font, bold = _font(30, True), _font(22), _font(22, True)
    draw.text((30, 25), f"{_metric_name(metric)} — {_period_label(result['period'])}", font=title_font, fill="black")
    max_v = max(values) if values else 1
    y = 100
    for label, value in zip(labels, values):
        draw.text((30, y), label[:32], font=bold, fill="black")
        bar_x = 330
        bar_w = int((value / max_v) * 650) if max_v else 0
        draw.rectangle((bar_x, y + 2, bar_x + bar_w, y + 28), fill="#6B7280")
        draw.text((1000, y), _metric_value(metric, value), font=font, fill="black")
        y += 75
    filename = f"business_chart_{uuid4().hex}.png"
    image.save(STATIC_REPORTS / filename)
    return f"/static/reports/{filename}"


def _text_response(result: dict) -> dict:
    rt = result["result_type"]
    if rt == "diagnosis":
        lines = [f"📊 *{_period_label(result['period'])}*"]
        cp = (result.get("comparison", {}) or {}).get("period")
        if cp: lines.append(f"Compared with *{_period_label(cp)}*.")
        growth, current = result.get("growth_pct", {}), result.get("current", {})
        lines += ["", f"*Sales:* {_metric_value('sales', current.get('sales', 0))} ({_growth_text(growth.get('sales'))})", "", "*Primary drivers:*", f"• Transactions: {_metric_value('transactions', current.get('transactions', 0))} ({_growth_text(growth.get('transactions'))})", f"• APT: {_metric_value('apt', current.get('apt', 0))} ({_growth_text(growth.get('apt'))})"]
        return {"response_type": "text", "body": "\n".join(lines)}

    if rt in {"grouped", "grouped_comparison", "filtered", "ranked"}:
        rows, dims, metrics = result.get("rows", []), result.get("group_by", []), result.get("metrics", [])
        lines = [f"📊 *{_period_label(result['period'])}*"]
        cp = (result.get("comparison", {}) or {}).get("period")
        if cp: lines += [f"Compared with *{_period_label(cp)}*."]
        lines.append("")
        if not rows:
            lines.append("No matching results found.")
        for i, row in enumerate(rows[:12], 1):
            label = " | ".join(str(row.get("groups", {}).get(d, "")) for d in dims)
            pieces = []
            for metric in metrics:
                piece = f"{_metric_name(metric)} {_metric_value(metric, row.get('metrics', {}).get(metric, 0))}"
                if rt == "grouped_comparison":
                    piece += f" vs {_metric_value(metric, row.get('comparison_metrics', {}).get(metric, 0))} ({_growth_text(row.get('growth_pct', {}).get(metric))})"
                elif metric in row.get("growth_pct", {}):
                    piece += f" ({_growth_text(row.get('growth_pct', {}).get(metric))})"
                pieces.append(piece)
            lines.append(f"{i}. *{label}* — " + " · ".join(pieces))
        return {"response_type": "text", "body": "\n".join(lines)}

    lines = [f"📊 *{_period_label(result['period'])}*", ""]
    comparison = result.get("comparison", {}) or {}
    growth = comparison.get("growth_pct") or {}
    for metric, value in result["metrics"].items():
        line = f"*{_metric_name(metric)}:* {_metric_value(metric, value)}"
        if metric in growth: line += f"  ({_growth_text(growth[metric])})"
        lines.append(line)
    if comparison.get("period"):
        lines.append(f"\nCompared with *{_period_label(comparison['period'])}*.")
    return {"response_type": "text", "body": "\n".join(lines)}


def present_business_query(query: dict, result: dict) -> dict:
    status = result.get("status")
    if status == "clarification": return {"response_type": "text", "body": result["question"]}
    if status == "no_data": return {"response_type": "text", "body": f"I could not find sales data for {_period_label(result['period'])}."}
    if status != "ok": return {"status": "fallback"}

    requested = str(query.get("presentation", "auto")).lower()
    rt = result.get("result_type")
    rows = result.get("rows", [])

    # Explicit user format always wins. Auto is a usability decision made only
    # after the analytical result is complete.
    if requested == "excel":
        if rt not in {"grouped", "grouped_comparison", "filtered", "ranked"}:
            return _text_response(result)
        return {"response_type": "media", "body": "📎 RestaurantAI Excel report", "relative_media_url": _make_excel(result)}

    if requested == "chart":
        path = _make_bar_chart(result)
        if path:
            return {"response_type": "media", "body": "📊 RestaurantAI chart", "relative_media_url": path}
        # A true time-series trend is owned by the existing trend pipeline.
        return {"status": "fallback"}

    dense = (
        rt == "grouped_comparison"
        or (rt in {"grouped", "filtered", "ranked"} and (len(rows) > 6 or len(result.get("metrics", [])) > 2))
    )
    if requested == "image_table" or (requested == "auto" and dense):
        return {"response_type": "media", "body": "📊 RestaurantAI analysis", "relative_media_url": _make_table_image(result)}

    return _text_response(result)
