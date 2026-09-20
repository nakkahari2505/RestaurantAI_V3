from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PIL import ImageDraw

from services.presentation.image_engine import (
    create_canvas,
    draw_right_aligned_text,
    draw_status_box,
    draw_table_row,
    load_font,
    save_png,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIRECTORY = PROJECT_ROOT / "static" / "reports"


def _format_report_date(date_text: str) -> str:
    date_value = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    return date_value.strftime("%d %b %Y")


def _format_indian_number(value: float) -> str:
    number = int(round(float(value)))
    sign = "-" if number < 0 else ""
    digits = str(abs(number))

    if len(digits) <= 3:
        return sign + digits

    last_three = digits[-3:]
    remaining = digits[:-3]
    groups = []

    while len(remaining) > 2:
        groups.insert(0, remaining[-2:])
        remaining = remaining[:-2]

    if remaining:
        groups.insert(0, remaining)

    return sign + ",".join(
        groups + [last_three]
    )


def _format_decimal(value: float) -> str:
    numeric_value = float(value)

    if numeric_value.is_integer():
        return str(int(numeric_value))

    return f"{numeric_value:.1f}"


def _format_missing_dates(
    missing_dates: list[str],
) -> str:
    return ", ".join(
        _format_report_date(date_text)
        for date_text in missing_dates
    )


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    maximum_width: int,
) -> list[str]:
    words = text.split()

    if not words:
        return [""]

    lines = []
    current_line = words[0]

    for word in words[1:]:
        test_line = f"{current_line} {word}"

        text_box = draw.textbbox(
            (0, 0),
            test_line,
            font=font,
        )

        text_width = (
            text_box[2] - text_box[0]
        )

        if text_width <= maximum_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word

    lines.append(current_line)

    return lines


def generate_sales_for_a_period_image(
    report: dict,
) -> dict:
    """
    Generate the complete Sales for a Period report as a PNG.

    All mapped stores are retained, including stores with
    zero Sales and zero Transactions for the selected period.
    """
    REPORTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    start_date = _format_report_date(
        report["start_date"]
    )

    end_date = _format_report_date(
        report["end_date"]
    )

    rows = report["rows"]
    total = report["total"]

    image_width = 1600

    left_margin = 70
    right_margin = 70

    title_y = 52
    period_y = 120
    table_top = 205

    header_height = 70
    row_height = 66
    total_height = 74

    legend_top_padding = 36
    legend_height = 105

    status_top_padding = 38
    status_height = 165

    image_height = (
        table_top
        + header_height
        + (len(rows) * row_height)
        + total_height
        + legend_top_padding
        + legend_height
        + status_top_padding
        + status_height
        + 40
    )

    image, draw = create_canvas(
        width=image_width,
        height=image_height,
        background="white",
    )

    title_font = load_font(
        size=44,
        bold=True,
    )

    period_font = load_font(
        size=30,
    )

    header_font = load_font(
        size=27,
        bold=True,
    )

    row_font = load_font(
        size=27,
    )

    total_font = load_font(
        size=29,
        bold=True,
    )

    legend_font = load_font(
        size=23,
    )

    status_heading_font = load_font(
        size=28,
        bold=True,
    )

    status_font = load_font(
        size=24,
    )

    title_colour = "#111827"
    text_colour = "#1F2937"
    muted_colour = "#4B5563"

    # Slightly darker than the previous version.
    border_colour = "#94A3B8"

    header_background = "#E8F0FE"
    alternate_row_background = "#F8FAFC"
    total_background = "#E2E8F0"

    success_background = "#DCFCE7"
    success_colour = "#166534"

    warning_background = "#FEF3C7"
    warning_colour = "#92400E"

    draw.text(
        (left_margin, title_y),
        "Sales Performance",
        font=title_font,
        fill=title_colour,
    )

    draw.text(
        (left_margin, period_y),
        (
            f"Time Period: "
            f"{start_date} to {end_date}"
        ),
        font=period_font,
        fill=muted_colour,
    )

    table_left = left_margin
    table_right = image_width - right_margin
    table_width = table_right - table_left

    column_widths = [
        390,  # Store
        255,  # Total Sales
        185,  # Total Txns
        240,  # ADS
        170,  # ADT
        220,  # APT
    ]

    if sum(column_widths) != table_width:
        raise ValueError(
            "Table column widths do not match "
            "the available image width."
        )

    column_lefts = [table_left]

    for width in column_widths[:-1]:
        column_lefts.append(
            column_lefts[-1] + width
        )

    column_rights = [
        column_lefts[index]
        + column_widths[index]
        for index in range(
            len(column_widths)
        )
    ]

    header_bottom = (
        table_top + header_height
    )

    draw_table_row(
        draw=draw,
        left=table_left,
        top=table_top,
        right=table_right,
        bottom=header_bottom,
        background=header_background,
        border_colour=border_colour,
        border_width=2,
    )

    headers = [
        "Store",
        "Total Sales",
        "Total Txns",
        "ADS",
        "ADT",
        "APT",
    ]

    header_text_y = table_top + 17

    draw.text(
        (
            column_lefts[0] + 18,
            header_text_y,
        ),
        headers[0],
        font=header_font,
        fill=title_colour,
    )

    for column_index in range(
        1,
        len(headers),
    ):
        draw_right_aligned_text(
            draw=draw,
            text=headers[column_index],
            right_x=(
                column_rights[column_index]
                - 18
            ),
            y=header_text_y,
            font=header_font,
            fill=title_colour,
        )

    current_y = header_bottom

    for row_index, row in enumerate(rows):
        row_bottom = (
            current_y + row_height
        )

        row_background = (
            alternate_row_background
            if row_index % 2 == 1
            else "white"
        )

        draw_table_row(
            draw=draw,
            left=table_left,
            top=current_y,
            right=table_right,
            bottom=row_bottom,
            background=row_background,
            border_colour=border_colour,
            border_width=1,
        )

        text_y = current_y + 16

        draw.text(
            (
                column_lefts[0] + 18,
                text_y,
            ),
            str(row["store"]),
            font=row_font,
            fill=text_colour,
        )

        values = [
            _format_indian_number(
                row["total_sales"]
            ),
            _format_indian_number(
                row["total_txns"]
            ),
            _format_indian_number(
                row["ads"]
            ),
            _format_decimal(
                row["adt"]
            ),
            _format_indian_number(
                row["apt"]
            ),
        ]

        for value_index, value in enumerate(
            values,
            start=1,
        ):
            draw_right_aligned_text(
                draw=draw,
                text=value,
                right_x=(
                    column_rights[value_index]
                    - 18
                ),
                y=text_y,
                font=row_font,
                fill=text_colour,
            )

        current_y = row_bottom

    total_bottom = (
        current_y + total_height
    )

    draw_table_row(
        draw=draw,
        left=table_left,
        top=current_y,
        right=table_right,
        bottom=total_bottom,
        background=total_background,
        border_colour=border_colour,
        border_width=2,
    )

    total_text_y = current_y + 18

    draw.text(
        (
            column_lefts[0] + 18,
            total_text_y,
        ),
        "TOTAL",
        font=total_font,
        fill=title_colour,
    )

    total_values = [
        _format_indian_number(
            total["total_sales"]
        ),
        _format_indian_number(
            total["total_txns"]
        ),
        _format_indian_number(
            total["ads"]
        ),
        _format_decimal(
            total["adt"]
        ),
        _format_indian_number(
            total["apt"]
        ),
    ]

    for value_index, value in enumerate(
        total_values,
        start=1,
    ):
        draw_right_aligned_text(
            draw=draw,
            text=value,
            right_x=(
                column_rights[value_index]
                - 18
            ),
            y=total_text_y,
            font=total_font,
            fill=title_colour,
        )

    legend_top = (
        total_bottom
        + legend_top_padding
    )

    draw.text(
        (
            table_left,
            legend_top,
        ),
        (
            "ADS = Average Daily Sales    "
            "ADT = Average Daily Transactions    "
            "APT = Average Per Transaction"
        ),
        font=legend_font,
        fill=muted_colour,
    )

    status_top = (
        legend_top
        + legend_height
        + status_top_padding
    )

    status_bottom = (
        status_top + status_height
    )

    if report["data_complete"]:
        draw_status_box(
            draw=draw,
            left=table_left,
            top=status_top,
            right=table_right,
            bottom=status_bottom,
            heading="Data Status",
            message=(
                "Sales data is available "
                "for all dates in the "
                "selected period."
            ),
            heading_font=status_heading_font,
            message_font=status_font,
            background=success_background,
            text_colour=success_colour,
        )

    else:
        missing_dates_text = (
            _format_missing_dates(
                report["missing_dates"]
            )
        )

        warning_text = (
            "Sales data is not available "
            f"for: {missing_dates_text}"
        )

        warning_lines = _wrap_text(
            draw=draw,
            text=warning_text,
            font=status_font,
            maximum_width=(
                table_width - 56
            ),
        )

        draw.rounded_rectangle(
            (
                table_left,
                status_top,
                table_right,
                status_bottom,
            ),
            radius=20,
            fill=warning_background,
        )

        draw.text(
            (
                table_left + 28,
                status_top + 22,
            ),
            "Data Warning",
            font=status_heading_font,
            fill=warning_colour,
        )

        line_y = status_top + 72

        for warning_line in warning_lines:
            draw.text(
                (
                    table_left + 28,
                    line_y,
                ),
                warning_line,
                font=status_font,
                fill=warning_colour,
            )

            line_y += 34

    filename = (
        "sales_for_a_period_"
        f"{uuid4().hex}.png"
    )

    file_path = (
        REPORTS_DIRECTORY / filename
    )

    save_png(
        image=image,
        file_path=file_path,
    )

    return {
        "filename": filename,
        "file_path": str(file_path),
        "relative_url": (
            f"/static/reports/{filename}"
        ),
    }