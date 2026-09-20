from __future__ import annotations

from pathlib import Path
from typing import Final

from PIL import ImageDraw

from services.presentation.image_engine import (
    create_canvas,
    get_text_width,
    load_font,
    save_png,
)


PROJECT_ROOT: Final[Path] = (
    Path(__file__).resolve().parents[3]
)
REPORTS_DIRECTORY: Final[Path] = (
    PROJECT_ROOT / "reports"
)

BACKGROUND: Final[str] = "#FFFFFF"
TEXT: Final[str] = "#202124"
MUTED: Final[str] = "#667085"
BORDER: Final[str] = "#D0D5DD"
SECTION_HEADER: Final[str] = "#15365D"
METRIC_HEADER: Final[str] = "#DCE8F8"
SUBHEADER: Final[str] = "#F2F6FC"
ROW_ALT: Final[str] = "#FAFBFC"
TOTAL_BG: Final[str] = "#E9EEF5"
POSITIVE: Final[str] = "#157A3D"
NEGATIVE: Final[str] = "#C62828"
NEUTRAL: Final[str] = "#475467"

TITLE_SIZE: Final[int] = 46
SUBTITLE_SIZE: Final[int] = 24
SECTION_SIZE: Final[int] = 28
HEADER_SIZE: Final[int] = 23
BODY_SIZE: Final[int] = 23
TOTAL_SIZE: Final[int] = 24
FOOTNOTE_SIZE: Final[int] = 19
NARRATIVE_SIZE: Final[int] = 21
NARRATIVE_LINE_GAP: Final[int] = 10
NARRATIVE_PADDING: Final[int] = 26
NARRATIVE_HEADING_HEIGHT: Final[int] = 44
NARRATIVE_PANEL_GAP: Final[int] = 10

LEFT_MARGIN: Final[int] = 42
RIGHT_MARGIN: Final[int] = 42
TOP_MARGIN: Final[int] = 34
BOTTOM_MARGIN: Final[int] = 34

STORE_WIDTH: Final[int] = 390
CURRENT_WIDTH: Final[int] = 215
COMPARE_WIDTH: Final[int] = 250
CHANGE_WIDTH: Final[int] = 165

SECTION_TITLE_HEIGHT: Final[int] = 74
METRIC_HEADER_HEIGHT: Final[int] = 58
SUBHEADER_HEIGHT: Final[int] = 62
ROW_HEIGHT: Final[int] = 58
SECTION_GAP: Final[int] = 34


def _indian_number(value: float, decimals: int = 0) -> str:
    numeric_value = float(value)
    sign = "-" if numeric_value < 0 else ""
    numeric_value = abs(numeric_value)

    rendered = f"{numeric_value:.{decimals}f}"
    if "." in rendered:
        integer_part, decimal_part = rendered.split(".")
    else:
        integer_part, decimal_part = rendered, ""

    if len(integer_part) <= 3:
        formatted = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted = ",".join(groups) + "," + last_three

    if decimals > 0:
        return sign + formatted + "." + decimal_part
    return sign + formatted


def _metric_value(metric_name: str, value: float) -> str:
    if metric_name in {"sales", "transactions", "apt", "ads"}:
        return _indian_number(value, decimals=0)

    if metric_name == "adt":
        return _indian_number(value, decimals=1)

    return _indian_number(value, decimals=1)


def _change_text(value: float | None) -> str:
    if value is None:
        return "New"
    return f"{value:+.1f}%"


def _change_colour(value: float | None) -> str:
    if value is None:
        return NEUTRAL
    if value > 0:
        return POSITIVE
    if value < 0:
        return NEGATIVE
    return NEUTRAL


def _draw_centered(
    draw: ImageDraw.ImageDraw,
    text: str,
    left: int,
    right: int,
    top: int,
    bottom: int,
    font,
    fill: str,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    width = bbox[2] - bbox[0]
    height = bbox[3] - bbox[1]

    x = left + (right - left - width) // 2
    y = top + (bottom - top - height) // 2 - bbox[1]

    draw.text((x, y), text, font=font, fill=fill)


def _draw_left(
    draw: ImageDraw.ImageDraw,
    text: str,
    left: int,
    top: int,
    bottom: int,
    font,
    fill: str,
    padding: int = 14,
) -> None:
    bbox = draw.textbbox((0, 0), text, font=font)
    height = bbox[3] - bbox[1]
    y = top + (bottom - top - height) // 2 - bbox[1]

    draw.text(
        (left + padding, y),
        text,
        font=font,
        fill=fill,
    )


def _draw_right(
    draw: ImageDraw.ImageDraw,
    text: str,
    right: int,
    top: int,
    bottom: int,
    font,
    fill: str,
    padding: int = 12,
) -> None:
    width = get_text_width(
        draw=draw,
        text=text,
        font=font,
    )
    bbox = draw.textbbox((0, 0), text, font=font)
    height = bbox[3] - bbox[1]
    y = top + (bottom - top - height) // 2 - bbox[1]

    draw.text(
        (right - padding - width, y),
        text,
        font=font,
        fill=fill,
    )


def _cell(
    draw: ImageDraw.ImageDraw,
    left: int,
    top: int,
    right: int,
    bottom: int,
    fill: str,
) -> None:
    draw.rectangle(
        (left, top, right, bottom),
        fill=fill,
        outline=BORDER,
        width=1,
    )


def _column_geometry(metric_count: int) -> tuple[int, list[dict]]:
    x = LEFT_MARGIN + STORE_WIDTH
    metrics = []

    for _ in range(metric_count):
        current_left = x
        current_right = current_left + CURRENT_WIDTH

        compare_left = current_right
        compare_right = compare_left + COMPARE_WIDTH

        change_left = compare_right
        change_right = change_left + CHANGE_WIDTH

        metrics.append(
            {
                "left": current_left,
                "right": change_right,
                "current": (current_left, current_right),
                "compare": (compare_left, compare_right),
                "change": (change_left, change_right),
            }
        )

        x = change_right

    return x + RIGHT_MARGIN, metrics


def _draw_section(
    draw: ImageDraw.ImageDraw,
    top: int,
    canvas_width: int,
    rows: list[dict],
    section_title: str,
    section_subtitle: str,
    metrics: list[tuple[str, str]],
    current_label: str,
    comparison_label: str,
    fonts: dict,
) -> int:
    table_left = LEFT_MARGIN
    table_right = canvas_width - RIGHT_MARGIN

    section_bottom = top + SECTION_TITLE_HEIGHT

    draw.rounded_rectangle(
        (table_left, top, table_right, section_bottom),
        radius=14,
        fill=SECTION_HEADER,
    )

    _draw_left(
        draw=draw,
        text=section_title,
        left=table_left,
        top=top,
        bottom=section_bottom,
        font=fonts["section"],
        fill="#FFFFFF",
        padding=22,
    )

    subtitle_width = get_text_width(
        draw=draw,
        text=section_subtitle,
        font=fonts["section_subtitle"],
    )
    subtitle_bbox = draw.textbbox(
        (0, 0),
        section_subtitle,
        font=fonts["section_subtitle"],
    )
    subtitle_height = subtitle_bbox[3] - subtitle_bbox[1]

    draw.text(
        (
            table_right - 22 - subtitle_width,
            top
            + (SECTION_TITLE_HEIGHT - subtitle_height) // 2
            - subtitle_bbox[1],
        ),
        section_subtitle,
        font=fonts["section_subtitle"],
        fill="#EAF0F8",
    )

    header_top = section_bottom + 10
    metric_header_bottom = header_top + METRIC_HEADER_HEIGHT
    subheader_bottom = metric_header_bottom + SUBHEADER_HEIGHT

    _cell(
        draw,
        table_left,
        header_top,
        table_left + STORE_WIDTH,
        subheader_bottom,
        METRIC_HEADER,
    )

    _draw_centered(
        draw,
        "Store",
        table_left,
        table_left + STORE_WIDTH,
        header_top,
        subheader_bottom,
        fonts["header"],
        TEXT,
    )

    _, metric_geometry = _column_geometry(len(metrics))

    for (metric_name, metric_label), geometry in zip(
        metrics,
        metric_geometry,
    ):
        _cell(
            draw,
            geometry["left"],
            header_top,
            geometry["right"],
            metric_header_bottom,
            METRIC_HEADER,
        )

        _draw_centered(
            draw,
            metric_label,
            geometry["left"],
            geometry["right"],
            header_top,
            metric_header_bottom,
            fonts["header"],
            TEXT,
        )

        for sub_name, sub_label in (
            ("current", current_label),
            ("compare", comparison_label),
            ("change", "% Ch"),
        ):
            left, right = geometry[sub_name]

            _cell(
                draw,
                left,
                metric_header_bottom,
                right,
                subheader_bottom,
                SUBHEADER,
            )

            _draw_centered(
                draw,
                sub_label,
                left,
                right,
                metric_header_bottom,
                subheader_bottom,
                fonts["subheader"],
                MUTED,
            )

    row_top = subheader_bottom

    for row_index, row in enumerate(rows):
        is_total = row["store"] == "TOTAL"
        row_bottom = row_top + ROW_HEIGHT

        if is_total:
            row_fill = TOTAL_BG
            row_font = fonts["total"]
        elif row_index % 2 == 1:
            row_fill = ROW_ALT
            row_font = fonts["body"]
        else:
            row_fill = BACKGROUND
            row_font = fonts["body"]

        _cell(
            draw,
            table_left,
            row_top,
            table_left + STORE_WIDTH,
            row_bottom,
            row_fill,
        )

        _draw_left(
            draw,
            row["store"],
            table_left,
            row_top,
            row_bottom,
            row_font,
            TEXT,
        )

        for (metric_name, _), geometry in zip(
            metrics,
            metric_geometry,
        ):
            metric_data = row[metric_name]

            current_value = metric_data["current"]
            comparison_value = metric_data["comparison"]
            change_pct = metric_data["change_pct"]

            for sub_name in ("current", "compare", "change"):
                left, right = geometry[sub_name]
                _cell(
                    draw,
                    left,
                    row_top,
                    right,
                    row_bottom,
                    row_fill,
                )

            _draw_right(
                draw,
                _metric_value(metric_name, current_value),
                geometry["current"][1],
                row_top,
                row_bottom,
                row_font,
                TEXT,
            )

            _draw_right(
                draw,
                _metric_value(metric_name, comparison_value),
                geometry["compare"][1],
                row_top,
                row_bottom,
                row_font,
                TEXT,
            )

            _draw_centered(
                draw,
                _change_text(change_pct),
                geometry["change"][0],
                geometry["change"][1],
                row_top,
                row_bottom,
                row_font,
                _change_colour(change_pct),
            )

        row_top = row_bottom

    return row_top + SECTION_GAP



def _wrap_text_by_width(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> list[str]:
    """Wrap text to a pixel width while preserving explicit paragraph breaks."""
    cleaned = str(text or "").replace("*", "").strip()
    if not cleaned:
        return []

    wrapped_lines: list[str] = []

    for raw_line in cleaned.splitlines():
        line = raw_line.strip()
        if not line:
            wrapped_lines.append("")
            continue

        words = line.split()
        current = ""

        for word in words:
            candidate = word if not current else f"{current} {word}"
            if get_text_width(draw=draw, text=candidate, font=font) <= max_width:
                current = candidate
            else:
                if current:
                    wrapped_lines.append(current)
                current = word

        if current:
            wrapped_lines.append(current)

    return wrapped_lines


def _narrative_panel_height(lines: list[str], font) -> int:
    if not lines:
        return 0

    # DejaVu font metrics are stable across local and Railway environments.
    bbox = font.getbbox("Ag")
    line_height = (bbox[3] - bbox[1]) + NARRATIVE_LINE_GAP
    blank_height = max(12, line_height // 2)

    content_height = sum(
        blank_height if line == "" else line_height
        for line in lines
    )

    return (
        NARRATIVE_PANEL_GAP
        + NARRATIVE_PADDING
        + NARRATIVE_HEADING_HEIGHT
        + content_height
        + NARRATIVE_PADDING
    )


def _draw_narrative_panel(
    draw: ImageDraw.ImageDraw,
    top: int,
    canvas_width: int,
    lines: list[str],
    fonts: dict,
) -> int:
    if not lines:
        return top

    panel_top = top + NARRATIVE_PANEL_GAP
    panel_height = _narrative_panel_height(lines, fonts["narrative"])
    panel_bottom = panel_top + panel_height - NARRATIVE_PANEL_GAP

    draw.rounded_rectangle(
        (
            LEFT_MARGIN,
            panel_top,
            canvas_width - RIGHT_MARGIN,
            panel_bottom,
        ),
        radius=14,
        fill="#F8FAFC",
        outline=BORDER,
        width=1,
    )

    x = LEFT_MARGIN + NARRATIVE_PADDING
    y = panel_top + NARRATIVE_PADDING

    draw.text(
        (x, y),
        "Management Summary & Alerts",
        font=fonts["narrative_heading"],
        fill=SECTION_HEADER,
    )

    y += NARRATIVE_HEADING_HEIGHT

    bbox = fonts["narrative"].getbbox("Ag")
    line_height = (bbox[3] - bbox[1]) + NARRATIVE_LINE_GAP
    blank_height = max(12, line_height // 2)

    for line in lines:
        if line == "":
            y += blank_height
            continue

        draw.text(
            (x, y),
            line,
            font=fonts["narrative"],
            fill=TEXT,
        )
        y += line_height

    return panel_bottom + SECTION_GAP

def generate_yesterday_morning_report_image(
    report: dict,
    file_name: str = "yesterday_morning_report.png",
    narrative: str | None = None,
) -> dict:
    sections = report["sections"]
    labels = report["labels"]

    section_rows = max(
        len(sections["yesterday"]["rows"]),
        len(sections["mtd_total"]["rows"]),
        len(sections["mtd_kpis"]["rows"]),
    )

    canvas_width, _ = _column_geometry(3)

    fonts = {
        "title": load_font(TITLE_SIZE, bold=True),
        "subtitle": load_font(SUBTITLE_SIZE),
        "section": load_font(SECTION_SIZE, bold=True),
        "section_subtitle": load_font(21),
        "header": load_font(HEADER_SIZE, bold=True),
        "subheader": load_font(19, bold=True),
        "body": load_font(BODY_SIZE),
        "total": load_font(TOTAL_SIZE, bold=True),
        "footnote": load_font(FOOTNOTE_SIZE),
        "narrative": load_font(NARRATIVE_SIZE),
        "narrative_heading": load_font(NARRATIVE_SIZE + 2, bold=True),
    }

    # Measure/wrap the existing full WhatsApp narrative before the final
    # canvas is created so the image expands dynamically when alerts grow.
    scratch_image, scratch_draw = create_canvas(
        width=canvas_width,
        height=100,
        background=BACKGROUND,
    )
    narrative_lines = _wrap_text_by_width(
        draw=scratch_draw,
        text=narrative or "",
        font=fonts["narrative"],
        max_width=(
            canvas_width
            - LEFT_MARGIN
            - RIGHT_MARGIN
            - 2 * NARRATIVE_PADDING
        ),
    )
    del scratch_image, scratch_draw

    one_section_height = (
        SECTION_TITLE_HEIGHT
        + 10
        + METRIC_HEADER_HEIGHT
        + SUBHEADER_HEIGHT
        + section_rows * ROW_HEIGHT
        + SECTION_GAP
    )

    title_area_height = 150
    footer_height = 66
    narrative_height = _narrative_panel_height(
        narrative_lines,
        fonts["narrative"],
    )

    canvas_height = (
        TOP_MARGIN
        + title_area_height
        + one_section_height * 3
        + narrative_height
        + footer_height
        + BOTTOM_MARGIN
    )

    image, draw = create_canvas(
        width=canvas_width,
        height=canvas_height,
        background=BACKGROUND,
    )

    title = "Auberry Daily Sales Report"
    title_width = get_text_width(
        draw=draw,
        text=title,
        font=fonts["title"],
    )

    draw.text(
        ((canvas_width - title_width) // 2, TOP_MARGIN),
        title,
        font=fonts["title"],
        fill=TEXT,
    )

    subtitle = (
        f"Yesterday: {labels['yesterday_full']}  |  "
        f"Sales & APT values in ₹"
    )

    subtitle_width = get_text_width(
        draw=draw,
        text=subtitle,
        font=fonts["subtitle"],
    )

    draw.text(
        (
            (canvas_width - subtitle_width) // 2,
            TOP_MARGIN + 68,
        ),
        subtitle,
        font=fonts["subtitle"],
        fill=MUTED,
    )

    top = TOP_MARGIN + title_area_height

    top = _draw_section(
        draw=draw,
        top=top,
        canvas_width=canvas_width,
        rows=sections["yesterday"]["rows"],
        section_title="Yesterday Performance",
        section_subtitle=(
            f"{labels['yesterday_full']} vs "
            f"{labels['lwsd_full']}"
        ),
        metrics=[
            ("sales", "Sales"),
            ("transactions", "Txns"),
            ("apt", "APT"),
        ],
        current_label=labels["yesterday_short"],
        comparison_label="LWSD " + labels["lwsd_short"],
        fonts=fonts,
    )

    top = _draw_section(
        draw=draw,
        top=top,
        canvas_width=canvas_width,
        rows=sections["mtd_total"]["rows"],
        section_title="MTD Total Performance",
        section_subtitle=(
            f"{labels['mtd_range']} vs "
            f"{labels['lmtd_range']}"
        ),
        metrics=[
            ("sales", "Sales"),
            ("transactions", "Txns"),
            ("apt", "APT"),
        ],
        current_label="MTD " + labels["mtd_short"],
        comparison_label="LMTD " + labels["lmtd_short"],
        fonts=fonts,
    )

    top = _draw_section(
        draw=draw,
        top=top,
        canvas_width=canvas_width,
        rows=sections["mtd_kpis"]["rows"],
        section_title="MTD Operating KPIs",
        section_subtitle=(
            f"{labels['mtd_range']} vs "
            f"{labels['lmtd_range']}"
        ),
        metrics=[
            ("ads", "ADS"),
            ("adt", "ADT"),
            ("apt", "APT"),
        ],
        current_label="MTD " + labels["mtd_short"],
        comparison_label="LMTD " + labels["lmtd_short"],
        fonts=fonts,
    )

    top = _draw_narrative_panel(
        draw=draw,
        top=top,
        canvas_width=canvas_width,
        lines=narrative_lines,
        fonts=fonts,
    )

    footnote = (
        "LWSD = same weekday last week  |  "
        "LMTD = same date range last month  |  "
        "ADS = Avg Daily Sales  |  ADT = Avg Daily Txns  |  "
        "APT = Avg Per Transaction"
    )

    draw.text(
        (
            LEFT_MARGIN,
            min(
                top,
                canvas_height - BOTTOM_MARGIN - footer_height,
            ),
        ),
        footnote,
        font=fonts["footnote"],
        fill=MUTED,
    )

    output_path = REPORTS_DIRECTORY / file_name

    save_png(
        image=image,
        file_path=output_path,
    )

    return {
        "file_path": str(output_path),
        "width": canvas_width,
        "height": canvas_height,
    }
