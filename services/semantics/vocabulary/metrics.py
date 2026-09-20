from typing import Final


# =========================================================
# CANONICAL BUSINESS METRICS
# =========================================================

METRIC_SALES: Final[str] = "sales"
METRIC_QUANTITY: Final[str] = "quantity"
METRIC_TRANSACTIONS: Final[str] = "transactions"
METRIC_ADS: Final[str] = "ads"
METRIC_ADT: Final[str] = "adt"
METRIC_APT: Final[str] = "apt"


SUPPORTED_METRICS: Final[set[str]] = {
    METRIC_SALES,
    METRIC_QUANTITY,
    METRIC_TRANSACTIONS,
    METRIC_ADS,
    METRIC_ADT,
    METRIC_APT,
}


# =========================================================
# BUSINESS METRIC VOCABULARY
# =========================================================

BUSINESS_METRICS: Final[dict[str, dict]] = {
    METRIC_SALES: {
        "display_name": "Sales",
        "full_name": "Sales",
        "description": (
            "Total sales value for the selected "
            "business scope."
        ),
        "synonyms": [
            "sales",
            "sale",
            "business",
            "revenue",
            "turnover",
            "sales value",
            "business value",
            "money made",
            "amount sold",
            "how much did we sell",
            "how much business",
            "how much revenue",
            "how much turnover",
            "collection",
            "collections",
        ],
    },

    METRIC_QUANTITY: {
        "display_name": "Qty",
        "full_name": "Quantity Sold",
        "description": (
            "Total quantity of items sold for the "
            "selected business scope."
        ),
        "synonyms": [
            "quantity",
            "qty",
            "quantity sold",
            "units",
            "units sold",
            "items sold",
            "pieces sold",
            "piece count",
            "number sold",
            "how many sold",
            "how many",
            "count sold",
            "sales volume",
            "item volume",
        ],
    },

    METRIC_TRANSACTIONS: {
        "display_name": "Txns",
        "full_name": "Transactions",
        "description": (
            "Unique business transactions, bills, "
            "invoices or orders."
        ),
        "synonyms": [
            "transactions",
            "transaction",
            "txns",
            "txn",
            "bills",
            "bill count",
            "number of bills",
            "invoices",
            "invoice count",
            "number of invoices",
            "orders",
            "order count",
            "number of orders",
            "receipts",
            "receipt count",
            "customers billed",
        ],
    },

    METRIC_ADS: {
        "display_name": "ADS",
        "full_name": "Average Daily Sales",
        "description": (
            "Average sales value per calendar day "
            "in the selected period."
        ),
        "synonyms": [
            "ads",
            "average daily sales",
            "daily average sales",
            "average sales per day",
            "sales per day",
            "average daily business",
            "daily business average",
            "daily sales average",
        ],
    },

    METRIC_ADT: {
        "display_name": "ADT",
        "full_name": "Average Daily Transactions",
        "description": (
            "Average number of transactions per "
            "calendar day in the selected period."
        ),
        "synonyms": [
            "adt",
            "average daily transactions",
            "daily average transactions",
            "average transactions per day",
            "transactions per day",
            "average daily bills",
            "daily bill average",
            "average bills per day",
            "average daily orders",
            "daily order average",
        ],
    },

    METRIC_APT: {
        "display_name": "APT",
        "full_name": "Average Per Transaction",
        "description": (
            "Average sales value generated per "
            "transaction."
        ),
        "synonyms": [
            "apt",
            "average per transaction",
            "average transaction value",
            "average bill value",
            "average bill",
            "average ticket size",
            "average order value",
            "aov",
            "atv",
            "sales per transaction",
            "revenue per transaction",
            "business per bill",
            "sales per bill",
            "value per bill",
        ],
    },
}


# =========================================================
# METRIC LOOKUP HELPERS
# =========================================================


def get_metric_definition(
    metric_name: str,
) -> dict:
    """
    Return the vocabulary definition for a canonical metric.

    Example:
        get_metric_definition("apt")
    """
    normalized_metric = (
        str(metric_name)
        .strip()
        .lower()
    )

    if normalized_metric not in BUSINESS_METRICS:
        raise ValueError(
            f"Unsupported business metric: {metric_name}"
        )

    return {
        **BUSINESS_METRICS[
            normalized_metric
        ],
        "synonyms": list(
            BUSINESS_METRICS[
                normalized_metric
            ]["synonyms"]
        ),
    }


def get_metric_display_name(
    metric_name: str,
) -> str:
    """
    Return the short display name for a canonical metric.

    Examples:
        sales -> Sales
        quantity -> Qty
        transactions -> Txns
        ads -> ADS
    """
    metric_definition = get_metric_definition(
        metric_name
    )

    return str(
        metric_definition["display_name"]
    )


def get_metric_full_name(
    metric_name: str,
) -> str:
    """
    Return the full business name for a canonical metric.

    Examples:
        quantity -> Quantity Sold
        ads -> Average Daily Sales
        apt -> Average Per Transaction
    """
    metric_definition = get_metric_definition(
        metric_name
    )

    return str(
        metric_definition["full_name"]
    )


def get_metric_synonyms(
    metric_name: str,
) -> list[str]:
    """
    Return all known business-language synonyms
    for a canonical metric.
    """
    metric_definition = get_metric_definition(
        metric_name
    )

    return list(
        metric_definition["synonyms"]
    )


def get_all_metric_synonyms() -> dict[str, list[str]]:
    """
    Return every canonical metric with its vocabulary.

    This can later be supplied to the RAL intent layer
    without exposing calculation logic.
    """
    return {
        metric_name: list(
            metric_definition["synonyms"]
        )
        for (
            metric_name,
            metric_definition,
        ) in BUSINESS_METRICS.items()
    }


def build_metric_vocabulary_prompt() -> str:
    """
    Build a compact text representation of the business
    metric vocabulary for the GPT intent parser.

    This contains business terminology only.

    It deliberately contains:
    - no formulas,
    - no pandas logic,
    - no Excel column names,
    - no client-specific information.
    """
    prompt_lines = [
        "Supported business metrics:",
    ]

    for (
        metric_name,
        metric_definition,
    ) in BUSINESS_METRICS.items():
        display_name = (
            metric_definition[
                "display_name"
            ]
        )

        full_name = (
            metric_definition[
                "full_name"
            ]
        )

        synonyms = ", ".join(
            metric_definition[
                "synonyms"
            ]
        )

        prompt_lines.append(
            f"- Canonical metric: {metric_name}"
        )

        prompt_lines.append(
            f"  Display name: {display_name}"
        )

        prompt_lines.append(
            f"  Full name: {full_name}"
        )

        prompt_lines.append(
            f"  Common expressions: {synonyms}"
        )

    return "\n".join(
        prompt_lines
    )

# =========================================================
# METRIC CALCULATIONS
# =========================================================

import pandas as pd


SALES_COLUMN = "Sub Total"
QUANTITY_COLUMN = "Qty"
STORE_COLUMN = "Restaurant"
DATE_COLUMN = "Date"
INVOICE_COLUMN = "Invoice No"


def calculate_sales(
    filtered_df: pd.DataFrame,
) -> float:
    """
    Total Sales.
    """
    return float(
        filtered_df[
            SALES_COLUMN
        ].fillna(0).sum()
    )


def calculate_quantity(
    filtered_df: pd.DataFrame,
) -> float:
    """
    Total Quantity Sold.
    """
    return float(
        filtered_df[
            QUANTITY_COLUMN
        ].fillna(0).sum()
    )


def calculate_transactions(
    filtered_df: pd.DataFrame,
) -> int:
    """
    Unique business transactions.
    """

    if filtered_df.empty:
        return 0

    transaction_ids = (
        filtered_df[
            STORE_COLUMN
        ].astype(str)
        + "|"
        + filtered_df[
            DATE_COLUMN
        ].astype(str)
        + "|"
        + filtered_df[
            INVOICE_COLUMN
        ].astype(str)
    )

    return int(
        transaction_ids.nunique()
    )


def calculate_ads(
    filtered_df: pd.DataFrame,
) -> float:

    sales = calculate_sales(
        filtered_df
    )

    if filtered_df.empty:
        return 0

    days = (
        pd.to_datetime(
            filtered_df[
                DATE_COLUMN
            ]
        )
        .dt.normalize()
        .nunique()
    )

    if days == 0:
        return 0

    return sales / days


def calculate_adt(
    filtered_df: pd.DataFrame,
) -> float:

    txns = calculate_transactions(
        filtered_df
    )

    if filtered_df.empty:
        return 0

    days = (
        pd.to_datetime(
            filtered_df[
                DATE_COLUMN
            ]
        )
        .dt.normalize()
        .nunique()
    )

    if days == 0:
        return 0

    return txns / days


def calculate_apt(
    filtered_df: pd.DataFrame,
) -> float:

    sales = calculate_sales(
        filtered_df
    )

    txns = calculate_transactions(
        filtered_df
    )

    if txns == 0:
        return 0

    return sales / txns


def calculate_metric(
    metric_name: str,
    filtered_df: pd.DataFrame,
):
    """
    Universal metric dispatcher.
    """

    metric_name = (
        metric_name
        .strip()
        .lower()
    )

    if metric_name == METRIC_SALES:
        return calculate_sales(
            filtered_df
        )

    if metric_name == METRIC_QUANTITY:
        return calculate_quantity(
            filtered_df
        )

    if metric_name == METRIC_TRANSACTIONS:
        return calculate_transactions(
            filtered_df
        )

    if metric_name == METRIC_ADS:
        return calculate_ads(
            filtered_df
        )

    if metric_name == METRIC_ADT:
        return calculate_adt(
            filtered_df
        )

    if metric_name == METRIC_APT:
        return calculate_apt(
            filtered_df
        )

    raise ValueError(
        f"Unsupported metric: {metric_name}"
    )