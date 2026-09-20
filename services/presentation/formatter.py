from datetime import datetime

from services.semantics.vocabulary.metrics import (
    METRIC_ADS,
    METRIC_ADT,
    METRIC_APT,
    METRIC_QUANTITY,
    METRIC_SALES,
    METRIC_TRANSACTIONS,
    get_metric_full_name,
)


# =========================================================
# DATE FORMATTING
# =========================================================


def _parse_report_date(
    report_date: str,
) -> datetime:
    return datetime.strptime(
        report_date,
        "%Y-%m-%d",
    )


def _format_report_date(
    report_date: str,
) -> str:
    date_value = _parse_report_date(
        report_date
    )

    return date_value.strftime(
        "%d %b %Y"
    )


def _format_date_with_ordinal(
    date_value: datetime,
) -> str:
    day = date_value.day

    if 10 < day % 100 < 14:
        suffix = "th"

    else:
        suffix = {
            1: "st",
            2: "nd",
            3: "rd",
        }.get(
            day % 10,
            "th",
        )

    return (
        f"{day}{suffix} "
        f"{date_value.strftime('%b')}"
    )


def _format_month_date_range(
    report_date: str,
) -> str:
    end_date = _parse_report_date(
        report_date
    )

    start_date = end_date.replace(
        day=1
    )

    return (
        f"{_format_date_with_ordinal(start_date)}"
        f" to "
        f"{_format_date_with_ordinal(end_date)}"
    )


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
    numeric_value = float(
        value
    )

    if numeric_value.is_integer():
        return str(
            int(numeric_value)
        )

    return f"{numeric_value:.1f}"


def _format_currency(
    value: float,
) -> str:
    return (
        "₹"
        + _format_indian_number(
            value
        )
    )


# =========================================================
# TEXT HELPERS
# =========================================================


def _shorten_store_name(
    store_name: str,
    width: int,
) -> str:
    cleaned_name = str(
        store_name
    ).strip()

    if len(cleaned_name) <= width:
        return cleaned_name

    return (
        cleaned_name[
            : width - 1
        ]
        + "…"
    )


def _format_name_list(
    values: list[str],
) -> str:
    cleaned_values = [
        str(value).strip()
        for value in values
        if str(value).strip()
    ]

    return ", ".join(
        cleaned_values
    )


# =========================================================
# YESTERDAY SALES FORMATTER
# =========================================================


def _build_two_column_table(
    rows: list[dict],
    value_key: str,
    total_value: float,
) -> list[str]:
    store_width = 18
    value_width = 11

    table_width = (
        store_width
        + value_width
    )

    lines = [
        "```",
        (
            f"{'Store':<{store_width}}"
            f"{'Sales':>{value_width}}"
        ),
        "-" * table_width,
    ]

    for row in rows:
        store_name = (
            _shorten_store_name(
                row["store"],
                store_width,
            )
        )

        sales_value = (
            _format_indian_number(
                row[value_key]
            )
        )

        lines.append(
            f"{store_name:<{store_width}}"
            f"{sales_value:>{value_width}}"
        )

    lines.extend(
        [
            "-" * table_width,
            (
                f"{'TOTAL':<{store_width}}"
                f"{_format_indian_number(total_value):>{value_width}}"
            ),
            "```",
        ]
    )

    return lines


def format_yesterday_sales_report(
    report: dict,
) -> str:
    report_date = (
        _format_report_date(
            report[
                "report_date"
            ]
        )
    )

    month_date_range = (
        _format_month_date_range(
            report[
                "report_date"
            ]
        )
    )

    lines = [
        "📊 *Yesterday Sales*",
        f"📅 {report_date}",
        "",
    ]

    lines.extend(
        _build_two_column_table(
            rows=report["rows"],
            value_key=(
                "yesterday_sales"
            ),
            total_value=report[
                "total"
            ][
                "yesterday_sales"
            ],
        )
    )

    lines.extend(
        [
            "",
            "📈 *Month Till Date*",
            f"🗓️ {month_date_range}",
            "",
        ]
    )

    lines.extend(
        _build_two_column_table(
            rows=report["rows"],
            value_key=(
                "month_to_date_sales"
            ),
            total_value=report[
                "total"
            ][
                "month_to_date_sales"
            ],
        )
    )

    lines.append("")

    if report.get(
        "warning"
    ):
        lines.extend(
            [
                "⚠️ *Data Warning:*",
                report["warning"],
            ]
        )

    else:
        lines.append(
            "✅ Data refreshed successfully."
        )

    return "\n".join(
        lines
    )


# =========================================================
# STORE PERFORMANCE FORMATTER
# =========================================================


def _build_sales_transactions_table(
    report: dict,
) -> list[str]:
    store_width = 14
    sales_width = 11
    txns_width = 7

    table_width = (
        store_width
        + sales_width
        + txns_width
    )

    lines = [
        "```",
        (
            f"{'Store':<{store_width}}"
            f"{'Sales':>{sales_width}}"
            f"{'Txns':>{txns_width}}"
        ),
        "-" * table_width,
    ]

    for row in report[
        "rows"
    ]:
        store_name = (
            _shorten_store_name(
                row["store"],
                store_width,
            )
        )

        lines.append(
            f"{store_name:<{store_width}}"
            f"{_format_indian_number(row['total_sales']):>{sales_width}}"
            f"{_format_indian_number(row['total_txns']):>{txns_width}}"
        )

    total = report[
        "total"
    ]

    lines.extend(
        [
            "-" * table_width,
            (
                f"{'TOTAL':<{store_width}}"
                f"{_format_indian_number(total['total_sales']):>{sales_width}}"
                f"{_format_indian_number(total['total_txns']):>{txns_width}}"
            ),
            "```",
        ]
    )

    return lines


def _build_average_kpis_table(
    report: dict,
) -> list[str]:
    store_width = 14
    ads_width = 9
    adt_width = 7
    apt_width = 7

    table_width = (
        store_width
        + ads_width
        + adt_width
        + apt_width
    )

    lines = [
        "```",
        (
            f"{'Store':<{store_width}}"
            f"{'ADS':>{ads_width}}"
            f"{'ADT':>{adt_width}}"
            f"{'APT':>{apt_width}}"
        ),
        "-" * table_width,
    ]

    for row in report[
        "rows"
    ]:
        store_name = (
            _shorten_store_name(
                row["store"],
                store_width,
            )
        )

        lines.append(
            f"{store_name:<{store_width}}"
            f"{_format_indian_number(row['ads']):>{ads_width}}"
            f"{_format_decimal(row['adt']):>{adt_width}}"
            f"{_format_indian_number(row['apt']):>{apt_width}}"
        )

    total = report[
        "total"
    ]

    lines.extend(
        [
            "-" * table_width,
            (
                f"{'TOTAL':<{store_width}}"
                f"{_format_indian_number(total['ads']):>{ads_width}}"
                f"{_format_decimal(total['adt']):>{adt_width}}"
                f"{_format_indian_number(total['apt']):>{apt_width}}"
            ),
            "```",
        ]
    )

    return lines


def _format_missing_dates(
    missing_dates: list[str],
) -> list[str]:
    formatted_dates = [
        _format_report_date(
            date_text
        )
        for date_text
        in missing_dates
    ]

    lines = []

    for index in range(
        0,
        len(formatted_dates),
        3,
    ):
        date_group = (
            formatted_dates[
                index:index + 3
            ]
        )

        lines.append(
            ", ".join(
                date_group
            )
        )

    return lines


def format_store_performance_report(
    report: dict,
) -> str:
    start_date = (
        _format_report_date(
            report[
                "start_date"
            ]
        )
    )

    end_date = (
        _format_report_date(
            report[
                "end_date"
            ]
        )
    )

    lines = [
        "📊 *Sales Performance*",
        "",
        "🗓️ *Time Period:*",
        (
            f"{start_date} "
            f"to {end_date}"
        ),
        "",
    ]

    lines.extend(
        _build_sales_transactions_table(
            report
        )
    )

    lines.extend(
        [
            "",
            "📈 *Average Performance*",
            "",
        ]
    )

    lines.extend(
        _build_average_kpis_table(
            report
        )
    )

    lines.extend(
        [
            "",
            "ADS = Average Daily Sales",
            "ADT = Average Daily Transactions",
            "APT = Average Per Transaction",
            "",
        ]
    )

    if report[
        "data_complete"
    ]:
        lines.append(
            "✅ Sales data is available for all dates "
            "in the selected period."
        )

    else:
        lines.append(
            "⚠️ *Sales data is not available for:*"
        )

        lines.extend(
            _format_missing_dates(
                report[
                    "missing_dates"
                ]
            )
        )

    return "\n".join(
        lines
    )


# =========================================================
# GENERIC RAL METRIC FORMATTER
# =========================================================


def _format_ral_time_period(
    ral_request: dict,
) -> str:
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

    if (
        not start_date
        or not end_date
    ):
        return "Not specified"

    formatted_start_date = (
        _format_report_date(
            start_date
        )
    )

    formatted_end_date = (
        _format_report_date(
            end_date
        )
    )

    if start_date == end_date:
        return formatted_start_date

    return (
        f"{formatted_start_date}"
        f" to "
        f"{formatted_end_date}"
    )


def _format_ral_metric_value(
    metric_name: str,
    metric_value: float,
) -> str:
    normalized_metric = (
        str(metric_name)
        .strip()
        .lower()
    )

    if normalized_metric in {
        METRIC_SALES,
        METRIC_ADS,
        METRIC_APT,
    }:
        return _format_currency(
            metric_value
        )

    if normalized_metric in {
        METRIC_QUANTITY,
        METRIC_TRANSACTIONS,
    }:
        return _format_indian_number(
            metric_value
        )

    if normalized_metric == METRIC_ADT:
        return _format_decimal(
            metric_value
        )

    return _format_decimal(
        metric_value
    )


def _build_ral_filter_lines(
    ral_request: dict,
) -> list[str]:
    lines = []

    stores = ral_request.get(
        "stores",
        [],
    )

    channels = ral_request.get(
        "channels",
        [],
    )

    aggregators = ral_request.get(
        "aggregators",
        [],
    )

    categories = ral_request.get(
        "categories",
        [],
    )

    items = ral_request.get(
        "items",
        [],
    )

    if stores:
        store_label = (
            "Store"
            if len(stores) == 1
            else "Stores"
        )

        lines.append(
            (
                f"🏬 *{store_label}:* "
                f"{_format_name_list(stores)}"
            )
        )

    if channels:
        channel_label = (
            "Channel"
            if len(channels) == 1
            else "Channels"
        )

        lines.append(
            (
                f"🛍️ *{channel_label}:* "
                f"{_format_name_list(channels)}"
            )
        )

    if aggregators:
        aggregator_label = (
            "Aggregator"
            if len(aggregators) == 1
            else "Aggregators"
        )

        lines.append(
            (
                f"📱 *{aggregator_label}:* "
                f"{_format_name_list(aggregators)}"
            )
        )

    if categories:
        category_label = (
            "Category"
            if len(categories) == 1
            else "Categories"
        )

        lines.append(
            (
                f"🍽️ *{category_label}:* "
                f"{_format_name_list(categories)}"
            )
        )

    if items:
        item_label = (
            "Item"
            if len(items) == 1
            else "Items"
        )

        lines.append(
            (
                f"📦 *{item_label}:* "
                f"{_format_name_list(items)}"
            )
        )

    return lines


def format_ral_metric_reply(
    ral_request: dict,
    metric_value: float,
) -> str:
    """
    Format one generic RAL metric result for WhatsApp.

    Examples supported:

    - Sales
    - Quantity
    - Transactions
    - ADS
    - ADT
    - APT

    Only filters actually present in RAL are displayed.
    """
    metric_name = str(
        ral_request.get(
            "metric",
            ""
        )
    ).strip().lower()

    metric_full_name = (
        get_metric_full_name(
            metric_name
        )
    )

    formatted_metric_value = (
        _format_ral_metric_value(
            metric_name=metric_name,
            metric_value=metric_value,
        )
    )

    time_period = (
        _format_ral_time_period(
            ral_request
        )
    )

    lines = [
        f"📊 *{metric_full_name}*",
        "",
        f"🗓️ *Period:* {time_period}",
    ]

    filter_lines = (
        _build_ral_filter_lines(
            ral_request
        )
    )

    if filter_lines:
        lines.extend(
            filter_lines
        )

    lines.extend(
        [
            "",
            (
                f"*{metric_full_name}: "
                f"{formatted_metric_value}*"
            ),
        ]
    )

    return "\n".join(
        lines
    )