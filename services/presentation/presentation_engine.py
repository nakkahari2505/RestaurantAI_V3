from datetime import datetime
from typing import Any


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
# NUMBER FORMATTING
# =========================================================


def _format_indian_number(
    value: float,
) -> str:
    """
    Format whole numbers using Indian comma grouping.

    Examples:

        1234 -> 1,234
        123456 -> 1,23,456
        1234567 -> 12,34,567
    """
    number = int(
        round(
            float(
                value
            )
        )
    )

    sign = (
        "-"
        if number < 0
        else ""
    )

    digits = str(
        abs(
            number
        )
    )

    if len(digits) <= 3:
        return (
            sign
            + digits
        )

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
    """
    Central metric display formatting.
    """
    normalized_metric = (
        str(
            metric_name
        )
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
# TEXT HELPERS
# =========================================================


def _metric_display_name(
    metric_name: str,
) -> str:
    normalized_metric = (
        str(
            metric_name
        )
        .strip()
        .lower()
    )

    return (
        METRIC_DISPLAY_NAMES.get(
            normalized_metric,
            normalized_metric.title(),
        )
    )


def _dimension_display_name(
    dimension_name: str,
) -> str:
    normalized_dimension = (
        str(
            dimension_name
        )
        .strip()
        .lower()
    )

    return (
        DIMENSION_DISPLAY_NAMES.get(
            normalized_dimension,
            normalized_dimension.title(),
        )
    )


def _build_group_label(
    groups: dict[str, str],
    grouping_dimensions: list[str],
) -> str:
    """
    Build clean display label.

    Examples:

        AMB Mall

        AMB Mall | Dine In

        AMB Mall | Dine In | Donuts
    """
    values = []

    for dimension in (
        grouping_dimensions
    ):
        value = groups.get(
            dimension,
            "",
        )

        if value:
            values.append(
                str(
                    value
                )
            )

    return " | ".join(
        values
    )


# =========================================================
# GROUPED TEXT PRESENTATION
# =========================================================


def format_grouped_result_text(
    grouped_result: dict,
    max_rows: int = 20,
) -> str:
    """
    Convert Grouping Engine result into WhatsApp-friendly
    readable text.
    """

    metric_name = (
        grouped_result[
            "metric"
        ]
    )

    metric_display = (
        _metric_display_name(
            metric_name
        )
    )

    grouping_dimensions = (
        grouped_result.get(
            "grouping_dimensions",
            [],
        )
    )

    dimension_display = (
        " + ".join(
            _dimension_display_name(
                dimension
            )
            for dimension
            in grouping_dimensions
        )
    )

    lines = [
        f"📊 *{metric_display}*",
        "",
        (
            f"🔹 *Grouped by:* "
            f"{dimension_display}"
        ),
        "",
    ]

    rows = (
        grouped_result.get(
            "rows",
            []
        )
    )

    visible_rows = (
        rows[:max_rows]
    )

    for index, row in enumerate(
        visible_rows,
        start=1,
    ):
        groups = row.get(
            "groups",
            {},
        )

        group_label = (
            _build_group_label(
                groups=groups,
                grouping_dimensions=(
                    grouping_dimensions
                ),
            )
        )

        metric_value = (
            _format_metric_value(
                metric_name=metric_name,
                value=row[
                    "metric_value"
                ],
            )
        )

        lines.append(
            f"{index}. "
            f"{group_label}: "
            f"*{metric_value}*"
        )

    if len(rows) > max_rows:
        lines.extend(
            [
                "",
                (
                    f"Showing top "
                    f"{max_rows} of "
                    f"{len(rows)} results."
                ),
            ]
        )

    return "\n".join(
        lines
    )


# =========================================================
# PLAIN TREND TEXT PRESENTATION
# =========================================================


def format_plain_trend_text(
    trend_result: dict,
    max_points: int = 30,
) -> str:
    """
    Render a non-grouped daily/weekly/monthly trend
    as clean WhatsApp text.
    """

    metric_name = (
        trend_result[
            "metric"
        ]
    )

    metric_display = (
        _metric_display_name(
            metric_name
        )
    )

    grain = (
        str(
            trend_result[
                "grain"
            ]
        )
        .strip()
        .title()
    )

    lines = [
        f"📈 *{metric_display} Trend*",
        "",
        f"🗓️ *Grain:* {grain}",
        "",
    ]

    rows = (
        trend_result.get(
            "rows",
            []
        )
    )

    visible_rows = (
        rows[:max_points]
    )

    for row in visible_rows:
        metric_value = (
            _format_metric_value(
                metric_name=metric_name,
                value=row[
                    "metric_value"
                ],
            )
        )

        lines.append(
            f"{row['period_label']}: "
            f"*{metric_value}*"
        )

    if len(rows) > max_points:
        lines.extend(
            [
                "",
                (
                    f"Showing first "
                    f"{max_points} of "
                    f"{len(rows)} periods."
                ),
            ]
        )

    return "\n".join(
        lines
    )


# =========================================================
# GROUPED TREND TEXT PRESENTATION
# =========================================================


def format_grouped_trend_text(
    trend_result: dict,
    max_periods: int = 10,
    max_groups_per_period: int = 10,
) -> str:
    """
    Render Trend + Grouping results.

    Example:

        Daily store-wise sales trend.
    """

    metric_name = (
        trend_result[
            "metric"
        ]
    )

    metric_display = (
        _metric_display_name(
            metric_name
        )
    )

    grain = (
        str(
            trend_result[
                "grain"
            ]
        )
        .strip()
        .title()
    )

    grouping_dimensions = (
        trend_result.get(
            "grouping_dimensions",
            [],
        )
    )

    dimension_display = (
        " + ".join(
            _dimension_display_name(
                dimension
            )
            for dimension
            in grouping_dimensions
        )
    )

    lines = [
        f"📈 *{metric_display} Trend*",
        "",
        f"🗓️ *Grain:* {grain}",
        (
            f"🔹 *Grouped by:* "
            f"{dimension_display}"
        ),
        "",
    ]

    periods = (
        trend_result.get(
            "rows",
            []
        )
    )

    visible_periods = (
        periods[:max_periods]
    )

    for period in (
        visible_periods
    ):
        lines.append(
            f"*{period['period_label']}*"
        )

        grouped_result = (
            period.get(
                "grouped_result",
                {},
            )
        )

        group_rows = (
            grouped_result.get(
                "rows",
                [],
            )
        )

        for group_row in (
            group_rows[
                :max_groups_per_period
            ]
        ):
            group_label = (
                _build_group_label(
                    groups=(
                        group_row.get(
                            "groups",
                            {},
                        )
                    ),
                    grouping_dimensions=(
                        grouping_dimensions
                    ),
                )
            )

            metric_value = (
                _format_metric_value(
                    metric_name=(
                        metric_name
                    ),
                    value=(
                        group_row[
                            "metric_value"
                        ]
                    ),
                )
            )

            lines.append(
                f"• {group_label}: "
                f"{metric_value}"
            )

        if (
            len(
                group_rows
            )
            > max_groups_per_period
        ):
            lines.append(
                (
                    f"• +"
                    f"{len(group_rows) - max_groups_per_period} "
                    f"more"
                )
            )

        lines.append("")

    if len(periods) > max_periods:
        lines.append(
            (
                f"Showing first "
                f"{max_periods} of "
                f"{len(periods)} periods."
            )
        )

    return "\n".join(
        lines
    ).strip()


# =========================================================
# CHART CONTEXT
# =========================================================


def _build_chart_subtitle(
    ral_request: dict,
) -> str:
    """
    Build compact business context for chart display.

    Examples:

        01 Jul 2026 to 31 Jul 2026

        Nexus Mall | 01 Aug 2026 to 07 Aug 2026

        Delivery | Zomato | Donuts | 01 Aug 2026 to 07 Aug 2026
    """
    parts = []

    for field_name in (
        "stores",
        "channels",
        "aggregators",
        "categories",
        "items",
    ):
        values = ral_request.get(
            field_name,
            [],
        )

        if values:
            parts.append(
                ", ".join(
                    str(value)
                    for value in values
                )
            )

    time_value = ral_request.get(
        "time",
        {},
    )

    start_date = time_value.get(
        "start_date"
    )

    end_date = time_value.get(
        "end_date"
    )

    if start_date and end_date:
        try:
            parsed_start = datetime.strptime(
                start_date,
                "%Y-%m-%d",
            )

            parsed_end = datetime.strptime(
                end_date,
                "%Y-%m-%d",
            )

            if start_date == end_date:
                period_text = parsed_start.strftime(
                    "%d %b %Y"
                )
            else:
                period_text = (
                    parsed_start.strftime(
                        "%d %b %Y"
                    )
                    + " to "
                    + parsed_end.strftime(
                        "%d %b %Y"
                    )
                )

            parts.append(
                period_text
            )

        except ValueError:
            pass

    if not parts:
        return "All Business"

    return " | ".join(
        parts
    )


# =========================================================
# CHART SPECIFICATION
# =========================================================


def build_chart_spec(
    result: dict,
    result_type: str,
    ral_request: dict,
) -> dict:
    """
    Build a chart-neutral specification.

    IMPORTANT:

    This function does NOT draw anything.

    It converts analytics output into a clean structure
    that the future chart/image renderer can consume.

    This keeps business calculation separate from graphics.
    """

    presentation_type = (
        ral_request.get(
            "presentation",
            {},
        )
        .get(
            "type",
            "text",
        )
    )

    if presentation_type not in {
        "bar_chart",
        "line_chart",
    }:
        raise ValueError(
            "Chart presentation was not requested."
        )

    normalized_result_type = (
        str(
            result_type
        )
        .strip()
        .lower()
    )

    # =====================================================
    # GROUPED RESULT
    # =====================================================

    if normalized_result_type == "grouped":

        metric_name = result[
            "metric"
        ]

        grouping_dimensions = (
            result.get(
                "grouping_dimensions",
                [],
            )
        )

        points = []

        for row in result.get(
            "rows",
            []
        ):
            label = (
                _build_group_label(
                    groups=(
                        row.get(
                            "groups",
                            {},
                        )
                    ),
                    grouping_dimensions=(
                        grouping_dimensions
                    ),
                )
            )

            points.append(
                {
                    "label": label,
                    "value": float(
                        row[
                            "metric_value"
                        ]
                    ),
                }
            )

        return {
            "chart_type": (
                presentation_type
            ),

            "metric": metric_name,

            "title": (
                f"{_metric_display_name(metric_name)} "
                f"by "
                + " + ".join(
                    _dimension_display_name(
                        dimension
                    )
                    for dimension
                    in grouping_dimensions
                )
            ),

            "subtitle": (
                _build_chart_subtitle(
                    ral_request
                )
            ),

            "series": [
                {
                    "name": (
                        _metric_display_name(
                            metric_name
                        )
                    ),
                    "points": points,
                }
            ],
        }

    # =====================================================
    # TREND RESULT
    # =====================================================

    if normalized_result_type == "trend":

        metric_name = result[
            "metric"
        ]

        grouping_enabled = (
            result.get(
                "grouping_enabled",
                False,
            )
        )

        # ---------------------------------------------
        # Plain trend
        # ---------------------------------------------

        if not grouping_enabled:

            points = []

            for row in result.get(
                "rows",
                []
            ):
                points.append(
                    {
                        "label": (
                            row[
                                "period_label"
                            ]
                        ),
                        "value": float(
                            row[
                                "metric_value"
                            ]
                        ),
                    }
                )

            return {
                "chart_type": (
                    presentation_type
                ),

                "metric": metric_name,

                "title": (
                    f"{_metric_display_name(metric_name)} "
                    f"Trend"
                ),

                "subtitle": (
                    _build_chart_subtitle(
                        ral_request
                    )
                ),

                "series": [
                    {
                        "name": (
                            _metric_display_name(
                                metric_name
                            )
                        ),
                        "points": points,
                    }
                ],
            }

        # ---------------------------------------------
        # Grouped trend
        # ---------------------------------------------

        grouping_dimensions = (
            result.get(
                "grouping_dimensions",
                [],
            )
        )

        series_map: dict[
            str,
            list[dict[str, Any]],
        ] = {}

        for period in result.get(
            "rows",
            []
        ):
            period_label = (
                period[
                    "period_label"
                ]
            )

            grouped_result = (
                period.get(
                    "grouped_result",
                    {},
                )
            )

            for row in (
                grouped_result.get(
                    "rows",
                    [],
                )
            ):
                group_label = (
                    _build_group_label(
                        groups=(
                            row.get(
                                "groups",
                                {},
                            )
                        ),
                        grouping_dimensions=(
                            grouping_dimensions
                        ),
                    )
                )

                series_map.setdefault(
                    group_label,
                    [],
                )

                series_map[
                    group_label
                ].append(
                    {
                        "label": (
                            period_label
                        ),
                        "value": float(
                            row[
                                "metric_value"
                            ]
                        ),
                    }
                )

        return {
            "chart_type": (
                presentation_type
            ),

            "metric": metric_name,

            "title": (
                f"{_metric_display_name(metric_name)} "
                f"Trend by "
                + " + ".join(
                    _dimension_display_name(
                        dimension
                    )
                    for dimension
                    in grouping_dimensions
                )
            ),

            "subtitle": (
                _build_chart_subtitle(
                    ral_request
                )
            ),

            "series": [
                {
                    "name": (
                        series_name
                    ),
                    "points": (
                        points
                    ),
                }
                for (
                    series_name,
                    points,
                ) in series_map.items()
            ],
        }

    raise ValueError(
        "Unsupported presentation result type."
    )



# =========================================================
# PIVOT TABLE SPECIFICATION
# =========================================================


def _distinct_group_value_count(
    grouped_result: dict,
    dimension: str,
) -> int:
    """
    Count distinct values for one grouping dimension.

    Used only to choose the most compact column dimension for
    a three-dimensional pivot table.
    """
    values = {
        str(
            row.get(
                "groups",
                {},
            ).get(
                dimension,
                "",
            )
        ).strip()
        for row in grouped_result.get(
            "rows",
            [],
        )
    }

    values.discard("")

    return len(values)


def _choose_pivot_axes(
    grouped_result: dict,
) -> tuple[list[str], str]:
    """
    Choose pivot rows and columns from grouping dimensions.

    Business rules:

    2 dimensions
        -> 1 row dimension + 1 column dimension

    3 dimensions
        -> 2 row dimensions + 1 column dimension

    If Store is present
        -> Store MUST be the first row dimension.

    For 3 dimensions, the column dimension is chosen from the
    non-Store dimensions using the smallest distinct-value
    count. This keeps the image narrower and more readable.
    """
    dimensions = list(
        grouped_result.get(
            "grouping_dimensions",
            [],
        )
    )

    if len(dimensions) not in {
        2,
        3,
    }:
        raise ValueError(
            "Pivot presentation currently supports "
            "two or three grouping dimensions."
        )

    if len(dimensions) == 2:
        if "store" in dimensions:
            row_dimensions = [
                "store",
            ]

            column_dimension = next(
                dimension
                for dimension in dimensions
                if dimension != "store"
            )

            return (
                row_dimensions,
                column_dimension,
            )

        return (
            [
                dimensions[0],
            ],
            dimensions[1],
        )

    # =====================================================
    # THREE DIMENSIONS
    # =====================================================

    if "store" in dimensions:
        non_store_dimensions = [
            dimension
            for dimension in dimensions
            if dimension != "store"
        ]

        column_dimension = min(
            non_store_dimensions,
            key=lambda dimension: (
                _distinct_group_value_count(
                    grouped_result,
                    dimension,
                ),
                dimensions.index(
                    dimension
                ),
            ),
        )

        second_row_dimension = next(
            dimension
            for dimension in non_store_dimensions
            if dimension != column_dimension
        )

        return (
            [
                "store",
                second_row_dimension,
            ],
            column_dimension,
        )

    column_dimension = min(
        dimensions,
        key=lambda dimension: (
            _distinct_group_value_count(
                grouped_result,
                dimension,
            ),
            dimensions.index(
                dimension
            ),
        ),
    )

    row_dimensions = [
        dimension
        for dimension in dimensions
        if dimension != column_dimension
    ]

    return (
        row_dimensions,
        column_dimension,
    )


def build_pivot_spec(
    grouped_result: dict,
    ral_request: dict,
) -> dict:
    """
    Convert a 2D/3D grouped analytics result into a generic
    pivot-table specification.

    This function decides HOW the grouped result should be
    arranged. It does not draw the image.
    """
    metric_name = str(
        grouped_result.get(
            "metric",
            "",
        )
    )

    row_dimensions, column_dimension = (
        _choose_pivot_axes(
            grouped_result
        )
    )

    title_dimensions = (
        row_dimensions
        + [
            column_dimension,
        ]
    )

    title = (
        f"{_metric_display_name(metric_name)} by "
        + " + ".join(
            _dimension_display_name(
                dimension
            )
            for dimension in title_dimensions
        )
    )

    return {
        "metric": metric_name,
        "title": title,
        "subtitle": (
            _build_chart_subtitle(
                ral_request
            )
        ),
        "row_dimensions": (
            row_dimensions
        ),
        "column_dimension": (
            column_dimension
        ),
        "rows": (
            grouped_result.get(
                "rows",
                [],
            )
        ),
        "show_grand_total": True,
        "show_row_totals": True,
        "show_subtotals": (
            len(
                row_dimensions
            ) == 2
        ),
    }


# =========================================================
# PUBLIC PRESENTATION ROUTER
# =========================================================


def present_result(
    result: dict,
    result_type: str,
    ral_request: dict,
) -> dict:
    """
    Common Presentation Layer entry point.

    Presentation policy:

        Explicit line/bar chart request
            -> chart

        Grouped result with 1 dimension
            -> compact WhatsApp text

        Grouped result with 2 dimensions
            -> pivot-table image

        Grouped result with 3 dimensions
            -> hierarchical pivot-table image
               (2 row dimensions + 1 column dimension)

        If Store is present in a pivot
            -> Store is always the first row dimension.

        Trend without explicit chart
            -> text (existing behaviour)

    The router/delivery layer should only act on the returned
    mode. It should not decide presentation rules itself.
    """
    presentation_type = (
        ral_request.get(
            "presentation",
            {},
        )
        .get(
            "type",
            "text",
        )
    )

    normalized_result_type = (
        str(
            result_type
        )
        .strip()
        .lower()
    )

    # =====================================================
    # EXPLICIT CHART REQUEST OVERRIDES AUTOMATIC PIVOT
    # =====================================================

    if presentation_type in {
        "bar_chart",
        "line_chart",
    }:
        return {
            "mode": "chart",
            "chart_spec": (
                build_chart_spec(
                    result=result,
                    result_type=(
                        normalized_result_type
                    ),
                    ral_request=(
                        ral_request
                    ),
                )
            ),
        }

    # =====================================================
    # GROUPED RESULT
    # =====================================================

    if normalized_result_type == "grouped":
        grouping_dimensions = list(
            result.get(
                "grouping_dimensions",
                [],
            )
        )

        dimension_count = len(
            grouping_dimensions
        )

        if dimension_count == 1:
            return {
                "mode": "text",
                "text": (
                    format_grouped_result_text(
                        grouped_result=result
                    )
                ),
            }

        if dimension_count in {
            2,
            3,
        }:
            return {
                "mode": "pivot_table",
                "pivot_spec": (
                    build_pivot_spec(
                        grouped_result=result,
                        ral_request=(
                            ral_request
                        ),
                    )
                ),
            }

        return {
            "mode": "text",
            "text": (
                "This request has too many grouping "
                "dimensions for a clean management view. "
                "Please narrow it to three dimensions or less."
            ),
        }

    # =====================================================
    # TREND TEXT
    # =====================================================

    if normalized_result_type == "trend":
        grouping_enabled = (
            result.get(
                "grouping_enabled",
                False,
            )
        )

        if grouping_enabled:
            presentation_text = (
                format_grouped_trend_text(
                    trend_result=result
                )
            )
        else:
            presentation_text = (
                format_plain_trend_text(
                    trend_result=result
                )
            )

        return {
            "mode": "text",
            "text": presentation_text,
        }

    raise ValueError(
        "Unsupported presentation result type."
    )

