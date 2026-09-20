from datetime import datetime

import pandas as pd


ACCEPTED_DATE_FORMATS = (
    "%d-%b-%Y",
    "%d %b %Y",
)


def _parse_date(
    date_text: str,
) -> pd.Timestamp:
    """
    Convert a supported date into a normalized pandas date.

    Official RestaurantAI format:
        DD-Mmm-YYYY

    Also accepted for backward compatibility:
        DD Mmm YYYY

    Examples:
        01-Jul-2026
        01 Jul 2026
        1-Jul-2026
    """
    cleaned_date = " ".join(
        str(date_text).strip().split()
    )

    for date_format in ACCEPTED_DATE_FORMATS:
        try:
            parsed_date = datetime.strptime(
                cleaned_date,
                date_format,
            )

            return pd.Timestamp(
                parsed_date
            ).normalize()

        except ValueError:
            continue

    raise ValueError(
        f"Invalid date: {date_text}. "
        "Please use DD-Mmm-YYYY format, "
        "for example 01-Jul-2026."
    )


def _prepare_sales_data(
    data: dict,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Prepare the raw sales sheet and short store-name mapping.
    """
    sales = data["sales"].copy()
    store_info = data["store_info"].copy()

    sales.columns = (
        sales.columns
        .astype(str)
        .str.strip()
    )

    store_info.columns = (
        store_info.columns
        .astype(str)
        .str.strip()
    )

    required_sales_columns = {
        "Date",
        "Restaurant",
        "Invoice No",
        "Sub Total",
    }

    missing_sales_columns = (
        required_sales_columns
        - set(sales.columns)
    )

    if missing_sales_columns:
        raise ValueError(
            "Missing columns in sales sheet: "
            + ", ".join(
                sorted(missing_sales_columns)
            )
        )

    required_store_columns = {
        "Restaurant",
        "Store",
    }

    missing_store_columns = (
        required_store_columns
        - set(store_info.columns)
    )

    if missing_store_columns:
        raise ValueError(
            "Missing columns in store_info sheet: "
            + ", ".join(
                sorted(missing_store_columns)
            )
        )

    sales["Restaurant"] = (
        sales["Restaurant"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    store_info["Restaurant"] = (
        store_info["Restaurant"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    store_info["Store"] = (
        store_info["Store"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    store_mapping = (
        store_info[
            [
                "Restaurant",
                "Store",
            ]
        ]
        .loc[
            lambda frame:
            frame["Restaurant"].ne("")
            & frame["Store"].ne("")
        ]
        .drop_duplicates(
            subset=["Restaurant"]
        )
    )

    all_stores = (
        store_mapping["Store"]
        .drop_duplicates()
        .tolist()
    )

    sales = sales.merge(
        store_mapping,
        on="Restaurant",
        how="left",
    )

    sales["Store"] = sales["Store"].fillna(
        sales["Restaurant"]
    )

    sales["Store"] = (
        sales["Store"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    sales["Date"] = pd.to_datetime(
        sales["Date"],
        errors="coerce",
    ).dt.normalize()

    sales["Sub Total"] = pd.to_numeric(
        sales["Sub Total"],
        errors="coerce",
    ).fillna(0.0)

    sales["Invoice No"] = (
        sales["Invoice No"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    sales = sales.dropna(
        subset=["Date"]
    )

    sales["Transaction_ID"] = (
        sales["Store"]
        + "|"
        + sales["Date"].dt.strftime(
            "%Y-%m-%d"
        )
        + "|"
        + sales["Invoice No"]
    )

    return sales, all_stores


def _get_missing_dates(
    period_data: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> list[pd.Timestamp]:
    """
    Return every calendar date in the selected period
    for which no sales row exists at all.
    """
    expected_dates = pd.date_range(
        start=start_date,
        end=end_date,
        freq="D",
    )

    available_dates = pd.DatetimeIndex(
        period_data["Date"]
        .dropna()
        .drop_duplicates()
        .sort_values()
    )

    missing_dates = expected_dates.difference(
        available_dates
    )

    return list(
        missing_dates
    )


def get_store_performance_report(
    data: dict,
    start_date_text: str,
    end_date_text: str,
) -> dict:
    """
    Calculate store-wise Sales, Transactions, ADS, ADT and APT
    for an inclusive date range.

    ADS and ADT use the full requested calendar period,
    including dates with no available sales rows.
    """
    start_date = _parse_date(
        start_date_text
    )

    end_date = _parse_date(
        end_date_text
    )

    if start_date > end_date:
        raise ValueError(
            "From date cannot be later than To date."
        )

    sales, all_stores = _prepare_sales_data(
        data
    )

    number_of_days = (
        end_date - start_date
    ).days + 1

    period_data = sales[
        sales["Date"].between(
            start_date,
            end_date,
            inclusive="both",
        )
    ].copy()

    missing_dates = _get_missing_dates(
        period_data=period_data,
        start_date=start_date,
        end_date=end_date,
    )

    grouped = (
        period_data.groupby(
            "Store",
            dropna=False,
        )
        .agg(
            total_sales=(
                "Sub Total",
                "sum",
            ),
            total_txns=(
                "Transaction_ID",
                "nunique",
            ),
        )
        .reset_index()
    )

    all_stores_frame = pd.DataFrame(
        {
            "Store": all_stores,
        }
    )

    grouped = all_stores_frame.merge(
        grouped,
        on="Store",
        how="left",
    )

    grouped["total_sales"] = (
        grouped["total_sales"]
        .fillna(0.0)
        .astype(float)
    )

    grouped["total_txns"] = (
        grouped["total_txns"]
        .fillna(0)
        .astype(int)
    )

    grouped["ads"] = (
        grouped["total_sales"]
        / number_of_days
    )

    grouped["adt"] = (
        grouped["total_txns"]
        / number_of_days
    )

    grouped["apt"] = grouped.apply(
        lambda row: (
            row["total_sales"]
            / row["total_txns"]
            if row["total_txns"] > 0
            else 0.0
        ),
        axis=1,
    )

    grouped = grouped.sort_values(
        by="total_sales",
        ascending=False,
    ).reset_index(
        drop=True
    )

    rows = []

    for _, row in grouped.iterrows():
        rows.append(
            {
                "store": str(
                    row["Store"]
                ),
                "total_sales": round(
                    float(
                        row["total_sales"]
                    ),
                    2,
                ),
                "total_txns": int(
                    row["total_txns"]
                ),
                "ads": round(
                    float(
                        row["ads"]
                    ),
                    2,
                ),
                "adt": round(
                    float(
                        row["adt"]
                    ),
                    2,
                ),
                "apt": round(
                    float(
                        row["apt"]
                    ),
                    2,
                ),
            }
        )

    total_sales = float(
        grouped["total_sales"].sum()
    )

    total_txns = int(
        grouped["total_txns"].sum()
    )

    total = {
        "store": "Total",
        "total_sales": round(
            total_sales,
            2,
        ),
        "total_txns": total_txns,
        "ads": round(
            total_sales
            / number_of_days,
            2,
        ),
        "adt": round(
            total_txns
            / number_of_days,
            2,
        ),
        "apt": round(
            (
                total_sales
                / total_txns
                if total_txns > 0
                else 0.0
            ),
            2,
        ),
    }

    return {
        "start_date": start_date.strftime(
            "%Y-%m-%d"
        ),
        "end_date": end_date.strftime(
            "%Y-%m-%d"
        ),
        "number_of_days": number_of_days,
        "rows": rows,
        "total": total,
        "missing_dates": [
            date_value.strftime(
                "%Y-%m-%d"
            )
            for date_value in missing_dates
        ],
        "data_complete": (
            len(missing_dates) == 0
        ),
    }