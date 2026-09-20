from __future__ import annotations

import calendar
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pandas as pd


IST = ZoneInfo("Asia/Kolkata")


def _ordinal(day_number: int) -> str:
    if 10 <= day_number % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day_number % 10, "th")
    return f"{day_number}{suffix}"


def _display_full_date(value: date, include_weekday: bool = False) -> str:
    base = f"{_ordinal(value.day)} {value.strftime('%B %Y')}"
    if include_weekday:
        return f"{base}, {value.strftime('%A')}"
    return base


def _display_short_date(value: date) -> str:
    return f"{value.day} {value.strftime('%b %Y')}"


def _display_range(start_date: date, end_date: date, include_year: bool = True) -> str:
    if start_date.month == end_date.month and start_date.year == end_date.year:
        year_text = f" {end_date.year}" if include_year else ""
        return (
            f"{_ordinal(start_date.day)}-{_ordinal(end_date.day)} "
            f"{end_date.strftime('%B')}{year_text}"
        )
    return f"{_display_full_date(start_date)} to {_display_full_date(end_date)}"


def _format_indian_number(value: float, decimals: int = 0) -> str:
    numeric_value = float(value)
    sign = "-" if numeric_value < 0 else ""
    numeric_value = abs(numeric_value)

    rendered = f"{numeric_value:.{decimals}f}"
    if "." in rendered:
        integer_part, decimal_part = rendered.split(".")
    else:
        integer_part, decimal_part = rendered, ""

    if len(integer_part) <= 3:
        formatted_integer = integer_part
    else:
        last_three = integer_part[-3:]
        remaining = integer_part[:-3]
        groups = []
        while len(remaining) > 2:
            groups.insert(0, remaining[-2:])
            remaining = remaining[:-2]
        if remaining:
            groups.insert(0, remaining)
        formatted_integer = ",".join(groups) + "," + last_three

    if decimals > 0:
        return sign + formatted_integer + "." + decimal_part
    return sign + formatted_integer


def _percentage_change(current_value: float, comparison_value: float) -> float | None:
    current = float(current_value)
    comparison = float(comparison_value)

    if comparison == 0:
        if current == 0:
            return 0.0
        return None

    return ((current - comparison) / abs(comparison)) * 100.0


def _period_before_current_month(yesterday: date) -> tuple[date, date]:
    first_current_month = yesterday.replace(day=1)
    last_previous_month = first_current_month - timedelta(days=1)

    comparison_day = min(
        yesterday.day,
        calendar.monthrange(
            last_previous_month.year,
            last_previous_month.month,
        )[1],
    )

    return (
        last_previous_month.replace(day=1),
        last_previous_month.replace(day=comparison_day),
    )


def _prepare_sales_frame(data: dict) -> pd.DataFrame:
    if not isinstance(data, dict):
        raise ValueError("Workbook data must be a dictionary.")

    if "sales" not in data:
        raise ValueError("Workbook data does not contain the sales sheet.")

    sales_df = data["sales"].copy()

    # -----------------------------------------------------
    # Store mapping
    # -----------------------------------------------------
    # The raw Petpooja sales sheet identifies the outlet using
    # Restaurant. RestaurantAI's established workbook structure
    # keeps the user-friendly short Store name in store_info.
    #
    # Some prepared data paths may already contain Store. In that
    # case we preserve it. Otherwise we perform the same
    # Restaurant -> Store mapping used elsewhere in RestaurantAI.
    if "Store" not in sales_df.columns:
        if "Restaurant" not in sales_df.columns:
            raise ValueError(
                "Sales data must contain either Store or Restaurant."
            )

        if "store_info" not in data:
            raise ValueError(
                "Workbook data does not contain store_info required "
                "for Restaurant-to-Store mapping."
            )

        store_info_df = data["store_info"].copy()

        store_info_df.columns = (
            store_info_df.columns
            .astype(str)
            .str.strip()
        )

        required_store_columns = {
            "Restaurant",
            "Store",
        }

        missing_store_columns = (
            required_store_columns
            - set(store_info_df.columns)
        )

        if missing_store_columns:
            raise ValueError(
                "store_info is missing required columns: "
                + ", ".join(
                    sorted(missing_store_columns)
                )
            )

        store_mapping = (
            store_info_df[
                [
                    "Restaurant",
                    "Store",
                ]
            ]
            .dropna(
                subset=["Restaurant"]
            )
            .drop_duplicates(
                subset=["Restaurant"],
                keep="last",
            )
        )

        sales_df = sales_df.merge(
            store_mapping,
            on="Restaurant",
            how="left",
        )

    required_columns = {
        "Date",
        "Store",
        "Sub Total",
    }

    missing_columns = (
        required_columns
        - set(sales_df.columns)
    )

    if missing_columns:
        raise ValueError(
            "Sales data is missing required columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    sales_df["Date"] = pd.to_datetime(
        sales_df["Date"],
        errors="coerce",
    ).dt.date

    sales_df["Store"] = (
        sales_df["Store"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    # Never silently lose a sales row just because a newly added
    # Restaurant has not yet been mapped in store_info. Keep the
    # Restaurant name visible as a safe fallback.
    if "Restaurant" in sales_df.columns:
        restaurant_fallback = (
            sales_df["Restaurant"]
            .fillna("")
            .astype(str)
            .str.strip()
        )

        sales_df.loc[
            sales_df["Store"] == "",
            "Store",
        ] = restaurant_fallback[
            sales_df["Store"] == ""
        ]

    sales_df["Sub Total"] = pd.to_numeric(
        sales_df["Sub Total"],
        errors="coerce",
    ).fillna(0.0)

    if "Transaction_ID" not in sales_df.columns:
        if "Invoice No" not in sales_df.columns:
            raise ValueError(
                "Sales data must contain Transaction_ID or Invoice No."
            )

        sales_df["Transaction_ID"] = (
            sales_df["Store"].astype(str)
            + "_"
            + sales_df["Date"].astype(str)
            + "_"
            + sales_df["Invoice No"].fillna("").astype(str).str.strip()
        )

    return sales_df[
        sales_df["Date"].notna()
        & (sales_df["Store"] != "")
    ].copy()


def _slice_period(
    sales_df: pd.DataFrame,
    start_date: date,
    end_date: date,
) -> pd.DataFrame:
    return sales_df[
        (sales_df["Date"] >= start_date)
        & (sales_df["Date"] <= end_date)
    ].copy()


def _period_store_kpis(
    sales_df: pd.DataFrame,
    start_date: date,
    end_date: date,
    store_order: list[str],
) -> dict:
    period_df = _slice_period(
        sales_df=sales_df,
        start_date=start_date,
        end_date=end_date,
    )

    day_count = (end_date - start_date).days + 1

    if len(period_df) == 0:
        grouped = pd.DataFrame(
            columns=["Store", "Sales", "Transactions"]
        )
    else:
        grouped = (
            period_df
            .groupby("Store", as_index=False)
            .agg(
                Sales=("Sub Total", "sum"),
                Transactions=("Transaction_ID", "nunique"),
            )
        )

    lookup = {
        str(row["Store"]): {
            "sales": float(row["Sales"]),
            "transactions": int(row["Transactions"]),
        }
        for _, row in grouped.iterrows()
    }

    rows = []

    for store_name in store_order:
        values = lookup.get(
            store_name,
            {"sales": 0.0, "transactions": 0},
        )

        sales_value = float(values["sales"])
        transaction_value = int(values["transactions"])

        apt_value = (
            sales_value / transaction_value
            if transaction_value > 0
            else 0.0
        )

        rows.append(
            {
                "store": store_name,
                "sales": sales_value,
                "transactions": transaction_value,
                "apt": apt_value,
                "ads": sales_value / day_count if day_count > 0 else 0.0,
                "adt": transaction_value / day_count if day_count > 0 else 0.0,
            }
        )

    total_sales = float(period_df["Sub Total"].sum())
    total_transactions = int(period_df["Transaction_ID"].nunique())
    total_apt = (
        total_sales / total_transactions
        if total_transactions > 0
        else 0.0
    )

    total = {
        "store": "TOTAL",
        "sales": total_sales,
        "transactions": total_transactions,
        "apt": total_apt,
        "ads": total_sales / day_count if day_count > 0 else 0.0,
        "adt": total_transactions / day_count if day_count > 0 else 0.0,
    }

    return {
        "start_date": start_date.isoformat(),
        "end_date": end_date.isoformat(),
        "day_count": day_count,
        "rows": rows,
        "total": total,
    }


def _add_comparison(
    current_period: dict,
    comparison_period: dict,
    metric_names: tuple[str, ...],
) -> list[dict]:
    current_lookup = {
        row["store"]: row
        for row in current_period["rows"]
    }
    comparison_lookup = {
        row["store"]: row
        for row in comparison_period["rows"]
    }

    rows = []

    for store_name in current_lookup:
        current_row = current_lookup[store_name]
        comparison_row = comparison_lookup[store_name]

        output = {"store": store_name}

        for metric_name in metric_names:
            current_value = float(current_row[metric_name])
            comparison_value = float(comparison_row[metric_name])

            output[metric_name] = {
                "current": current_value,
                "comparison": comparison_value,
                "change_pct": _percentage_change(
                    current_value,
                    comparison_value,
                ),
            }

        rows.append(output)

    total_output = {"store": "TOTAL"}

    for metric_name in metric_names:
        current_value = float(current_period["total"][metric_name])
        comparison_value = float(comparison_period["total"][metric_name])

        total_output[metric_name] = {
            "current": current_value,
            "comparison": comparison_value,
            "change_pct": _percentage_change(
                current_value,
                comparison_value,
            ),
        }

    rows.append(total_output)
    return rows


def get_yesterday_morning_report(
    data: dict,
    as_of_date: date | None = None,
) -> dict:
    """
    Management-style report behind the "Yesterday sales" command.

    Comparison rules:
    - Yesterday vs the same weekday one week earlier.
    - Current MTD vs same day-number period last month.
    - MTD ADS / ADT / APT vs same period last month.
    """
    sales_df = _prepare_sales_frame(data)

    today = (
        as_of_date
        if as_of_date is not None
        else datetime.now(IST).date()
    )

    yesterday = today - timedelta(days=1)
    lwsd = yesterday - timedelta(days=7)

    mtd_start = yesterday.replace(day=1)
    lmtd_start, lmtd_end = _period_before_current_month(yesterday)

    available_dates = sorted(
        {
            value
            for value in sales_df["Date"].dropna()
        }
    )

    latest_available_date = (
        available_dates[-1]
        if available_dates
        else None
    )

    yesterday_available = yesterday in set(available_dates)

    relevant_start = min(lwsd, lmtd_start, mtd_start)
    relevant_end = max(yesterday, lmtd_end)

    relevant_df = _slice_period(
        sales_df=sales_df,
        start_date=relevant_start,
        end_date=relevant_end,
    )

    store_names = sorted(
        {
            str(value).strip()
            for value in relevant_df["Store"].dropna()
            if str(value).strip()
        }
    )

    mtd_df = _slice_period(
        sales_df=sales_df,
        start_date=mtd_start,
        end_date=yesterday,
    )

    mtd_sales_by_store = (
        mtd_df.groupby("Store")["Sub Total"]
        .sum()
        .to_dict()
    )

    store_order = sorted(
        store_names,
        key=lambda store_name: (
            -float(mtd_sales_by_store.get(store_name, 0.0)),
            store_name.casefold(),
        ),
    )

    yesterday_current = _period_store_kpis(
        sales_df=sales_df,
        start_date=yesterday,
        end_date=yesterday,
        store_order=store_order,
    )

    yesterday_comparison = _period_store_kpis(
        sales_df=sales_df,
        start_date=lwsd,
        end_date=lwsd,
        store_order=store_order,
    )

    mtd_current = _period_store_kpis(
        sales_df=sales_df,
        start_date=mtd_start,
        end_date=yesterday,
        store_order=store_order,
    )

    mtd_comparison = _period_store_kpis(
        sales_df=sales_df,
        start_date=lmtd_start,
        end_date=lmtd_end,
        store_order=store_order,
    )

    return {
        "report_type": "yesterday_morning",
        "dates": {
            "today": today.isoformat(),
            "yesterday": yesterday.isoformat(),
            "lwsd": lwsd.isoformat(),
            "mtd_start": mtd_start.isoformat(),
            "mtd_end": yesterday.isoformat(),
            "lmtd_start": lmtd_start.isoformat(),
            "lmtd_end": lmtd_end.isoformat(),
        },
        "labels": {
            "yesterday_full": _display_full_date(
                yesterday,
                include_weekday=True,
            ),
            "lwsd_full": _display_full_date(
                lwsd,
                include_weekday=True,
            ),
            "mtd_range": _display_range(
                mtd_start,
                yesterday,
                include_year=True,
            ),
            "lmtd_range": _display_range(
                lmtd_start,
                lmtd_end,
                include_year=True,
            ),
            "yesterday_short": _display_short_date(yesterday),
            "lwsd_short": _display_short_date(lwsd),
            "mtd_short": _display_range(
                mtd_start,
                yesterday,
                include_year=False,
            ),
            "lmtd_short": _display_range(
                lmtd_start,
                lmtd_end,
                include_year=False,
            ),
        },
        "data_status": {
            "yesterday_available": yesterday_available,
            "latest_available_date": (
                latest_available_date.isoformat()
                if latest_available_date is not None
                else None
            ),
        },
        "summary": {
            "yesterday_sales": yesterday_current["total"]["sales"],
            "lwsd_sales": yesterday_comparison["total"]["sales"],
            "yesterday_sales_change_pct": _percentage_change(
                yesterday_current["total"]["sales"],
                yesterday_comparison["total"]["sales"],
            ),
            "mtd_sales": mtd_current["total"]["sales"],
            "lmtd_sales": mtd_comparison["total"]["sales"],
            "mtd_sales_change_pct": _percentage_change(
                mtd_current["total"]["sales"],
                mtd_comparison["total"]["sales"],
            ),
        },
        "sections": {
            "yesterday": {
                "title": "Yesterday",
                "rows": _add_comparison(
                    current_period=yesterday_current,
                    comparison_period=yesterday_comparison,
                    metric_names=("sales", "transactions", "apt"),
                ),
            },
            "mtd_total": {
                "title": "MTD Total",
                "rows": _add_comparison(
                    current_period=mtd_current,
                    comparison_period=mtd_comparison,
                    metric_names=("sales", "transactions", "apt"),
                ),
            },
            "mtd_kpis": {
                "title": "MTD KPIs",
                "rows": _add_comparison(
                    current_period=mtd_current,
                    comparison_period=mtd_comparison,
                    metric_names=("ads", "adt", "apt"),
                ),
            },
        },
    }


def _movement_phrase(change_pct: float | None) -> str:
    if change_pct is None:
        return "not directly comparable"
    if change_pct > 0:
        return f"up by *{abs(change_pct):.1f}%*"
    if change_pct < 0:
        return f"down by *{abs(change_pct):.1f}%*"
    return "*unchanged*"


def _format_daily_alert_additions(data: dict, as_of_date: date | None = None) -> str:
    """Build the compact operational alerts appended to the morning message."""
    from services.intelligence.product_zero_sales import detect_product_zero_sales
    from services.intelligence.store_three_day_decline import detect_three_day_store_declines

    zero_result = detect_product_zero_sales(
        data=data,
        as_of_date=as_of_date,
    )
    zero_findings = zero_result.get("anomalies", [])

    if zero_findings:
        zero_lines = ["*Zero-sale products*"]

        # Group findings store-wise. Inside each store, show the longest
        # current zero-sales streak first so management sees the oldest issue
        # before newer 3-day alerts.
        findings_by_store: dict[str, list[dict]] = {}
        for finding in zero_findings:
            store = finding["store"]
            findings_by_store.setdefault(store, []).append(finding)

        for store, store_findings in findings_by_store.items():
            store_findings.sort(
                key=lambda finding: (
                    -int(
                        finding.get(
                            "zero_sales_operating_days",
                            len(finding.get("zero_sales_dates", [])),
                        )
                    ),
                    str(finding.get("item", "")).casefold(),
                )
            )

            zero_lines.append(f"*{store}*")

            for finding in store_findings:
                zero_days = int(
                    finding.get(
                        "zero_sales_operating_days",
                        len(finding.get("zero_sales_dates", [])),
                    )
                )

                day_word = "day" if zero_days == 1 else "days"

                zero_lines.append(
                    f"• {finding['item']} sales were zero "
                    f"for the last {zero_days} operating {day_word}."
                )

            zero_lines.append("")

        if zero_lines[-1] == "":
            zero_lines.pop()
    else:
        zero_lines = [
            "*Zero-sale products*",
            "• No zero-sale products.",
        ]

    decline_result = detect_three_day_store_declines(
        data=data,
        as_of_date=as_of_date,
    )
    decline_findings = decline_result.get("findings", [])
    minimum_decline_days = int(
        decline_result.get("minimum_decline_days", 3)
    )

    if decline_findings:
        decline_lines = ["*Store decline streak*"]

        for finding in decline_findings:
            decline_days = int(
                finding.get(
                    "decline_days",
                    len(finding.get("comparisons", [])),
                )
            )

            changes = ", ".join(
                f"{entry['change_pct']:.1f}%"
                for entry in finding["comparisons"]
            )

            day_word = "day" if decline_days == 1 else "days"

            decline_lines.append(
                f"• {finding['store']} was down versus the same weekdays "
                f"last week for {decline_days} consecutive comparable "
                f"{day_word} ({changes})."
            )
    else:
        decline_lines = [
            "*Store decline streak*",
            f"• No store is currently down for {minimum_decline_days} or more "
            f"consecutive comparable days versus the same weekdays last week.",
        ]

    return "\n".join(zero_lines + [""] + decline_lines)

def format_yesterday_morning_narrative(report: dict, data: dict | None = None) -> str:
    summary = report["summary"]
    labels = report["labels"]

    yesterday_sales = _format_indian_number(summary["yesterday_sales"])
    lwsd_sales = _format_indian_number(summary["lwsd_sales"])
    mtd_sales = _format_indian_number(summary["mtd_sales"])
    lmtd_sales = _format_indian_number(summary["lmtd_sales"])

    yesterday_movement = _movement_phrase(
        summary["yesterday_sales_change_pct"]
    )
    mtd_movement = _movement_phrase(
        summary["mtd_sales_change_pct"]
    )

    lwsd_date = datetime.strptime(
        report["dates"]["lwsd"],
        "%Y-%m-%d",
    ).date()

    narrative = (
        f"Yesterday ({labels['yesterday_full']}) sales were "
        f"*₹{yesterday_sales}/-*, {yesterday_movement} compared with "
        f"last {lwsd_date.strftime('%A')} "
        f"({_display_full_date(lwsd_date)}), when sales were "
        f"*₹{lwsd_sales}/-*.\n\n"
        f"Month till date ({labels['mtd_range']}) sales were "
        f"*₹{mtd_sales}/-*, {mtd_movement} against last month same "
        f"period ({labels['lmtd_range']}), when sales were "
        f"*₹{lmtd_sales}/-*.\n\n"
        f"Detailed report is attached."
    )

    if data is not None:
        as_of_date = datetime.strptime(
            report["dates"]["today"], "%Y-%m-%d"
        ).date()
        narrative += "\n\n" + _format_daily_alert_additions(
            data=data,
            as_of_date=as_of_date,
        )

    return narrative
