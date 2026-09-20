from __future__ import annotations

from typing import Any, Final
import unicodedata

import pandas as pd

from services.semantics.builders.channel_builder import (
    DERIVED_AGGREGATOR_COLUMN,
    DERIVED_CHANNEL_COLUMN,
    enrich_channel_dimensions,
)
from services.semantics.builders.product_builder import (
    build_product_dictionary,
)
from services.semantics.builders.store_builder import (
    build_store_dictionary,
)
from services.semantics.vocabulary.metrics import (
    calculate_metric,
)


# =========================================================
# SOURCE / DERIVED COLUMNS
# =========================================================

SOURCE_STORE_COLUMN: Final[str] = "Restaurant"
CATEGORY_COLUMN: Final[str] = "Category"
ITEM_COLUMN: Final[str] = "Item Name"

DERIVED_STORE_COLUMN: Final[str] = "__RestaurantAI_Store"
DERIVED_CATEGORY_COLUMN: Final[str] = "__RestaurantAI_Category"
DERIVED_ITEM_COLUMN: Final[str] = "__RestaurantAI_Item"

SUPPORTED_GROUPING_DIMENSIONS: Final[set[str]] = {
    "store",
    "channel",
    "aggregator",
    "category",
    "item",
}


# =========================================================
# TEXT HELPERS
# =========================================================


def _clean_text(
    value: Any,
) -> str:
    if pd.isna(value):
        return ""

    cleaned_value = unicodedata.normalize(
        "NFKC",
        str(value),
    )

    for invisible_character in (
        "\u200b",
        "\u200c",
        "\u200d",
        "\ufeff",
    ):
        cleaned_value = cleaned_value.replace(
            invisible_character,
            "",
        )

    return " ".join(
        cleaned_value.strip().split()
    )


def _normalize_text(
    value: Any,
) -> str:
    return _clean_text(
        value
    ).lower()


# =========================================================
# STORE CANONICALIZATION
# =========================================================


def _build_store_lookup(
    data: dict,
) -> dict[str, str]:
    store_dictionary = (
        build_store_dictionary(
            data=data
        )
    )

    lookup: dict[str, str] = {}

    for (
        canonical_name,
        store_definition,
    ) in store_dictionary.items():
        lookup[
            _normalize_text(
                canonical_name
            )
        ] = canonical_name

        for alias in store_definition.get(
            "aliases",
            [],
        ):
            lookup[
                _normalize_text(
                    alias
                )
            ] = canonical_name

    return lookup


def _canonicalize_store_series(
    sales: pd.DataFrame,
    data: dict,
) -> pd.Series:
    if SOURCE_STORE_COLUMN not in sales.columns:
        raise ValueError(
            "Sales data is missing Restaurant column."
        )

    lookup = _build_store_lookup(
        data
    )

    return sales[
        SOURCE_STORE_COLUMN
    ].map(
        lambda value: lookup.get(
            _normalize_text(value),
            _clean_text(value)
            or "Unspecified",
        )
    )


# =========================================================
# PRODUCT CANONICALIZATION
# =========================================================


def _build_product_lookups(
    data: dict,
) -> tuple[
    dict[str, str],
    dict[str, str],
    dict[str, str],
]:
    product_dictionary = (
        build_product_dictionary(
            data=data
        )
    )

    category_lookup: dict[
        str,
        str,
    ] = {}

    item_lookup: dict[
        str,
        str,
    ] = {}

    item_to_category_lookup: dict[
        str,
        str,
    ] = {}

    for (
        canonical_category,
        category_definition,
    ) in product_dictionary.items():
        category_lookup[
            _normalize_text(
                canonical_category
            )
        ] = canonical_category

        items = category_definition.get(
            "items",
            {},
        )

        for (
            canonical_item,
            item_definition,
        ) in items.items():
            accepted_item_names = {
                canonical_item,
                *item_definition.get(
                    "raw_names",
                    [],
                ),
                *item_definition.get(
                    "aliases",
                    [],
                ),
            }

            for item_name in accepted_item_names:
                normalized_item = (
                    _normalize_text(
                        item_name
                    )
                )

                if not normalized_item:
                    continue

                item_lookup[
                    normalized_item
                ] = canonical_item

                item_to_category_lookup[
                    normalized_item
                ] = canonical_category

    return (
        category_lookup,
        item_lookup,
        item_to_category_lookup,
    )


def _canonicalize_product_columns(
    sales: pd.DataFrame,
    data: dict,
) -> tuple[
    pd.Series,
    pd.Series,
]:
    if CATEGORY_COLUMN not in sales.columns:
        raise ValueError(
            "Sales data is missing Category column."
        )

    if ITEM_COLUMN not in sales.columns:
        raise ValueError(
            "Sales data is missing Item Name column."
        )

    (
        category_lookup,
        item_lookup,
        item_to_category_lookup,
    ) = _build_product_lookups(
        data
    )

    canonical_items = sales[
        ITEM_COLUMN
    ].map(
        lambda value: item_lookup.get(
            _normalize_text(value),
            _clean_text(value)
            or "Unspecified",
        )
    )

    canonical_categories: list[str] = []

    for (
        raw_category,
        raw_item,
    ) in zip(
        sales[CATEGORY_COLUMN],
        sales[ITEM_COLUMN],
    ):
        normalized_item = (
            _normalize_text(
                raw_item
            )
        )

        mapped_category = (
            item_to_category_lookup.get(
                normalized_item
            )
        )

        if mapped_category:
            canonical_categories.append(
                mapped_category
            )
            continue

        normalized_category = (
            _normalize_text(
                raw_category
            )
        )

        canonical_categories.append(
            category_lookup.get(
                normalized_category,
                _clean_text(
                    raw_category
                )
                or "Unmapped",
            )
        )

    return (
        pd.Series(
            canonical_categories,
            index=sales.index,
        ),
        canonical_items,
    )


# =========================================================
# GROUPING PREPARATION
# =========================================================


def _prepare_grouping_dataframe(
    filtered_sales: pd.DataFrame,
    data: dict,
) -> pd.DataFrame:
    """
    Add canonical grouping columns without changing the raw
    columns or business metric inputs.

    Most importantly, Channel/Aggregator comes from the same
    channel_builder used by Filter Engine:

        Order Type -> Channel
        Area       -> Delivery Aggregator
    """
    prepared = (
        enrich_channel_dimensions(
            filtered_sales
        )
    )

    prepared[
        DERIVED_STORE_COLUMN
    ] = _canonicalize_store_series(
        prepared,
        data,
    )

    (
        canonical_categories,
        canonical_items,
    ) = _canonicalize_product_columns(
        prepared,
        data,
    )

    prepared[
        DERIVED_CATEGORY_COLUMN
    ] = canonical_categories

    prepared[
        DERIVED_ITEM_COLUMN
    ] = canonical_items

    return prepared


def _grouping_column(
    dimension: str,
) -> str:
    mapping = {
        "store": DERIVED_STORE_COLUMN,
        "channel": DERIVED_CHANNEL_COLUMN,
        "aggregator": DERIVED_AGGREGATOR_COLUMN,
        "category": DERIVED_CATEGORY_COLUMN,
        "item": DERIVED_ITEM_COLUMN,
    }

    return mapping[
        dimension
    ]


# =========================================================
# PUBLIC GROUPING ENGINE
# =========================================================


def calculate_grouped_metric(
    filtered_sales: pd.DataFrame,
    data: dict,
    ral_request: dict,
) -> dict:
    """
    Calculate one RestaurantAI metric split by one or more
    canonical business dimensions.

    Output contract is intentionally unchanged:

        {
            "metric": "sales",
            "grouping_dimensions": ["store", "channel"],
            "row_count": ...,
            "rows": [
                {
                    "groups": {
                        "store": "AMB Mall",
                        "channel": "Dine In"
                    },
                    "metric_value": 396464,
                    "matching_rows": ...
                }
            ]
        }

    This keeps Trend Engine, Presentation Engine and Message
    Router compatible.
    """
    if not isinstance(
        filtered_sales,
        pd.DataFrame,
    ):
        raise ValueError(
            "Filtered sales must be a DataFrame."
        )

    if not isinstance(
        ral_request,
        dict,
    ):
        raise ValueError(
            "RAL request must be an object."
        )

    grouping = ral_request.get(
        "grouping",
        {},
    )

    if not isinstance(
        grouping,
        dict,
    ):
        raise ValueError(
            "RAL grouping must be an object."
        )

    grouping_dimensions = list(
        grouping.get(
            "dimensions",
            [],
        )
    )

    if not grouping_dimensions:
        raise ValueError(
            "At least one grouping dimension is required."
        )

    normalized_dimensions = [
        str(dimension)
        .strip()
        .lower()
        for dimension in grouping_dimensions
    ]

    unsupported_dimensions = [
        dimension
        for dimension in normalized_dimensions
        if dimension
        not in SUPPORTED_GROUPING_DIMENSIONS
    ]

    if unsupported_dimensions:
        raise ValueError(
            "Unsupported grouping dimensions: "
            + ", ".join(
                unsupported_dimensions
            )
        )

    metric_name = str(
        ral_request.get(
            "metric",
            "",
        )
    ).strip().lower()

    if not metric_name:
        raise ValueError(
            "RAL metric is required for grouping."
        )

    prepared = (
        _prepare_grouping_dataframe(
            filtered_sales=filtered_sales,
            data=data,
        )
    )

    # Aggregator is meaningful only for Delivery rows.
    # For non-delivery rows it remains blank and is excluded
    # only when aggregator is explicitly a grouping dimension.
    if "aggregator" in normalized_dimensions:
        prepared = prepared.loc[
            prepared[
                DERIVED_AGGREGATOR_COLUMN
            ]
            .astype(str)
            .str.strip()
            .ne("")
        ].copy()

    group_columns = [
        _grouping_column(
            dimension
        )
        for dimension in normalized_dimensions
    ]

    grouped_rows: list[dict] = []

    # dropna=False is an explicit guardrail: introducing a
    # dimension must never silently delete a valid store.
    grouped_iterator = prepared.groupby(
        group_columns,
        dropna=False,
        sort=False,
    )

    for (
        group_key,
        group_df,
    ) in grouped_iterator:
        if len(group_columns) == 1:
            # pandas may return either a scalar or a one-item
            # tuple when grouping with a one-column list.
            # Normalize both forms so labels never appear as
            # strings such as "('Zomato',)".
            if (
                isinstance(
                    group_key,
                    tuple,
                )
                and len(group_key) == 1
            ):
                group_values = (
                    group_key[0],
                )
            else:
                group_values = (
                    group_key,
                )
        else:
            group_values = tuple(
                group_key
            )

        groups = {
            dimension: (
                _clean_text(value)
                or "Unspecified"
            )
            for (
                dimension,
                value,
            ) in zip(
                normalized_dimensions,
                group_values,
            )
        }

        metric_value = calculate_metric(
            metric_name=metric_name,
            filtered_df=group_df,
        )

        grouped_rows.append(
            {
                "groups": groups,
                "metric_value": metric_value,
                "matching_rows": len(
                    group_df
                ),
            }
        )

    # Preserve the useful current behaviour: highest-value
    # combinations first for text presentation. Pivot renderer
    # reorders rows/columns as needed for management tables.
    grouped_rows.sort(
        key=lambda row: float(
            row.get(
                "metric_value",
                0,
            )
        ),
        reverse=True,
    )

    return {
        "metric": metric_name,
        "grouping_dimensions": (
            normalized_dimensions
        ),
        "row_count": len(
            grouped_rows
        ),
        "rows": grouped_rows,
    }
