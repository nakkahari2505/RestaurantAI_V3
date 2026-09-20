from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd


INDIA_TIMEZONE = ZoneInfo("Asia/Kolkata")


def _format_date_with_ordinal(date_value) -> str:
    day = date_value.day

    if 10 < day % 100 < 14:
        suffix = "th"
    else:
        suffix = {
            1: "st",
            2: "nd",
            3: "rd",
        }.get(day % 10, "th")

    return f"{day}{suffix} {date_value.strftime('%b')}"


def get_yesterday_sales_report(data: dict) -> dict:
    sales = data["sales"].copy()
    store_info = data["store_info"].copy()

    # Clean column names.
    sales.columns = sales.columns.astype(str).str.strip()
    store_info.columns = store_info.columns.astype(str).str.strip()

    required_sales_columns = {"Date", "Restaurant", "Sub Total"}
    missing_sales_columns = required_sales_columns - set(sales.columns)

    if missing_sales_columns:
        raise ValueError(
            "Missing required columns in sales sheet: "
            + ", ".join(sorted(missing_sales_columns))
        )

    required_store_columns = {"Restaurant", "Store"}
    missing_store_columns = required_store_columns - set(store_info.columns)

    if missing_store_columns:
        raise ValueError(
            "Missing required columns in store_info sheet: "
            + ", ".join(sorted(missing_store_columns))
        )

    # Standardize the store mapping.
    store_mapping = store_info[["Restaurant", "Store"]].copy()
    store_mapping["Restaurant"] = (
        store_mapping["Restaurant"].astype(str).str.strip()
    )
    store_mapping["Store"] = store_mapping["Store"].astype(str).str.strip()

    store_mapping = (
        store_mapping
        .dropna(subset=["Restaurant", "Store"])
        .drop_duplicates(subset=["Restaurant"])
    )

    # Standardize sales data.
    sales["Restaurant"] = sales["Restaurant"].astype(str).str.strip()
    sales["Date"] = pd.to_datetime(sales["Date"], errors="coerce").dt.normalize()
    sales["Sub Total"] = pd.to_numeric(
        sales["Sub Total"],
        errors="coerce",
    ).fillna(0)

    sales = sales.dropna(subset=["Date"])

    # Map the long Restaurant name to the short Store name.
    sales = sales.merge(
        store_mapping,
        on="Restaurant",
        how="left",
    )

    # Keep unmapped restaurants visible rather than silently losing them.
    sales["Store"] = sales["Store"].fillna(sales["Restaurant"])

    # Actual previous calendar date in India time.
    today_india = datetime.now(INDIA_TIMEZONE).date()
    yesterday = pd.Timestamp(today_india) - pd.Timedelta(days=1)

    month_start = yesterday.replace(day=1)

    # All stores from store_info must appear, including stores with zero sales.
    all_stores = (
        store_mapping["Store"]
        .dropna()
        .drop_duplicates()
        .sort_values()
        .tolist()
    )

    # Add any unmapped store names found in sales.
    additional_stores = sorted(
        set(sales["Store"].dropna().unique()) - set(all_stores)
    )
    all_stores.extend(additional_stores)

    yesterday_data = sales[sales["Date"] == yesterday]

    month_to_date_data = sales[
        (sales["Date"] >= month_start)
        & (sales["Date"] <= yesterday)
    ]

    yesterday_by_store = (
        yesterday_data.groupby("Store")["Sub Total"].sum().to_dict()
    )

    month_to_date_by_store = (
        month_to_date_data.groupby("Store")["Sub Total"].sum().to_dict()
    )

    rows = []

    for store in all_stores:
        rows.append(
            {
                "store": store,
                "yesterday_sales": round(
                    float(yesterday_by_store.get(store, 0)),
                    2,
                ),
                "month_to_date_sales": round(
                    float(month_to_date_by_store.get(store, 0)),
                    2,
                ),
            }
        )

    yesterday_total = sum(row["yesterday_sales"] for row in rows)
    month_to_date_total = sum(row["month_to_date_sales"] for row in rows)

    latest_available_date = None

    if not sales.empty:
        latest_available_date = sales["Date"].max()

    warning = None

    if yesterday_data.empty:
        if latest_available_date is not None:
            warning = (
                "Warning: No sales data is available for "
                f"{yesterday.strftime('%d %b %Y')}. "
                "Latest available data: "
                f"{latest_available_date.strftime('%d %b %Y')}."
            )
        else:
            warning = (
                "Warning: No sales data is available for "
                f"{yesterday.strftime('%d %b %Y')}. "
                "The sales file contains no valid dated records."
            )

    return {
        "report_date": yesterday.strftime("%Y-%m-%d"),
        "yesterday_column": (
            f"{_format_date_with_ordinal(yesterday)} Sale"
        ),
        "month_column": (
            f"This Month ({yesterday.strftime('%b')}’"
            f"{yesterday.strftime('%y')}) Sale"
        ),
        "rows": rows,
        "total": {
            "store": "Total",
            "yesterday_sales": round(float(yesterday_total), 2),
            "month_to_date_sales": round(
                float(month_to_date_total),
                2,
            ),
        },
        "warning": warning,
    }