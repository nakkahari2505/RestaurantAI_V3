from pathlib import Path
from typing import Callable, Final

from PIL import ImageDraw

from services.presentation.image_engine import (
    create_canvas,
    draw_centered_text,
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
# CANVAS
# =========================================================

CANVAS_WIDTH: Final[int] = 1400
CANVAS_HEIGHT: Final[int] = 900

LEFT_MARGIN: Final[int] = 110
RIGHT_MARGIN: Final[int] = 90
BOTTOM_MARGIN: Final[int] = 120


# =========================================================
# COLOURS
# =========================================================

BACKGROUND_COLOUR: Final[str] = "white"
TEXT_COLOUR: Final[str] = "#222222"
SECONDARY_TEXT_COLOUR: Final[str] = "#666666"
AXIS_COLOUR: Final[str] = "#999999"
GRID_COLOUR: Final[str] = "#E6E6E6"

PRIMARY_COLOUR: Final[str] = "#2F6FED"
BAR_COLOUR: Final[str] = "#2F6FED"


# =========================================================
# FONT SIZES
# =========================================================

TITLE_FONT_SIZE: Final[int] = 42
SUBTITLE_FONT_SIZE: Final[int] = 24
AXIS_FONT_SIZE: Final[int] = 22
VALUE_FONT_SIZE: Final[int] = 19
LEGEND_FONT_SIZE: Final[int] = 20


# =========================================================
# CHART TYPES
# =========================================================

CHART_LINE: Final[str] = "line_chart"
CHART_BAR: Final[str] = "bar_chart"

SUPPORTED_CHART_TYPES: Final[set[str]] = {
    CHART_LINE,
    CHART_BAR,
}


# =========================================================
# NUMBER FORMATTING
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
            + [
                last_three,
            ]
        )
    )


def _format_decimal(
    value: float,
) -> str:
    numeric_value = float(
        value
    )

    if numeric_value.is_integer():
        return str(
            int(
                numeric_value
            )
        )

    return (
        f"{numeric_value:.1f}"
    )


def _format_metric_value(
    metric_name: str,
    value: float,
) -> str:
    normalized_metric = (
        str(metric_name)
        .strip()
        .lower()
    )

    if normalized_metric == "sales":
        return (
            "₹"
            + _format_indian_number(
                value
            )
        )

    if normalized_metric == "adt":
        return _format_decimal(
            value
        )

    return _format_indian_number(
        value
    )


# =========================================================
# VALIDATION
# =========================================================


def _validate_chart_spec(
    chart_spec: dict,
) -> None:
    """
    Validate the minimum generic chart contract.

    Chart Engine deliberately knows nothing about:
    - restaurants,
    - stores,
    - categories,
    - channels,
    - RAL,
    - filters,
    - analytics formulas.

    It only accepts a presentation specification.
    """
    if not isinstance(
        chart_spec,
        dict,
    ):
        raise ValueError(
            "Chart specification must be an object."
        )

    chart_type = (
        str(
            chart_spec.get(
                "chart_type",
                "",
            )
        )
        .strip()
        .lower()
    )

    if chart_type not in SUPPORTED_CHART_TYPES:
        raise ValueError(
            "Unsupported chart type: "
            f"{chart_type}"
        )

    title = chart_spec.get(
        "title",
        "",
    )

    if not isinstance(
        title,
        str,
    ):
        raise ValueError(
            "Chart title must be text."
        )

    series = chart_spec.get(
        "series",
        [],
    )

    if not isinstance(
        series,
        list,
    ):
        raise ValueError(
            "Chart series must be a list."
        )

    for series_item in series:
        if not isinstance(
            series_item,
            dict,
        ):
            raise ValueError(
                "Each chart series must be an object."
            )

        points = series_item.get(
            "points",
            [],
        )

        if not isinstance(
            points,
            list,
        ):
            raise ValueError(
                "Chart series points must be a list."
            )

        for point in points:
            if not isinstance(
                point,
                dict,
            ):
                raise ValueError(
                    "Each chart point must be an object."
                )

            if (
                "label" not in point
                or "value" not in point
            ):
                raise ValueError(
                    "Every chart point requires "
                    "label and value."
                )

            try:
                float(
                    point[
                        "value"
                    ]
                )
            except (
                TypeError,
                ValueError,
            ) as error:
                raise ValueError(
                    "Every chart point value "
                    "must be numeric."
                ) from error


# =========================================================
# GENERIC HELPERS
# =========================================================


def _nice_axis_max(
    maximum_value: float,
) -> float:
    """
    Leave enough visual headroom for value labels.
    """
    maximum_value = float(
        maximum_value
    )

    if maximum_value <= 0:
        return 1.0

    return (
        maximum_value
        * 1.25
    )


def _draw_y_grid(
    draw: ImageDraw.ImageDraw,
    plot_left: int,
    plot_top: int,
    plot_right: int,
    plot_bottom: int,
    axis_max: float,
    metric_name: str,
) -> None:
    axis_font = load_font(
        AXIS_FONT_SIZE
    )

    steps = 5

    plot_height = (
        plot_bottom
        - plot_top
    )

    for step in range(
        steps + 1
    ):
        ratio = (
            step
            / steps
        )

        y = int(
            plot_bottom
            - (
                plot_height
                * ratio
            )
        )

        value = (
            axis_max
            * ratio
        )

        draw.line(
            (
                plot_left,
                y,
                plot_right,
                y,
            ),
            fill=GRID_COLOUR,
            width=1,
        )

        label = (
            _format_metric_value(
                metric_name,
                value,
            )
        )

        label_width = (
            get_text_width(
                draw=draw,
                text=label,
                font=axis_font,
            )
        )

        draw.text(
            (
                plot_left
                - label_width
                - 20,
                y - 12,
            ),
            label,
            font=axis_font,
            fill=SECONDARY_TEXT_COLOUR,
        )


def _draw_axes(
    draw: ImageDraw.ImageDraw,
    plot_left: int,
    plot_top: int,
    plot_right: int,
    plot_bottom: int,
) -> None:
    draw.line(
        (
            plot_left,
            plot_bottom,
            plot_right,
            plot_bottom,
        ),
        fill=AXIS_COLOUR,
        width=2,
    )

    draw.line(
        (
            plot_left,
            plot_top,
            plot_left,
            plot_bottom,
        ),
        fill=AXIS_COLOUR,
        width=2,
    )


def _draw_chart_header(
    draw: ImageDraw.ImageDraw,
    title: str,
    subtitle: str,
) -> int:
    """
    Draw title and optional subtitle.

    Returns the top Y position available for plotting.
    """
    title_font = load_font(
        TITLE_FONT_SIZE,
        bold=True,
    )

    subtitle_font = load_font(
        SUBTITLE_FONT_SIZE
    )

    draw_centered_text(
        draw=draw,
        text=title,
        left_x=LEFT_MARGIN,
        right_x=(
            CANVAS_WIDTH
            - RIGHT_MARGIN
        ),
        y=30,
        font=title_font,
        fill=TEXT_COLOUR,
    )

    if subtitle:
        draw_centered_text(
            draw=draw,
            text=subtitle,
            left_x=LEFT_MARGIN,
            right_x=(
                CANVAS_WIDTH
                - RIGHT_MARGIN
            ),
            y=90,
            font=subtitle_font,
            fill=SECONDARY_TEXT_COLOUR,
        )

        return 170

    return 145


def _draw_no_data_message(
    draw: ImageDraw.ImageDraw,
    plot_left: int,
    plot_right: int,
    plot_top: int,
) -> None:
    subtitle_font = load_font(
        SUBTITLE_FONT_SIZE
    )

    draw_centered_text(
        draw=draw,
        text="No data available",
        left_x=plot_left,
        right_x=plot_right,
        y=(
            plot_top
            + 200
        ),
        font=subtitle_font,
        fill=SECONDARY_TEXT_COLOUR,
    )


def _should_show_point_label(
    point_index: int,
    point_count: int,
) -> bool:
    """
    Keep line-chart value labels readable.

    Up to 12 points:
        show every value.

    Above 12:
        show first, last and selected intermediate points.
    """
    if point_count <= 12:
        return True

    step = max(
        1,
        point_count // 8,
    )

    return (
        point_index == 0
        or point_index
        == point_count - 1
        or point_index % step == 0
    )


def _get_all_values(
    series_list: list[dict],
) -> list[float]:
    values: list[float] = []

    for series in series_list:
        for point in (
            series.get(
                "points",
                [],
            )
        ):
            values.append(
                float(
                    point[
                        "value"
                    ]
                )
            )

    return values


# =========================================================
# LINE CHART RENDERER
# =========================================================


def _render_line_chart(
    chart_spec: dict,
    output_path: Path,
) -> Path:
    image, draw = (
        create_canvas(
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            background=BACKGROUND_COLOUR,
        )
    )

    axis_font = load_font(
        AXIS_FONT_SIZE
    )

    value_font = load_font(
        VALUE_FONT_SIZE,
        bold=True,
    )

    title = str(
        chart_spec.get(
            "title",
            "Trend",
        )
    )

    subtitle = str(
        chart_spec.get(
            "subtitle",
            "",
        )
    )

    metric_name = str(
        chart_spec.get(
            "metric",
            "",
        )
    )

    series_list = (
        chart_spec.get(
            "series",
            [],
        )
    )

    plot_top = (
        _draw_chart_header(
            draw=draw,
            title=title,
            subtitle=subtitle,
        )
    )

    plot_left = (
        LEFT_MARGIN
        + 80
    )

    plot_right = (
        CANVAS_WIDTH
        - RIGHT_MARGIN
    )

    plot_bottom = (
        CANVAS_HEIGHT
        - BOTTOM_MARGIN
    )

    all_values = (
        _get_all_values(
            series_list
        )
    )

    maximum_value = (
        max(
            all_values
        )
        if all_values
        else 0
    )

    axis_max = (
        _nice_axis_max(
            maximum_value
        )
    )

    _draw_y_grid(
        draw=draw,
        plot_left=plot_left,
        plot_top=plot_top,
        plot_right=plot_right,
        plot_bottom=plot_bottom,
        axis_max=axis_max,
        metric_name=metric_name,
    )

    _draw_axes(
        draw=draw,
        plot_left=plot_left,
        plot_top=plot_top,
        plot_right=plot_right,
        plot_bottom=plot_bottom,
    )

    if not series_list:
        _draw_no_data_message(
            draw=draw,
            plot_left=plot_left,
            plot_right=plot_right,
            plot_top=plot_top,
        )

        save_png(
            image=image,
            file_path=output_path,
        )

        return output_path

    plot_width = (
        plot_right
        - plot_left
    )

    plot_height = (
        plot_bottom
        - plot_top
    )

    # Current production renderer uses one common visual
    # colour. Multi-series palette can be added later without
    # changing the public chart contract.
    for series in series_list:
        points = (
            series.get(
                "points",
                [],
            )
        )

        if not points:
            continue

        point_count = (
            len(points)
        )

        coordinates: list[
            tuple[int, int]
        ] = []

        for index, point in enumerate(
            points
        ):
            if point_count == 1:
                x = (
                    plot_left
                    + plot_width // 2
                )

            else:
                x = int(
                    plot_left
                    + (
                        plot_width
                        * index
                        / (
                            point_count
                            - 1
                        )
                    )
                )

            value = float(
                point[
                    "value"
                ]
            )

            y = int(
                plot_bottom
                - (
                    value
                    / axis_max
                    * plot_height
                )
            )

            coordinates.append(
                (
                    x,
                    y,
                )
            )

        if len(
            coordinates
        ) >= 2:
            draw.line(
                coordinates,
                fill=PRIMARY_COLOUR,
                width=5,
                joint="curve",
            )

        for index, (
            point,
            coordinate,
        ) in enumerate(
            zip(
                points,
                coordinates,
            )
        ):
            x, y = coordinate

            draw.ellipse(
                (
                    x - 7,
                    y - 7,
                    x + 7,
                    y + 7,
                ),
                fill=PRIMARY_COLOUR,
            )

            if _should_show_point_label(
                point_index=index,
                point_count=point_count,
            ):
                value_text = (
                    _format_metric_value(
                        metric_name=metric_name,
                        value=point[
                            "value"
                        ],
                    )
                )

                value_width = (
                    get_text_width(
                        draw=draw,
                        text=value_text,
                        font=value_font,
                    )
                )

                draw.text(
                    (
                        x
                        - value_width // 2,
                        y - 36,
                    ),
                    value_text,
                    font=value_font,
                    fill=TEXT_COLOUR,
                )

        max_x_labels = 8

        label_step = max(
            1,
            (
                point_count
                // max_x_labels
            ),
        )

        for index, (
            point,
            coordinate,
        ) in enumerate(
            zip(
                points,
                coordinates,
            )
        ):
            if (
                index
                % label_step
                != 0
                and index
                != point_count - 1
            ):
                continue

            label = str(
                point[
                    "label"
                ]
            )

            x, _ = coordinate

            label_width = (
                get_text_width(
                    draw=draw,
                    text=label,
                    font=axis_font,
                )
            )

            draw.text(
                (
                    x
                    - label_width // 2,
                    plot_bottom
                    + 20,
                ),
                label,
                font=axis_font,
                fill=SECONDARY_TEXT_COLOUR,
            )

    save_png(
        image=image,
        file_path=output_path,
    )

    return output_path


# =========================================================
# BAR CHART RENDERER
# =========================================================


def _render_bar_chart(
    chart_spec: dict,
    output_path: Path,
) -> Path:
    image, draw = (
        create_canvas(
            width=CANVAS_WIDTH,
            height=CANVAS_HEIGHT,
            background=BACKGROUND_COLOUR,
        )
    )

    axis_font = load_font(
        AXIS_FONT_SIZE
    )

    value_font = load_font(
        VALUE_FONT_SIZE,
        bold=True,
    )

    title = str(
        chart_spec.get(
            "title",
            "Grouped Result",
        )
    )

    subtitle = str(
        chart_spec.get(
            "subtitle",
            "",
        )
    )

    metric_name = str(
        chart_spec.get(
            "metric",
            "",
        )
    )

    series_list = (
        chart_spec.get(
            "series",
            [],
        )
    )

    plot_top = (
        _draw_chart_header(
            draw=draw,
            title=title,
            subtitle=subtitle,
        )
    )

    if not series_list:
        _draw_no_data_message(
            draw=draw,
            plot_left=LEFT_MARGIN,
            plot_right=(
                CANVAS_WIDTH
                - RIGHT_MARGIN
            ),
            plot_top=plot_top,
        )

        save_png(
            image=image,
            file_path=output_path,
        )

        return output_path

    points = (
        series_list[
            0
        ].get(
            "points",
            [],
        )
    )

    # Deliberate WhatsApp readability guardrail.
    # Full list remains in analytics output.
    points = (
        points[:15]
    )

    plot_left = (
        LEFT_MARGIN
        + 80
    )

    plot_right = (
        CANVAS_WIDTH
        - RIGHT_MARGIN
    )

    plot_bottom = (
        CANVAS_HEIGHT
        - BOTTOM_MARGIN
    )

    values = [
        float(
            point[
                "value"
            ]
        )
        for point
        in points
    ]

    maximum_value = (
        max(values)
        if values
        else 0
    )

    axis_max = (
        _nice_axis_max(
            maximum_value
        )
    )

    _draw_y_grid(
        draw=draw,
        plot_left=plot_left,
        plot_top=plot_top,
        plot_right=plot_right,
        plot_bottom=plot_bottom,
        axis_max=axis_max,
        metric_name=metric_name,
    )

    _draw_axes(
        draw=draw,
        plot_left=plot_left,
        plot_top=plot_top,
        plot_right=plot_right,
        plot_bottom=plot_bottom,
    )

    if not points:
        save_png(
            image=image,
            file_path=output_path,
        )

        return output_path

    plot_width = (
        plot_right
        - plot_left
    )

    plot_height = (
        plot_bottom
        - plot_top
    )

    slot_width = (
        plot_width
        / len(points)
    )

    bar_width = max(
        20,
        int(
            slot_width
            * 0.58
        ),
    )

    for index, point in enumerate(
        points
    ):
        value = float(
            point[
                "value"
            ]
        )

        center_x = int(
            plot_left
            + (
                slot_width
                * index
            )
            + (
                slot_width
                / 2
            )
        )

        bar_height = int(
            (
                value
                / axis_max
            )
            * plot_height
        )

        bar_top = (
            plot_bottom
            - bar_height
        )

        left = (
            center_x
            - bar_width // 2
        )

        right = (
            center_x
            + bar_width // 2
        )

        draw.rectangle(
            (
                left,
                bar_top,
                right,
                plot_bottom,
            ),
            fill=BAR_COLOUR,
        )

        value_text = (
            _format_metric_value(
                metric_name,
                value,
            )
        )

        value_width = (
            get_text_width(
                draw=draw,
                text=value_text,
                font=value_font,
            )
        )

        draw.text(
            (
                center_x
                - value_width // 2,
                bar_top
                - 35,
            ),
            value_text,
            font=value_font,
            fill=TEXT_COLOUR,
        )

        label = str(
            point[
                "label"
            ]
        )

        if len(label) > 18:
            label = (
                label[:17]
                + "…"
            )

        label_width = (
            get_text_width(
                draw=draw,
                text=label,
                font=axis_font,
            )
        )

        draw.text(
            (
                center_x
                - label_width // 2,
                plot_bottom
                + 20,
            ),
            label,
            font=axis_font,
            fill=SECONDARY_TEXT_COLOUR,
        )

    save_png(
        image=image,
        file_path=output_path,
    )

    return output_path


# =========================================================
# RENDERER REGISTRY
# =========================================================

ChartRenderer = Callable[
    [
        dict,
        Path,
    ],
    Path,
]


CHART_RENDERERS: Final[
    dict[
        str,
        ChartRenderer,
    ]
] = {
    CHART_LINE: _render_line_chart,
    CHART_BAR: _render_bar_chart,
}


# =========================================================
# PUBLIC GENERIC CHART ENGINE
# =========================================================


def render_chart(
    chart_spec: dict,
    file_name: str = "restaurantai_chart.png",
) -> Path:
    """
    Generic RestaurantAI chart entry point.

    The caller provides only a chart specification.

    The caller does NOT need to know:
    - Pillow,
    - fonts,
    - canvas size,
    - margins,
    - axes,
    - formatting,
    - drawing logic,
    - output folder.

    Supported today:

        line_chart
        bar_chart

    Future chart types can be added by:
    1. implementing one renderer function,
    2. registering it in CHART_RENDERERS.

    Analytics engines do not need to change.
    """
    _validate_chart_spec(
        chart_spec
    )

    chart_type = (
        str(
            chart_spec[
                "chart_type"
            ]
        )
        .strip()
        .lower()
    )

    renderer = (
        CHART_RENDERERS.get(
            chart_type
        )
    )

    if renderer is None:
        raise ValueError(
            "No renderer is registered for "
            f"chart type: {chart_type}"
        )

    safe_file_name = (
        Path(
            str(
                file_name
            )
        ).name
    )

    if not safe_file_name:
        safe_file_name = (
            "restaurantai_chart.png"
        )

    if not safe_file_name.lower().endswith(
        ".png"
    ):
        safe_file_name = (
            safe_file_name
            + ".png"
        )

    output_path = (
        REPORTS_DIRECTORY
        / safe_file_name
    )

    return renderer(
        chart_spec,
        output_path,
    )


# =========================================================
# CONVENIENCE WRAPPERS
# =========================================================


def render_line_chart(
    title: str,
    labels: list[str],
    values: list[float],
    metric_name: str = "",
    subtitle: str = "",
    file_name: str = "restaurantai_line_chart.png",
) -> Path:
    """
    Optional generic convenience wrapper.

    Useful when another future service has plain X/Y values
    and does not need to manually build a chart specification.
    """
    if len(labels) != len(values):
        raise ValueError(
            "Line chart labels and values "
            "must have the same length."
        )

    chart_spec = {
        "chart_type": CHART_LINE,
        "metric": metric_name,
        "title": title,
        "subtitle": subtitle,
        "series": [
            {
                "name": title,
                "points": [
                    {
                        "label": str(label),
                        "value": float(value),
                    }
                    for (
                        label,
                        value,
                    ) in zip(
                        labels,
                        values,
                    )
                ],
            }
        ],
    }

    return render_chart(
        chart_spec=chart_spec,
        file_name=file_name,
    )


def render_bar_chart(
    title: str,
    labels: list[str],
    values: list[float],
    metric_name: str = "",
    subtitle: str = "",
    file_name: str = "restaurantai_bar_chart.png",
) -> Path:
    """
    Optional generic convenience wrapper.

    Useful for any future grouped/ranked analytics result.
    """
    if len(labels) != len(values):
        raise ValueError(
            "Bar chart labels and values "
            "must have the same length."
        )

    chart_spec = {
        "chart_type": CHART_BAR,
        "metric": metric_name,
        "title": title,
        "subtitle": subtitle,
        "series": [
            {
                "name": title,
                "points": [
                    {
                        "label": str(label),
                        "value": float(value),
                    }
                    for (
                        label,
                        value,
                    ) in zip(
                        labels,
                        values,
                    )
                ],
            }
        ],
    }

    return render_chart(
        chart_spec=chart_spec,
        file_name=file_name,
    )
