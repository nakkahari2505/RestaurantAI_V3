from pathlib import Path
from typing import Final

from PIL import ImageDraw

from services.presentation.image_engine import (
    create_canvas,
    get_text_width,
    load_font,
    save_png,
)


# =========================================================
# OUTPUT
# =========================================================

PROJECT_ROOT: Final[Path] = (
    Path(__file__).resolve().parents[2]
)

REPORTS_DIRECTORY: Final[Path] = (
    PROJECT_ROOT / "reports"
)


# =========================================================
# PRESENTATION CONSTANTS
# =========================================================

BACKGROUND: Final[str] = "white"
TEXT: Final[str] = "#222222"
MUTED_TEXT: Final[str] = "#666666"
HEADER_BACKGROUND: Final[str] = "#EAF0FF"
SUBTOTAL_BACKGROUND: Final[str] = "#F7F8FA"
TOTAL_BACKGROUND: Final[str] = "#EEF1F5"
ALTERNATE_ROW_BACKGROUND: Final[str] = "#FCFCFC"
BORDER: Final[str] = "#D0D5DD"

TITLE_FONT_SIZE: Final[int] = 38
SUBTITLE_FONT_SIZE: Final[int] = 22
HEADER_FONT_SIZE: Final[int] = 20
BODY_FONT_SIZE: Final[int] = 20
TOTAL_FONT_SIZE: Final[int] = 20

LEFT_PADDING: Final[int] = 34
RIGHT_PADDING: Final[int] = 34
TOP_PADDING: Final[int] = 26
BOTTOM_PADDING: Final[int] = 30

ROW_DIMENSION_WIDTH: Final[int] = 250
VALUE_COLUMN_WIDTH: Final[int] = 180
TOTAL_COLUMN_WIDTH: Final[int] = 190

TITLE_AREA_HEIGHT: Final[int] = 120
HEADER_HEIGHT: Final[int] = 82
ROW_HEIGHT: Final[int] = 56

ADDITIVE_METRICS: Final[set[str]] = {
    "sales",
    "quantity",
    "transactions",
}


# =========================================================
# DISPLAY NAMES
# =========================================================

METRIC_DISPLAY_NAMES = {
    "sales": "Sales",
    "quantity": "Quantity Sold",
    "transactions": "Transactions",
    "ads": "Average Daily Sales",
    "adt": "Average Daily Transactions",
    "apt": "Average Per Transaction",
}

DIMENSION_DISPLAY_NAMES = {
    "store": "Store",
    "channel": "Channel",
    "aggregator": "Aggregator",
    "category": "Category",
    "item": "Item",
}


# =========================================================
# FORMATTING
# =========================================================


def _format_indian_number(
    value: float,
) -> str:
    number = int(
        round(
            float(value)
        )
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
        remaining = remaining[:-2]

    if remaining:
        groups.insert(
            0,
            remaining,
        )

    return (
        sign
        + ",".join(
            groups
            + [
                last_three,
            ]
        )
    )


def _format_decimal(
    value: float,
) -> str:
    numeric_value = float(value)

    if numeric_value.is_integer():
        return str(
            int(numeric_value)
        )

    return f"{numeric_value:.1f}"


def _format_metric_value(
    metric_name: str,
    value: float,
) -> str:
    normalized_metric = (
        str(metric_name)
        .strip()
        .lower()
    )

    if normalized_metric == "adt":
        return _format_decimal(value)

    # ₹ is shown once in the subtitle for sales so that a
    # wide pivot remains clean and compact.
    return _format_indian_number(value)


def _metric_display_name(
    metric_name: str,
) -> str:
    normalized = (
        str(metric_name)
        .strip()
        .lower()
    )

    return METRIC_DISPLAY_NAMES.get(
        normalized,
        normalized.title(),
    )


def _dimension_display_name(
    dimension_name: str,
) -> str:
    normalized = (
        str(dimension_name)
        .strip()
        .lower()
    )

    return DIMENSION_DISPLAY_NAMES.get(
        normalized,
        normalized.title(),
    )


# =========================================================
# DRAWING HELPERS
# =========================================================


def _truncate_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font,
    max_width: int,
) -> str:
    cleaned = str(text)

    if get_text_width(
        draw=draw,
        text=cleaned,
        font=font,
    ) <= max_width:
        return cleaned

    ellipsis = "…"

    while cleaned:
        candidate = cleaned + ellipsis

        if get_text_width(
            draw=draw,
            text=candidate,
            font=font,
        ) <= max_width:
            return candidate

        cleaned = cleaned[:-1]

    return ellipsis


def _draw_cell_text_left(
    draw: ImageDraw.ImageDraw,
    text: str,
    left: int,
    top: int,
    width: int,
    height: int,
    font,
    fill: str = TEXT,
) -> None:
    cleaned = _truncate_text(
        draw=draw,
        text=text,
        font=font,
        max_width=width - 20,
    )

    box = draw.textbbox(
        (0, 0),
        cleaned,
        font=font,
    )

    text_height = box[3] - box[1]

    draw.text(
        (
            left + 10,
            top
            + (height - text_height) // 2
            - 2,
        ),
        cleaned,
        font=font,
        fill=fill,
    )


def _draw_cell_text_right(
    draw: ImageDraw.ImageDraw,
    text: str,
    left: int,
    top: int,
    width: int,
    height: int,
    font,
    fill: str = TEXT,
) -> None:
    text_width = get_text_width(
        draw=draw,
        text=text,
        font=font,
    )

    box = draw.textbbox(
        (0, 0),
        text,
        font=font,
    )

    text_height = box[3] - box[1]

    draw.text(
        (
            left
            + width
            - text_width
            - 10,
            top
            + (height - text_height) // 2
            - 2,
        ),
        text,
        font=font,
        fill=fill,
    )


def _draw_header_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    left: int,
    top: int,
    width: int,
    height: int,
    font,
) -> None:
    cleaned = _truncate_text(
        draw=draw,
        text=text,
        font=font,
        max_width=width - 18,
    )

    text_width = get_text_width(
        draw=draw,
        text=cleaned,
        font=font,
    )

    box = draw.textbbox(
        (0, 0),
        cleaned,
        font=font,
    )

    text_height = box[3] - box[1]

    draw.text(
        (
            left
            + (width - text_width) // 2,
            top
            + (height - text_height) // 2
            - 2,
        ),
        cleaned,
        font=font,
        fill=TEXT,
    )


# =========================================================
# PIVOT DATA MODEL
# =========================================================


def _normalise_group_value(
    value,
) -> str:
    cleaned = str(
        value
        if value is not None
        else ""
    ).strip()

    return cleaned or "Unspecified"


def _build_pivot_data(
    pivot_spec: dict,
) -> dict:
    row_dimensions = list(
        pivot_spec.get(
            "row_dimensions",
            [],
        )
    )

    column_dimension = str(
        pivot_spec.get(
            "column_dimension",
            "",
        )
    )

    if len(row_dimensions) not in {
        1,
        2,
    }:
        raise ValueError(
            "Pivot image requires one or two row dimensions."
        )

    if not column_dimension:
        raise ValueError(
            "Pivot image requires one column dimension."
        )

    matrix = {}
    row_totals = {}
    column_totals = {}
    first_level_totals = {}

    for source_row in pivot_spec.get(
        "rows",
        [],
    ):
        groups = source_row.get(
            "groups",
            {},
        )

        row_key = tuple(
            _normalise_group_value(
                groups.get(
                    dimension,
                    "",
                )
            )
            for dimension in row_dimensions
        )

        column_key = _normalise_group_value(
            groups.get(
                column_dimension,
                "",
            )
        )

        value = float(
            source_row.get(
                "metric_value",
                0,
            )
        )

        matrix.setdefault(
            row_key,
            {},
        )

        matrix[row_key][column_key] = (
            matrix[row_key].get(
                column_key,
                0.0,
            )
            + value
        )

        row_totals[row_key] = (
            row_totals.get(
                row_key,
                0.0,
            )
            + value
        )

        column_totals[column_key] = (
            column_totals.get(
                column_key,
                0.0,
            )
            + value
        )

        first_level_key = row_key[0]

        first_level_totals[first_level_key] = (
            first_level_totals.get(
                first_level_key,
                0.0,
            )
            + value
        )

    column_keys = sorted(
        column_totals,
        key=lambda key: (
            -column_totals[key],
            str(key).lower(),
        ),
    )

    if len(row_dimensions) == 1:
        row_keys = sorted(
            matrix,
            key=lambda key: (
                -row_totals[key],
                str(key[0]).lower(),
            ),
        )
    else:
        first_level_order = sorted(
            first_level_totals,
            key=lambda key: (
                -first_level_totals[key],
                str(key).lower(),
            ),
        )

        first_level_rank = {
            value: index
            for index, value in enumerate(
                first_level_order
            )
        }

        row_keys = sorted(
            matrix,
            key=lambda key: (
                first_level_rank[
                    key[0]
                ],
                -row_totals[key],
                str(key[1]).lower(),
            ),
        )

    grand_total = sum(
        row_totals.values()
    )

    return {
        "row_dimensions": row_dimensions,
        "column_dimension": column_dimension,
        "row_keys": row_keys,
        "column_keys": column_keys,
        "matrix": matrix,
        "row_totals": row_totals,
        "column_totals": column_totals,
        "first_level_totals": first_level_totals,
        "grand_total": grand_total,
    }


# =========================================================
# PUBLIC RENDERER
# =========================================================


def generate_grouped_pivot_image(
    pivot_spec: dict,
    file_name: str = "grouped_pivot.png",
) -> dict:
    """
    Render a professional 2D/3D management pivot table.

    2D grouping:
        1 row dimension + 1 column dimension

    3D grouping:
        2 row dimensions + 1 column dimension

    If Store is part of the request, Presentation Engine places
    it as the first row dimension before this renderer is called.

    Important guardrail:
    totals are mathematically safe only for additive metrics
    (sales, quantity, transactions). Non-additive metrics are
    never summed into misleading totals.
    """
    pivot_data = _build_pivot_data(
        pivot_spec
    )

    metric_name = str(
        pivot_spec.get(
            "metric",
            "",
        )
    )

    normalized_metric = (
        metric_name
        .strip()
        .lower()
    )

    totals_enabled = (
        normalized_metric
        in ADDITIVE_METRICS
    )

    row_dimensions = (
        pivot_data[
            "row_dimensions"
        ]
    )

    column_dimension = (
        pivot_data[
            "column_dimension"
        ]
    )

    row_keys = (
        pivot_data[
            "row_keys"
        ]
    )

    column_keys = (
        pivot_data[
            "column_keys"
        ]
    )

    # For two row dimensions, insert a subtotal row after each
    # first-level group (Store subtotal when Store is present).
    subtotal_row_count = (
        len(
            {
                row_key[0]
                for row_key in row_keys
            }
        )
        if (
            len(row_dimensions) == 2
            and totals_enabled
        )
        else 0
    )

    grand_total_row_count = (
        1
        if totals_enabled
        else 0
    )

    canvas_width = (
        LEFT_PADDING
        + (
            len(row_dimensions)
            * ROW_DIMENSION_WIDTH
        )
        + (
            len(column_keys)
            * VALUE_COLUMN_WIDTH
        )
        + (
            TOTAL_COLUMN_WIDTH
            if totals_enabled
            else 0
        )
        + RIGHT_PADDING
    )

    canvas_height = (
        TOP_PADDING
        + TITLE_AREA_HEIGHT
        + HEADER_HEIGHT
        + (
            len(row_keys)
            * ROW_HEIGHT
        )
        + (
            subtotal_row_count
            * ROW_HEIGHT
        )
        + (
            grand_total_row_count
            * ROW_HEIGHT
        )
        + BOTTOM_PADDING
    )

    image, draw = create_canvas(
        width=canvas_width,
        height=canvas_height,
        background=BACKGROUND,
    )

    title_font = load_font(
        TITLE_FONT_SIZE,
        bold=True,
    )

    subtitle_font = load_font(
        SUBTITLE_FONT_SIZE
    )

    header_font = load_font(
        HEADER_FONT_SIZE,
        bold=True,
    )

    body_font = load_font(
        BODY_FONT_SIZE
    )

    total_font = load_font(
        TOTAL_FONT_SIZE,
        bold=True,
    )

    title = str(
        pivot_spec.get(
            "title",
            (
                f"{_metric_display_name(metric_name)} "
                "Pivot"
            ),
        )
    )

    subtitle = str(
        pivot_spec.get(
            "subtitle",
            "",
        )
    )

    if (
        normalized_metric == "sales"
        and "Values in ₹" not in subtitle
    ):
        subtitle = (
            f"{subtitle} | Values in ₹"
            if subtitle
            else "Values in ₹"
        )

    title_width = get_text_width(
        draw=draw,
        text=title,
        font=title_font,
    )

    draw.text(
        (
            (canvas_width - title_width) // 2,
            TOP_PADDING,
        ),
        title,
        font=title_font,
        fill=TEXT,
    )

    if subtitle:
        subtitle_width = get_text_width(
            draw=draw,
            text=subtitle,
            font=subtitle_font,
        )

        draw.text(
            (
                (canvas_width - subtitle_width) // 2,
                TOP_PADDING + 54,
            ),
            subtitle,
            font=subtitle_font,
            fill=MUTED_TEXT,
        )

    table_top = (
        TOP_PADDING
        + TITLE_AREA_HEIGHT
    )

    # =====================================================
    # HEADER
    # =====================================================

    current_x = LEFT_PADDING

    for dimension in row_dimensions:
        draw.rectangle(
            (
                current_x,
                table_top,
                current_x + ROW_DIMENSION_WIDTH,
                table_top + HEADER_HEIGHT,
            ),
            fill=HEADER_BACKGROUND,
            outline=BORDER,
            width=1,
        )

        _draw_header_text(
            draw=draw,
            text=_dimension_display_name(
                dimension
            ),
            left=current_x,
            top=table_top,
            width=ROW_DIMENSION_WIDTH,
            height=HEADER_HEIGHT,
            font=header_font,
        )

        current_x += ROW_DIMENSION_WIDTH

    for column_key in column_keys:
        draw.rectangle(
            (
                current_x,
                table_top,
                current_x + VALUE_COLUMN_WIDTH,
                table_top + HEADER_HEIGHT,
            ),
            fill=HEADER_BACKGROUND,
            outline=BORDER,
            width=1,
        )

        _draw_header_text(
            draw=draw,
            text=column_key,
            left=current_x,
            top=table_top,
            width=VALUE_COLUMN_WIDTH,
            height=HEADER_HEIGHT,
            font=header_font,
        )

        current_x += VALUE_COLUMN_WIDTH

    if totals_enabled:
        draw.rectangle(
            (
                current_x,
                table_top,
                current_x + TOTAL_COLUMN_WIDTH,
                table_top + HEADER_HEIGHT,
            ),
            fill=HEADER_BACKGROUND,
            outline=BORDER,
            width=1,
        )

        _draw_header_text(
            draw=draw,
            text="Total",
            left=current_x,
            top=table_top,
            width=TOTAL_COLUMN_WIDTH,
            height=HEADER_HEIGHT,
            font=header_font,
        )

    # =====================================================
    # BODY
    # =====================================================

    current_y = (
        table_top
        + HEADER_HEIGHT
    )

    previous_first_level = None
    body_index = 0

    def draw_subtotal_row(
        first_level_value: str,
        top: int,
    ) -> int:
        current_cell_x = LEFT_PADDING

        # Label spans the row-dimension area visually through
        # matching background cells.
        for row_dimension_index in range(
            len(row_dimensions)
        ):
            draw.rectangle(
                (
                    current_cell_x,
                    top,
                    current_cell_x + ROW_DIMENSION_WIDTH,
                    top + ROW_HEIGHT,
                ),
                fill=SUBTOTAL_BACKGROUND,
                outline=BORDER,
                width=1,
            )

            if row_dimension_index == 0:
                _draw_cell_text_left(
                    draw=draw,
                    text=(
                        f"{first_level_value} Total"
                    ),
                    left=current_cell_x,
                    top=top,
                    width=ROW_DIMENSION_WIDTH,
                    height=ROW_HEIGHT,
                    font=total_font,
                )

            current_cell_x += ROW_DIMENSION_WIDTH

        matching_row_keys = [
            row_key
            for row_key in row_keys
            if row_key[0] == first_level_value
        ]

        for column_key in column_keys:
            subtotal_value = sum(
                pivot_data[
                    "matrix"
                ]
                .get(
                    row_key,
                    {},
                )
                .get(
                    column_key,
                    0.0,
                )
                for row_key in matching_row_keys
            )

            draw.rectangle(
                (
                    current_cell_x,
                    top,
                    current_cell_x + VALUE_COLUMN_WIDTH,
                    top + ROW_HEIGHT,
                ),
                fill=SUBTOTAL_BACKGROUND,
                outline=BORDER,
                width=1,
            )

            _draw_cell_text_right(
                draw=draw,
                text=_format_metric_value(
                    metric_name,
                    subtotal_value,
                ),
                left=current_cell_x,
                top=top,
                width=VALUE_COLUMN_WIDTH,
                height=ROW_HEIGHT,
                font=total_font,
            )

            current_cell_x += VALUE_COLUMN_WIDTH

        draw.rectangle(
            (
                current_cell_x,
                top,
                current_cell_x + TOTAL_COLUMN_WIDTH,
                top + ROW_HEIGHT,
            ),
            fill=SUBTOTAL_BACKGROUND,
            outline=BORDER,
            width=1,
        )

        _draw_cell_text_right(
            draw=draw,
            text=_format_metric_value(
                metric_name,
                pivot_data[
                    "first_level_totals"
                ][
                    first_level_value
                ],
            ),
            left=current_cell_x,
            top=top,
            width=TOTAL_COLUMN_WIDTH,
            height=ROW_HEIGHT,
            font=total_font,
        )

        return top + ROW_HEIGHT

    for row_key in row_keys:
        first_level = row_key[0]

        if (
            len(row_dimensions) == 2
            and totals_enabled
            and previous_first_level is not None
            and first_level != previous_first_level
        ):
            current_y = draw_subtotal_row(
                previous_first_level,
                current_y,
            )

        background = (
            ALTERNATE_ROW_BACKGROUND
            if body_index % 2
            else BACKGROUND
        )

        current_x = LEFT_PADDING

        for dimension_index, row_value in enumerate(
            row_key
        ):
            draw.rectangle(
                (
                    current_x,
                    current_y,
                    current_x + ROW_DIMENSION_WIDTH,
                    current_y + ROW_HEIGHT,
                ),
                fill=background,
                outline=BORDER,
                width=1,
            )

            display_value = row_value

            # In hierarchical 3D pivots, repeat Store/first
            # dimension only on the first detail row of that
            # group. This reads like a professional pivot.
            if (
                len(row_dimensions) == 2
                and dimension_index == 0
                and previous_first_level == first_level
            ):
                display_value = ""

            _draw_cell_text_left(
                draw=draw,
                text=display_value,
                left=current_x,
                top=current_y,
                width=ROW_DIMENSION_WIDTH,
                height=ROW_HEIGHT,
                font=body_font,
            )

            current_x += ROW_DIMENSION_WIDTH

        for column_key in column_keys:
            value = (
                pivot_data[
                    "matrix"
                ]
                .get(
                    row_key,
                    {},
                )
                .get(
                    column_key,
                    0.0,
                )
            )

            draw.rectangle(
                (
                    current_x,
                    current_y,
                    current_x + VALUE_COLUMN_WIDTH,
                    current_y + ROW_HEIGHT,
                ),
                fill=background,
                outline=BORDER,
                width=1,
            )

            _draw_cell_text_right(
                draw=draw,
                text=_format_metric_value(
                    metric_name,
                    value,
                ),
                left=current_x,
                top=current_y,
                width=VALUE_COLUMN_WIDTH,
                height=ROW_HEIGHT,
                font=body_font,
            )

            current_x += VALUE_COLUMN_WIDTH

        if totals_enabled:
            draw.rectangle(
                (
                    current_x,
                    current_y,
                    current_x + TOTAL_COLUMN_WIDTH,
                    current_y + ROW_HEIGHT,
                ),
                fill=TOTAL_BACKGROUND,
                outline=BORDER,
                width=1,
            )

            _draw_cell_text_right(
                draw=draw,
                text=_format_metric_value(
                    metric_name,
                    pivot_data[
                        "row_totals"
                    ][
                        row_key
                    ],
                ),
                left=current_x,
                top=current_y,
                width=TOTAL_COLUMN_WIDTH,
                height=ROW_HEIGHT,
                font=total_font,
            )

        previous_first_level = first_level
        current_y += ROW_HEIGHT
        body_index += 1

    if (
        len(row_dimensions) == 2
        and totals_enabled
        and previous_first_level is not None
    ):
        current_y = draw_subtotal_row(
            previous_first_level,
            current_y,
        )

    # =====================================================
    # GRAND TOTAL
    # =====================================================

    if totals_enabled:
        current_x = LEFT_PADDING

        for dimension_index in range(
            len(row_dimensions)
        ):
            draw.rectangle(
                (
                    current_x,
                    current_y,
                    current_x + ROW_DIMENSION_WIDTH,
                    current_y + ROW_HEIGHT,
                ),
                fill=TOTAL_BACKGROUND,
                outline=BORDER,
                width=1,
            )

            if dimension_index == 0:
                _draw_cell_text_left(
                    draw=draw,
                    text="GRAND TOTAL",
                    left=current_x,
                    top=current_y,
                    width=ROW_DIMENSION_WIDTH,
                    height=ROW_HEIGHT,
                    font=total_font,
                )

            current_x += ROW_DIMENSION_WIDTH

        for column_key in column_keys:
            draw.rectangle(
                (
                    current_x,
                    current_y,
                    current_x + VALUE_COLUMN_WIDTH,
                    current_y + ROW_HEIGHT,
                ),
                fill=TOTAL_BACKGROUND,
                outline=BORDER,
                width=1,
            )

            _draw_cell_text_right(
                draw=draw,
                text=_format_metric_value(
                    metric_name,
                    pivot_data[
                        "column_totals"
                    ][
                        column_key
                    ],
                ),
                left=current_x,
                top=current_y,
                width=VALUE_COLUMN_WIDTH,
                height=ROW_HEIGHT,
                font=total_font,
            )

            current_x += VALUE_COLUMN_WIDTH

        draw.rectangle(
            (
                current_x,
                current_y,
                current_x + TOTAL_COLUMN_WIDTH,
                current_y + ROW_HEIGHT,
            ),
            fill=TOTAL_BACKGROUND,
            outline=BORDER,
            width=1,
        )

        _draw_cell_text_right(
            draw=draw,
            text=_format_metric_value(
                metric_name,
                pivot_data[
                    "grand_total"
                ],
            ),
            left=current_x,
            top=current_y,
            width=TOTAL_COLUMN_WIDTH,
            height=ROW_HEIGHT,
            font=total_font,
        )

    output_path = (
        REPORTS_DIRECTORY
        / Path(
            file_name
        ).name
    )

    save_png(
        image=image,
        file_path=output_path,
    )

    return {
        "file_path": str(
            output_path
        ),
        "row_dimensions": (
            row_dimensions
        ),
        "column_dimension": (
            column_dimension
        ),
        "row_count": len(
            row_keys
        ),
        "column_count": len(
            column_keys
        ),
        "totals_enabled": (
            totals_enabled
        ),
    }
