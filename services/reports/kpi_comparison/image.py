from datetime import datetime
from pathlib import Path
from uuid import uuid4

from PIL import ImageDraw

from services.presentation.image_engine import (
    create_canvas,
    draw_right_aligned_text,
    draw_table_row,
    load_font,
    save_png,
)


PROJECT_ROOT = Path(__file__).resolve().parents[3]
REPORTS_DIRECTORY = PROJECT_ROOT / "static" / "reports"


# =========================================================
# FORMATTING HELPERS
# =========================================================


def _format_date(
    date_text: str,
) -> str:
    """
    Convert YYYY-MM-DD into DD-Mmm-YYYY.
    """
    date_value = datetime.strptime(
        date_text,
        "%Y-%m-%d",
    )

    return date_value.strftime(
        "%d-%b-%Y"
    )


def _format_indian_number(
    value: float,
) -> str:
    """
    Format a number using the Indian comma system.

    Example:
        2180387 -> 21,80,387
    """
    number = int(
        round(float(value))
    )

    sign = (
        "-"
        if number < 0
        else ""
    )

    digits = str(
        abs(number)
    )

    if len(digits) <= 3:
        return sign + digits

    last_three = digits[-3:]
    remaining = digits[:-3]

    groups = []

    while len(remaining) > 2:
        groups.insert(
            0,
            remaining[-2:],
        )

        remaining = (
            remaining[:-2]
        )

    if remaining:
        groups.insert(
            0,
            remaining,
        )

    return (
        sign
        + ",".join(
            groups
            + [last_three]
        )
    )


def _format_decimal(
    value: float,
) -> str:
    """
    Show ADT with one decimal.

    Zero remains 0.
    """
    numeric_value = float(value)

    if numeric_value == 0:
        return "0"

    return f"{numeric_value:.1f}"


def _format_percentage(
    value: float,
) -> str:
    """
    Format percentage with explicit positive or negative sign.
    """
    numeric_value = float(value)

    return f"{numeric_value:+.1f}%"


def _percentage_colour(
    value: float,
) -> str:
    """
    Positive = green
    Negative = red
    Zero = neutral dark
    """
    numeric_value = float(value)

    if numeric_value > 0:
        return "#15803D"

    if numeric_value < 0:
        return "#B91C1C"

    return "#374151"


def _format_metric_value(
    metric_name: str,
    value: float,
) -> str:
    """
    Apply the correct display format to each KPI.
    """
    if metric_name == "ads":
        return _format_indian_number(
            value
        )

    if metric_name == "adt":
        return _format_decimal(
            value
        )

    if metric_name == "apt":
        return _format_indian_number(
            value
        )

    return str(value)


def _format_missing_dates(
    missing_dates: list[str],
) -> str:
    """
    Convert missing dates from YYYY-MM-DD
    to DD Mon YYYY.
    """
    return ", ".join(
        datetime.strptime(
            date_text,
            "%Y-%m-%d",
        ).strftime(
            "%d %b %Y"
        )
        for date_text in missing_dates
    )


def _wrap_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    maximum_width: int,
) -> list[str]:
    """
    Wrap text so warning messages remain within the box.
    """
    words = text.split()

    if not words:
        return [""]

    lines = []
    current_line = words[0]

    for word in words[1:]:
        test_line = (
            f"{current_line} {word}"
        )

        text_box = draw.textbbox(
            (0, 0),
            test_line,
            font=font,
        )

        text_width = (
            text_box[2]
            - text_box[0]
        )

        if text_width <= maximum_width:
            current_line = test_line

        else:
            lines.append(
                current_line
            )

            current_line = word

    lines.append(
        current_line
    )

    return lines


# =========================================================
# DRAWING HELPERS
# =========================================================


def _draw_centred_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    left_x: int,
    right_x: int,
    y: int,
    font,
    fill: str,
) -> None:
    """
    Draw text centred within a horizontal area.
    """
    centre_x = (
        left_x
        + right_x
    ) // 2

    draw.text(
        (
            centre_x,
            y,
        ),
        text,
        font=font,
        fill=fill,
        anchor="ma",
    )


def _draw_vertical_divider(
    draw: ImageDraw.ImageDraw,
    x: int,
    top: int,
    bottom: int,
    colour: str,
    width: int = 1,
) -> None:
    draw.line(
        (
            x,
            top,
            x,
            bottom,
        ),
        fill=colour,
        width=width,
    )


def _draw_horizontal_divider(
    draw: ImageDraw.ImageDraw,
    left: int,
    right: int,
    y: int,
    colour: str,
    width: int = 1,
) -> None:
    draw.line(
        (
            left,
            y,
            right,
            y,
        ),
        fill=colour,
        width=width,
    )


# =========================================================
# MAIN IMAGE GENERATOR
# =========================================================


def generate_kpi_period_comparison_image(
    report: dict,
) -> dict:
    """
    Generate a WhatsApp-readable PNG containing:

    - DINE-IN comparison
    - DELIVERY comparison
    - OVERALL comparison
    - ADS, ADT and APT
    - From value
    - To value
    - Percentage change
    - Missing-date status
    """
    REPORTS_DIRECTORY.mkdir(
        parents=True,
        exist_ok=True,
    )

    from_period = report[
        "from_period"
    ]

    to_period = report[
        "to_period"
    ]

    sections = report[
        "sections"
    ]

    from_start = _format_date(
        from_period["start_date"]
    )

    from_end = _format_date(
        from_period["end_date"]
    )

    to_start = _format_date(
        to_period["start_date"]
    )

    to_end = _format_date(
        to_period["end_date"]
    )

    # -----------------------------------------------------
    # CANVAS AND SPACING
    # -----------------------------------------------------

    image_width = 2600

    left_margin = 85
    right_margin = 85

    title_y = 58
    subtitle_y = 132

    period_card_top = 190
    period_card_height = 118

    first_section_top = 355

    section_title_height = 68
    metric_title_height = 52
    column_header_height = 66
    row_height = 62
    total_height = 72
    section_gap = 68

    legend_height = 110
    status_gap = 34
    status_height = 225
    bottom_margin = 60

    number_of_rows = sum(
        len(section["rows"])
        for section in sections
    )

    sections_height = (
        len(sections)
        * (
            section_title_height
            + metric_title_height
            + column_header_height
            + total_height
        )
        + number_of_rows
        * row_height
        + (
            len(sections) - 1
        )
        * section_gap
    )

    image_height = (
        first_section_top
        + sections_height
        + legend_height
        + status_gap
        + status_height
        + bottom_margin
    )

    image, draw = create_canvas(
        width=image_width,
        height=image_height,
        background="#F8FAFC",
    )

    # -----------------------------------------------------
    # FONTS
    # -----------------------------------------------------

    title_font = load_font(
        size=58,
        bold=True,
    )

    subtitle_font = load_font(
        size=27,
    )

    period_label_font = load_font(
        size=27,
        bold=True,
    )

    period_value_font = load_font(
        size=27,
    )

    section_title_font = load_font(
        size=35,
        bold=True,
    )

    metric_title_font = load_font(
        size=29,
        bold=True,
    )

    header_font = load_font(
        size=25,
        bold=True,
    )

    body_font = load_font(
        size=25,
    )

    percentage_font = load_font(
        size=25,
        bold=True,
    )

    total_font = load_font(
        size=28,
        bold=True,
    )

    legend_font = load_font(
        size=23,
    )

    status_heading_font = load_font(
        size=32,
        bold=True,
    )

    status_body_font = load_font(
        size=26,
    )

    # -----------------------------------------------------
    # COLOURS
    # -----------------------------------------------------

    title_colour = "#0F172A"
    text_colour = "#1E293B"
    muted_colour = "#475569"

    card_background = "#FFFFFF"
    card_border = "#CBD5E1"

    section_background = "#1F3A60"
    section_text_colour = "#FFFFFF"

    metric_background = "#EFF4FA"
    header_background = "#DFE8F4"

    white_row = "#FFFFFF"
    alternate_row = "#F4F7FA"

    total_background = "#D6DEE9"
    total_border = "#334155"

    grid_colour = "#CBD5E1"
    metric_divider_colour = "#94A3B8"

    success_background = "#DCFCE7"
    success_border = "#86EFAC"
    success_colour = "#166534"

    warning_background = "#FEF3C7"
    warning_border = "#FCD34D"
    warning_colour = "#92400E"

    # -----------------------------------------------------
    # TITLE
    # -----------------------------------------------------

    draw.text(
        (
            image_width // 2,
            title_y,
        ),
        "STORE PERFORMANCE COMPARISON",
        font=title_font,
        fill=title_colour,
        anchor="ma",
    )

    draw.text(
        (
            image_width // 2,
            subtitle_y,
        ),
        (
            "Comparative view of store-level "
            "ADS, ADT and APT"
        ),
        font=subtitle_font,
        fill=muted_colour,
        anchor="ma",
    )

    # -----------------------------------------------------
    # PERIOD CARD
    # -----------------------------------------------------

    period_card_left = 455
    period_card_right = (
        image_width - 455
    )

    period_card_bottom = (
        period_card_top
        + period_card_height
    )

    draw.rounded_rectangle(
        (
            period_card_left,
            period_card_top,
            period_card_right,
            period_card_bottom,
        ),
        radius=20,
        fill=card_background,
        outline=card_border,
        width=2,
    )

    label_x = (
        period_card_left + 55
    )

    value_x = (
        period_card_left + 275
    )

    first_period_y = (
        period_card_top + 20
    )

    second_period_y = (
        period_card_top + 67
    )

    draw.text(
        (
            label_x,
            first_period_y,
        ),
        "From Period:",
        font=period_label_font,
        fill=title_colour,
    )

    draw.text(
        (
            value_x,
            first_period_y,
        ),
        (
            f"{from_start} to {from_end}"
        ),
        font=period_value_font,
        fill=text_colour,
    )

    draw.text(
        (
            label_x,
            second_period_y,
        ),
        "To Period:",
        font=period_label_font,
        fill=title_colour,
    )

    draw.text(
        (
            value_x,
            second_period_y,
        ),
        (
            f"{to_start} to {to_end}"
        ),
        font=period_value_font,
        fill=text_colour,
    )

    # -----------------------------------------------------
    # TABLE DIMENSIONS
    # -----------------------------------------------------

    table_left = left_margin
    table_right = (
        image_width - right_margin
    )

    table_width = (
        table_right - table_left
    )

    store_width = 400

    metric_group_width = (
        table_width - store_width
    ) // 3

    sub_column_width = (
        metric_group_width // 3
    )

    store_left = table_left
    store_right = (
        table_left + store_width
    )

    metric_names = [
        ("ADS", "ads"),
        ("ADT", "adt"),
        ("APT", "apt"),
    ]

    current_y = first_section_top

    # -----------------------------------------------------
    # SECTIONS
    # -----------------------------------------------------

    for section_index, section in enumerate(
        sections
    ):
        section_top = current_y

        section_bottom = (
            section_top
            + section_title_height
        )

        draw.rounded_rectangle(
            (
                table_left,
                section_top,
                table_right,
                section_bottom,
            ),
            radius=13,
            fill=section_background,
        )

        draw.text(
            (
                table_left + 28,
                section_top + 15,
            ),
            section["name"],
            font=section_title_font,
            fill=section_text_colour,
        )

        current_y = section_bottom

        # ---------------------------------------------
        # METRIC GROUP HEADINGS
        # ---------------------------------------------

        metric_title_bottom = (
            current_y
            + metric_title_height
        )

        draw.rectangle(
            (
                table_left,
                current_y,
                table_right,
                metric_title_bottom,
            ),
            fill=metric_background,
        )

        draw.text(
            (
                store_left + 18,
                current_y + 13,
            ),
            "Store",
            font=metric_title_font,
            fill=title_colour,
        )

        for metric_index, (
            metric_label,
            _,
        ) in enumerate(metric_names):
            metric_left = (
                store_right
                + metric_index
                * metric_group_width
            )

            metric_right = (
                metric_left
                + metric_group_width
            )

            _draw_centred_text(
                draw=draw,
                text=metric_label,
                left_x=metric_left,
                right_x=metric_right,
                y=current_y + 12,
                font=metric_title_font,
                fill=title_colour,
            )

            if metric_index > 0:
                _draw_vertical_divider(
                    draw=draw,
                    x=metric_left,
                    top=current_y,
                    bottom=metric_title_bottom,
                    colour=metric_divider_colour,
                    width=2,
                )

        _draw_horizontal_divider(
            draw=draw,
            left=table_left,
            right=table_right,
            y=metric_title_bottom,
            colour=grid_colour,
            width=2,
        )

        current_y = metric_title_bottom

        # ---------------------------------------------
        # COLUMN HEADINGS
        # ---------------------------------------------

        header_bottom = (
            current_y
            + column_header_height
        )

        draw_table_row(
            draw=draw,
            left=table_left,
            top=current_y,
            right=table_right,
            bottom=header_bottom,
            background=header_background,
            border_colour=grid_colour,
            border_width=1,
        )

        headings = [
            "From",
            "To",
            "% Change",
        ]

        for metric_index in range(3):
            metric_left = (
                store_right
                + metric_index
                * metric_group_width
            )

            for sub_index, heading in enumerate(
                headings
            ):
                sub_left = (
                    metric_left
                    + sub_index
                    * sub_column_width
                )

                sub_right = (
                    sub_left
                    + sub_column_width
                )

                _draw_centred_text(
                    draw=draw,
                    text=heading,
                    left_x=sub_left,
                    right_x=sub_right,
                    y=current_y + 18,
                    font=header_font,
                    fill=title_colour,
                )

                if sub_index > 0:
                    _draw_vertical_divider(
                        draw=draw,
                        x=sub_left,
                        top=current_y,
                        bottom=header_bottom,
                        colour=grid_colour,
                    )

            if metric_index > 0:
                _draw_vertical_divider(
                    draw=draw,
                    x=metric_left,
                    top=current_y,
                    bottom=header_bottom,
                    colour=metric_divider_colour,
                    width=2,
                )

        current_y = header_bottom

        # ---------------------------------------------
        # STORE ROWS
        # ---------------------------------------------

        for row_index, row in enumerate(
            section["rows"]
        ):
            row_bottom = (
                current_y + row_height
            )

            row_background = (
                alternate_row
                if row_index % 2 == 1
                else white_row
            )

            draw_table_row(
                draw=draw,
                left=table_left,
                top=current_y,
                right=table_right,
                bottom=row_bottom,
                background=row_background,
                border_colour=grid_colour,
                border_width=1,
            )

            body_y = (
                current_y + 17
            )

            draw.text(
                (
                    store_left + 18,
                    body_y,
                ),
                str(row["store"]),
                font=body_font,
                fill=text_colour,
            )

            for metric_index, (
                _,
                metric_key,
            ) in enumerate(metric_names):
                metric_left = (
                    store_right
                    + metric_index
                    * metric_group_width
                )

                metric_data = row[
                    metric_key
                ]

                display_values = [
                    _format_metric_value(
                        metric_key,
                        metric_data["from"],
                    ),
                    _format_metric_value(
                        metric_key,
                        metric_data["to"],
                    ),
                    _format_percentage(
                        metric_data[
                            "percentage_change"
                        ]
                    ),
                ]

                for sub_index, display_value in enumerate(
                    display_values
                ):
                    sub_left = (
                        metric_left
                        + sub_index
                        * sub_column_width
                    )

                    sub_right = (
                        sub_left
                        + sub_column_width
                    )

                    value_colour = (
                        _percentage_colour(
                            metric_data[
                                "percentage_change"
                            ]
                        )
                        if sub_index == 2
                        else text_colour
                    )

                    value_font = (
                        percentage_font
                        if sub_index == 2
                        else body_font
                    )

                    draw_right_aligned_text(
                        draw=draw,
                        text=display_value,
                        right_x=(
                            sub_right - 18
                        ),
                        y=body_y,
                        font=value_font,
                        fill=value_colour,
                    )

                    if sub_index > 0:
                        _draw_vertical_divider(
                            draw=draw,
                            x=sub_left,
                            top=current_y,
                            bottom=row_bottom,
                            colour=grid_colour,
                        )

                if metric_index > 0:
                    _draw_vertical_divider(
                        draw=draw,
                        x=metric_left,
                        top=current_y,
                        bottom=row_bottom,
                        colour=metric_divider_colour,
                        width=2,
                    )

            current_y = row_bottom

        # ---------------------------------------------
        # TOTAL ROW
        # ---------------------------------------------

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
            border_colour=total_border,
            border_width=2,
        )

        total_y = (
            current_y + 20
        )

        draw.text(
            (
                store_left + 18,
                total_y,
            ),
            "TOTAL",
            font=total_font,
            fill=title_colour,
        )

        total = section["total"]

        for metric_index, (
            _,
            metric_key,
        ) in enumerate(metric_names):
            metric_left = (
                store_right
                + metric_index
                * metric_group_width
            )

            metric_data = total[
                metric_key
            ]

            total_values = [
                _format_metric_value(
                    metric_key,
                    metric_data["from"],
                ),
                _format_metric_value(
                    metric_key,
                    metric_data["to"],
                ),
                _format_percentage(
                    metric_data[
                        "percentage_change"
                    ]
                ),
            ]

            for sub_index, display_value in enumerate(
                total_values
            ):
                sub_left = (
                    metric_left
                    + sub_index
                    * sub_column_width
                )

                sub_right = (
                    sub_left
                    + sub_column_width
                )

                value_colour = (
                    _percentage_colour(
                        metric_data[
                            "percentage_change"
                        ]
                    )
                    if sub_index == 2
                    else title_colour
                )

                draw_right_aligned_text(
                    draw=draw,
                    text=display_value,
                    right_x=(
                        sub_right - 18
                    ),
                    y=total_y,
                    font=total_font,
                    fill=value_colour,
                )

                if sub_index > 0:
                    _draw_vertical_divider(
                        draw=draw,
                        x=sub_left,
                        top=current_y,
                        bottom=total_bottom,
                        colour=metric_divider_colour,
                    )

            if metric_index > 0:
                _draw_vertical_divider(
                    draw=draw,
                    x=metric_left,
                    top=current_y,
                    bottom=total_bottom,
                    colour=total_border,
                    width=2,
                )

        current_y = total_bottom

        if section_index < (
            len(sections) - 1
        ):
            current_y += section_gap

    # -----------------------------------------------------
    # KPI LEGEND
    # -----------------------------------------------------

    legend_y = (
        current_y + 34
    )

    draw.text(
        (
            table_left,
            legend_y,
        ),
        (
            "ADS = Average Daily Sales     "
            "ADT = Average Daily Transactions     "
            "APT = Average Per Transaction"
        ),
        font=legend_font,
        fill=muted_colour,
    )

    # -----------------------------------------------------
    # DATA STATUS
    # -----------------------------------------------------

    status_top = (
        current_y
        + legend_height
        + status_gap
    )

    status_bottom = (
        status_top + status_height
    )

    if report["data_complete"]:
        draw.rounded_rectangle(
            (
                table_left,
                status_top,
                table_right,
                status_bottom,
            ),
            radius=24,
            fill=success_background,
            outline=success_border,
            width=2,
        )

        draw.text(
            (
                table_left + 36,
                status_top + 30,
            ),
            "Data Status",
            font=status_heading_font,
            fill=success_colour,
        )

        draw.text(
            (
                table_left + 36,
                status_top + 102,
            ),
            (
                "Sales data is available for every date "
                "in both comparison periods."
            ),
            font=status_body_font,
            fill=success_colour,
        )

    else:
        warning_lines = []

        if not from_period[
            "data_complete"
        ]:
            warning_lines.append(
                (
                    "From Period missing dates: "
                    + _format_missing_dates(
                        from_period[
                            "missing_dates"
                        ]
                    )
                )
            )

        if not to_period[
            "data_complete"
        ]:
            warning_lines.append(
                (
                    "To Period missing dates: "
                    + _format_missing_dates(
                        to_period[
                            "missing_dates"
                        ]
                    )
                )
            )

        warning_text = "   |   ".join(
            warning_lines
        )

        wrapped_warning_lines = _wrap_text(
            draw=draw,
            text=warning_text,
            font=status_body_font,
            maximum_width=(
                table_width - 72
            ),
        )

        draw.rounded_rectangle(
            (
                table_left,
                status_top,
                table_right,
                status_bottom,
            ),
            radius=24,
            fill=warning_background,
            outline=warning_border,
            width=2,
        )

        draw.text(
            (
                table_left + 36,
                status_top + 28,
            ),
            "Data Warning",
            font=status_heading_font,
            fill=warning_colour,
        )

        warning_y = (
            status_top + 94
        )

        for warning_line in wrapped_warning_lines:
            draw.text(
                (
                    table_left + 36,
                    warning_y,
                ),
                warning_line,
                font=status_body_font,
                fill=warning_colour,
            )

            warning_y += 38

    # -----------------------------------------------------
    # SAVE IMAGE
    # -----------------------------------------------------

    filename = (
        "kpi_period_comparison_"
        f"{uuid4().hex}.png"
    )

    file_path = (
        REPORTS_DIRECTORY
        / filename
    )

    save_png(
        image=image,
        file_path=file_path,
    )

    return {
        "filename": filename,
        "file_path": str(
            file_path
        ),
        "relative_url": (
            f"/static/reports/{filename}"
        ),
    }