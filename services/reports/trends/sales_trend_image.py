from __future__ import annotations

from pathlib import Path
from uuid import uuid4

from services.presentation.chart_engine import (
    render_line_chart,
)


def generate_sales_trend_image(
    report: dict,
) -> Path:
    """
    Render the monthly trend using RestaurantAI's existing
    professional chart engine.

    The shared chart engine already owns:
    - business colours,
    - fonts,
    - spacing,
    - line/point rendering,
    - visible point labels,
    - Indian number formatting.
    """
    points = report.get(
        "points",
        [],
    )

    if not points:
        raise ValueError(
            "No monthly trend points were generated."
        )

    labels = [
        str(
            point[
                "month"
            ]
        )
        for point in points
    ]

    values = [
        float(
            point[
                "value"
            ]
        )
        for point in points
    ]

    file_name = (
        "restaurantai_monthly_trend_"
        f"{uuid4().hex}.png"
    )

    return render_line_chart(
        title=str(
            report[
                "title"
            ]
        ),
        labels=labels,
        values=values,
        metric_name=str(
            report[
                "metric"
            ]
        ),
        subtitle=str(
            report.get(
                "subtitle",
                "",
            )
        ),
        file_name=file_name,
    )
