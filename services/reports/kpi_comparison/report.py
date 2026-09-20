from datetime import datetime

import pandas as pd


DATE_FORMAT = "%d-%b-%Y"


def _parse_date(date_text: str) -> pd.Timestamp:
    """
    Parse dates such as 01-Apr-2025.
    """
    cleaned_date = str(date_text).strip()

    try:
        return pd.Timestamp(
            datetime.strptime(
                cleaned_date,
                DATE_FORMAT,
            )
        ).normalize()

    except ValueError as exc:
        raise ValueError(
            f"Invalid date: {cleaned_date}. "
            "Use DD-Mmm-YYYY, for example 01-Apr-2026."
        ) from exc


def _validate_period(
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
    period_name: str,
) -> None:
    if start_date > end_date:
        raise ValueError(
            f"{period_name} start date cannot be later "
            "than its end date."
        )


def _prepare_sales_data(
    data: dict,
) -> tuple[pd.DataFrame, list[str]]:
    """
    Prepare the Auberry cloud workbook for KPI comparison.

    Channel rules:
    - Order Type = Dine In -> DINE-IN
    - Otherwise Area contains Swiggy -> SWIGGY
    - Otherwise Area contains Zomato -> ZOMATO
    - Remaining rows -> OTHERS
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
        "Order Type",
        "Area",
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

    sales["Store"] = (
        sales["Store"]
        .fillna(
            sales["Restaurant"]
        )
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

    sales["Order Type"] = (
        sales["Order Type"]
        .fillna("")
        .astype(str)
        .str.strip()
    )

    sales["Area"] = (
        sales["Area"]
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

    order_type_lower = (
        sales["Order Type"]
        .str.lower()
    )

    area_lower = (
        sales["Area"]
        .str.lower()
    )

    sales["Channel"] = "OTHERS"

    dine_in_mask = (
        order_type_lower.eq("dine in")
    )

    swiggy_mask = (
        ~dine_in_mask
        & area_lower.str.contains(
            "swiggy",
            na=False,
        )
    )

    zomato_mask = (
        ~dine_in_mask
        & area_lower.str.contains(
            "zomato",
            na=False,
        )
    )

    sales.loc[
        dine_in_mask,
        "Channel",
    ] = "DINE-IN"

    sales.loc[
        swiggy_mask,
        "Channel",
    ] = "SWIGGY"

    sales.loc[
        zomato_mask,
        "Channel",
    ] = "ZOMATO"

    return sales, all_stores


def _get_period_data(
    sales: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> pd.DataFrame:
    return sales.loc[
        sales["Date"].between(
            start_date,
            end_date,
            inclusive="both",
        )
    ].copy()


def _get_missing_dates(
    period_data: pd.DataFrame,
    start_date: pd.Timestamp,
    end_date: pd.Timestamp,
) -> list[str]:
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

    return [
        date_value.strftime("%Y-%m-%d")
        for date_value in missing_dates
    ]


def _filter_channel_section(
    period_data: pd.DataFrame,
    section_name: str,
) -> pd.DataFrame:
    if section_name == "DINE-IN":
        return period_data.loc[
            period_data["Channel"].eq(
                "DINE-IN"
            )
        ].copy()

    if section_name == "DELIVERY":
        return period_data.loc[
            period_data["Channel"].isin(
                [
                    "SWIGGY",
                    "ZOMATO",
                ]
            )
        ].copy()

    if section_name == "OVERALL":
        return period_data.copy()

    raise ValueError(
        f"Unsupported section: {section_name}"
    )


def _safe_divide(
    numerator: float,
    denominator: float,
) -> float:
    if denominator == 0:
        return 0.0

    return (
        float(numerator)
        / float(denominator)
    )


def _percentage_change(
    from_value: float,
    to_value: float,
) -> float:
    """
    When the From value is zero, keep change as 0.0%
    instead of showing an undefined/infinite percentage.
    """
    if float(from_value) == 0:
        return 0.0

    return (
        (
            float(to_value)
            - float(from_value)
        )
        / float(from_value)
        * 100
    )


def _calculate_metrics(
    dataframe: pd.DataFrame,
    number_of_days: int,
) -> dict:
    total_sales = float(
        dataframe["Sub Total"].sum()
    )

    total_txns = int(
        dataframe["Transaction_ID"].nunique()
    )

    return {
        "ads": _safe_divide(
            total_sales,
            number_of_days,
        ),
        "adt": _safe_divide(
            total_txns,
            number_of_days,
        ),
        "apt": _safe_divide(
            total_sales,
            total_txns,
        ),
    }


def _metric_comparison(
    from_metrics: dict,
    to_metrics: dict,
    metric_name: str,
) -> dict:
    from_value = float(
        from_metrics[metric_name]
    )

    to_value = float(
        to_metrics[metric_name]
    )

    return {
        "from": round(
            from_value,
            2,
        ),
        "to": round(
            to_value,
            2,
        ),
        "percentage_change": round(
            _percentage_change(
                from_value,
                to_value,
            ),
            1,
        ),
    }


def _build_store_row(
    store_name: str,
    from_section_data: pd.DataFrame,
    to_section_data: pd.DataFrame,
    from_number_of_days: int,
    to_number_of_days: int,
) -> dict:
    from_store_data = from_section_data.loc[
        from_section_data["Store"].eq(
            store_name
        )
    ]

    to_store_data = to_section_data.loc[
        to_section_data["Store"].eq(
            store_name
        )
    ]

    from_metrics = _calculate_metrics(
        dataframe=from_store_data,
        number_of_days=from_number_of_days,
    )

    to_metrics = _calculate_metrics(
        dataframe=to_store_data,
        number_of_days=to_number_of_days,
    )

    return {
        "store": store_name,
        "ads": _metric_comparison(
            from_metrics,
            to_metrics,
            "ads",
        ),
        "adt": _metric_comparison(
            from_metrics,
            to_metrics,
            "adt",
        ),
        "apt": _metric_comparison(
            from_metrics,
            to_metrics,
            "apt",
        ),
    }


def _build_section(
    section_name: str,
    all_stores: list[str],
    from_period_data: pd.DataFrame,
    to_period_data: pd.DataFrame,
    from_number_of_days: int,
    to_number_of_days: int,
) -> dict:
    from_section_data = (
        _filter_channel_section(
            from_period_data,
            section_name,
        )
    )

    to_section_data = (
        _filter_channel_section(
            to_period_data,
            section_name,
        )
    )

    rows = [
        _build_store_row(
            store_name=store_name,
            from_section_data=from_section_data,
            to_section_data=to_section_data,
            from_number_of_days=(
                from_number_of_days
            ),
            to_number_of_days=(
                to_number_of_days
            ),
        )
        for store_name in all_stores
    ]

    rows = sorted(
        rows,
        key=lambda row: (
            row["ads"]["to"],
            row["ads"]["from"],
        ),
        reverse=True,
    )

    from_total_metrics = _calculate_metrics(
        dataframe=from_section_data,
        number_of_days=from_number_of_days,
    )

    to_total_metrics = _calculate_metrics(
        dataframe=to_section_data,
        number_of_days=to_number_of_days,
    )

    total = {
        "store": "TOTAL",
        "ads": _metric_comparison(
            from_total_metrics,
            to_total_metrics,
            "ads",
        ),
        "adt": _metric_comparison(
            from_total_metrics,
            to_total_metrics,
            "adt",
        ),
        "apt": _metric_comparison(
            from_total_metrics,
            to_total_metrics,
            "apt",
        ),
    }

    return {
        "name": section_name,
        "rows": rows,
        "total": total,
    }


def get_kpi_period_comparison_report(
    data: dict,
    from_start_date_text: str,
    from_end_date_text: str,
    to_start_date_text: str,
    to_end_date_text: str,
) -> dict:
    """
    Compare store ADS, ADT and APT across two periods.

    ADS and ADT use all calendar days in their
    respective periods.
    """
    from_start_date = _parse_date(
        from_start_date_text
    )

    from_end_date = _parse_date(
        from_end_date_text
    )

    to_start_date = _parse_date(
        to_start_date_text
    )

    to_end_date = _parse_date(
        to_end_date_text
    )

    _validate_period(
        from_start_date,
        from_end_date,
        "From period",
    )

    _validate_period(
        to_start_date,
        to_end_date,
        "To period",
    )

    sales, all_stores = _prepare_sales_data(
        data
    )

    from_number_of_days = (
        from_end_date
        - from_start_date
    ).days + 1

    to_number_of_days = (
        to_end_date
        - to_start_date
    ).days + 1

    from_period_data = _get_period_data(
        sales,
        from_start_date,
        from_end_date,
    )

    to_period_data = _get_period_data(
        sales,
        to_start_date,
        to_end_date,
    )

    from_missing_dates = _get_missing_dates(
        from_period_data,
        from_start_date,
        from_end_date,
    )

    to_missing_dates = _get_missing_dates(
        to_period_data,
        to_start_date,
        to_end_date,
    )

    sections = [
        _build_section(
            section_name=section_name,
            all_stores=all_stores,
            from_period_data=from_period_data,
            to_period_data=to_period_data,
            from_number_of_days=(
                from_number_of_days
            ),
            to_number_of_days=(
                to_number_of_days
            ),
        )
        for section_name in [
            "DINE-IN",
            "DELIVERY",
            "OVERALL",
        ]
    ]

    return {
        "from_period": {
            "start_date": (
                from_start_date.strftime(
                    "%Y-%m-%d"
                )
            ),
            "end_date": (
                from_end_date.strftime(
                    "%Y-%m-%d"
                )
            ),
            "number_of_days": (
                from_number_of_days
            ),
            "missing_dates": (
                from_missing_dates
            ),
            "data_complete": (
                len(from_missing_dates) == 0
            ),
        },
        "to_period": {
            "start_date": (
                to_start_date.strftime(
                    "%Y-%m-%d"
                )
            ),
            "end_date": (
                to_end_date.strftime(
                    "%Y-%m-%d"
                )
            ),
            "number_of_days": (
                to_number_of_days
            ),
            "missing_dates": (
                to_missing_dates
            ),
            "data_complete": (
                len(to_missing_dates) == 0
            ),
        },
        "sections": sections,
        "data_complete": (
            len(from_missing_dates) == 0
            and len(to_missing_dates) == 0
        ),
    }