from typing import Any, Final
import unicodedata

import pandas as pd

from services.semantics.builders.channel_builder import (
    AGGREGATOR_OTHERS,
    AGGREGATOR_SWIGGY,
    AGGREGATOR_ZOMATO,
    CHANNEL_DELIVERY,
    CHANNEL_DINE_IN,
    CHANNEL_OTHERS,
    CHANNEL_TAKE_AWAY,
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


# =========================================================
# AUBERRY V1 SOURCE COLUMNS
# =========================================================

SALES_SHEET_KEY: Final[str] = "sales"

DATE_COLUMN: Final[str] = "Date"
SOURCE_STORE_COLUMN: Final[str] = "Restaurant"
AREA_COLUMN: Final[str] = "Area"
CATEGORY_COLUMN: Final[str] = "Category"
ITEM_COLUMN: Final[str] = "Item Name"


# =========================================================
# TEXT HELPERS
# =========================================================


def _clean_text(
    value: Any,
) -> str:
    """
    Convert a value into clean, consistently comparable text.

    In addition to ordinary trimming, this removes invisible
    zero-width characters and normalizes Unicode so visually
    identical category/item names match deterministically.
    """
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
    """
    Normalize text for deterministic matching.

    This is used only for comparisons.
    It does not change the original DataFrame values.
    """
    return _clean_text(
        value
    ).lower()


def _normalized_series(
    series: pd.Series,
) -> pd.Series:
    """
    Return a normalized text version of a pandas Series.
    """
    return (
        series
        .fillna("")
        .map(_normalize_text)
    )


# =========================================================
# VALIDATION
# =========================================================


def _validate_filter_inputs(
    data: dict,
    ral_request: dict,
) -> None:
    """
    Validate the minimum structure required by the
    RAL Filter Engine.
    """
    if not isinstance(
        data,
        dict,
    ):
        raise ValueError(
            "Client data must be an object."
        )

    if SALES_SHEET_KEY not in data:
        raise ValueError(
            "Sales data was not found."
        )

    if not isinstance(
        ral_request,
        dict,
    ):
        raise ValueError(
            "RAL request must be an object."
        )

    required_ral_fields = {
        "time",
        "stores",
        "regions",
        "channels",
        "aggregators",
        "categories",
        "items",
    }

    missing_ral_fields = (
        required_ral_fields
        - set(ral_request.keys())
    )

    if missing_ral_fields:
        raise ValueError(
            "RAL request is missing filter fields: "
            + ", ".join(
                sorted(missing_ral_fields)
            )
        )

    if ral_request["regions"]:
        raise ValueError(
            "Region filtering is not connected yet."
        )


def _validate_sales_columns(
    sales: pd.DataFrame,
) -> None:
    """
    Validate the physical Auberry columns currently required
    by the filter engine.
    """
    required_columns = {
        DATE_COLUMN,
        SOURCE_STORE_COLUMN,
        CATEGORY_COLUMN,
        ITEM_COLUMN,
    }

    missing_columns = (
        required_columns
        - set(sales.columns)
    )

    if missing_columns:
        raise ValueError(
            "Sales data is missing required columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )


# =========================================================
# TIME FILTER
# =========================================================


def _apply_time_filter(
    sales: pd.DataFrame,
    ral_request: dict,
) -> pd.DataFrame:
    """
    Apply the inclusive RAL start-date and end-date filter.

    Relative periods such as last_month must already have
    been resolved by services.semantics.vocabulary.time.resolve_ral_time.
    """
    time_value = ral_request[
        "time"
    ]

    if not isinstance(
        time_value,
        dict,
    ):
        raise ValueError(
            "RAL time must be an object."
        )

    start_date_text = time_value.get(
        "start_date"
    )

    end_date_text = time_value.get(
        "end_date"
    )

    if (
        start_date_text is None
        and end_date_text is None
    ):
        raise ValueError(
            "The requested time period has not been "
            "resolved into dates."
        )

    if (
        start_date_text is None
        or end_date_text is None
    ):
        raise ValueError(
            "Both start_date and end_date are required."
        )

    try:
        start_date = pd.Timestamp(
            start_date_text
        ).normalize()

        end_date = pd.Timestamp(
            end_date_text
        ).normalize()

    except Exception as error:
        raise ValueError(
            "RAL dates must use valid YYYY-MM-DD values."
        ) from error

    if start_date > end_date:
        raise ValueError(
            "The start date cannot be after the end date."
        )

    parsed_sales_dates = pd.to_datetime(
        sales[DATE_COLUMN],
        errors="coerce",
        dayfirst=True,
    ).dt.normalize()

    valid_date_mask = (
        parsed_sales_dates.notna()
        & parsed_sales_dates.between(
            start_date,
            end_date,
            inclusive="both",
        )
    )

    return sales.loc[
        valid_date_mask
    ].copy()


# =========================================================
# STORE FILTER
# =========================================================


def _apply_store_filter(
    filtered_sales: pd.DataFrame,
    data: dict,
    ral_request: dict,
) -> pd.DataFrame:
    """
    Filter raw Restaurant values using the canonical stores
    selected by RAL.

    The Store Builder supplies the relationship:

        raw Restaurant name
            ->
        canonical short store name
    """
    requested_stores = ral_request[
        "stores"
    ]

    if not requested_stores:
        return filtered_sales

    store_dictionary = (
        build_store_dictionary(
            data=data
        )
    )

    requested_canonical_names = {
        _normalize_text(
            store_name
        )
        for store_name in requested_stores
    }

    accepted_raw_store_names: set[str] = set()

    unresolved_stores: list[str] = []

    for requested_store in requested_stores:
        requested_normalized = (
            _normalize_text(
                requested_store
            )
        )

        matching_definition = None

        for (
            canonical_name,
            store_definition,
        ) in store_dictionary.items():
            if (
                _normalize_text(
                    canonical_name
                )
                == requested_normalized
            ):
                matching_definition = (
                    store_definition
                )

                break

        if matching_definition is None:
            unresolved_stores.append(
                requested_store
            )

            continue

        aliases = matching_definition.get(
            "aliases",
            [],
        )

        for alias in aliases:
            accepted_raw_store_names.add(
                _normalize_text(
                    alias
                )
            )

    if unresolved_stores:
        raise ValueError(
            "Unknown store selection: "
            + ", ".join(
                unresolved_stores
            )
        )

    # Include canonical names themselves as an additional
    # safeguard when the raw sales data already uses them.
    accepted_raw_store_names.update(
        requested_canonical_names
    )

    store_mask = _normalized_series(
        filtered_sales[
            SOURCE_STORE_COLUMN
        ]
    ).isin(
        accepted_raw_store_names
    )

    return filtered_sales.loc[
        store_mask
    ].copy()


# =========================================================
# CHANNEL AND AGGREGATOR FILTER
# =========================================================


def _canonical_channel_names() -> set[str]:
    return {
        _normalize_text(
            CHANNEL_DINE_IN
        ),
        _normalize_text(
            CHANNEL_DELIVERY
        ),
        _normalize_text(
            CHANNEL_TAKE_AWAY
        ),
        _normalize_text(
            CHANNEL_OTHERS
        ),
    }


def _canonical_aggregator_names() -> set[str]:
    return {
        _normalize_text(
            AGGREGATOR_SWIGGY
        ),
        _normalize_text(
            AGGREGATOR_ZOMATO
        ),
        _normalize_text(
            AGGREGATOR_OTHERS
        ),
    }


def _apply_channel_filter(
    filtered_sales: pd.DataFrame,
    data: dict,
    ral_request: dict,
) -> pd.DataFrame:
    """
    Apply Auberry's canonical parent-channel and aggregator
    filters using the SAME deterministic derivation used by
    the Grouping Engine.

    Parent Channel source:
        Order Type

    Delivery Aggregator source:
        Area

    This replaces the old assumption that Area itself was the
    parent channel.
    """
    requested_channels = ral_request[
        "channels"
    ]

    requested_aggregators = ral_request[
        "aggregators"
    ]

    if (
        not requested_channels
        and not requested_aggregators
    ):
        # Still enrich the dimensions so downstream grouping
        # can use the same canonical Channel/Aggregator values.
        return enrich_channel_dimensions(
            filtered_sales
        )

    enriched_sales = (
        enrich_channel_dimensions(
            filtered_sales
        )
    )

    if requested_channels:
        normalized_requested_channels = {
            _normalize_text(
                channel_name
            )
            for channel_name in requested_channels
        }

        unknown_channels = (
            normalized_requested_channels
            - _canonical_channel_names()
        )

        if unknown_channels:
            raise ValueError(
                "Unknown channel selection: "
                + ", ".join(
                    sorted(
                        unknown_channels
                    )
                )
            )

        channel_mask = (
            _normalized_series(
                enriched_sales[
                    DERIVED_CHANNEL_COLUMN
                ]
            )
            .isin(
                normalized_requested_channels
            )
        )

        enriched_sales = (
            enriched_sales.loc[
                channel_mask
            ].copy()
        )

    if requested_aggregators:
        normalized_requested_aggregators = {
            _normalize_text(
                aggregator_name
            )
            for aggregator_name
            in requested_aggregators
        }

        unknown_aggregators = (
            normalized_requested_aggregators
            - _canonical_aggregator_names()
        )

        if unknown_aggregators:
            raise ValueError(
                "Unknown aggregator selection: "
                + ", ".join(
                    sorted(
                        unknown_aggregators
                    )
                )
            )

        # Aggregators are meaningful only inside Delivery.
        delivery_mask = (
            enriched_sales[
                DERIVED_CHANNEL_COLUMN
            ]
            == CHANNEL_DELIVERY
        )

        aggregator_mask = (
            _normalized_series(
                enriched_sales[
                    DERIVED_AGGREGATOR_COLUMN
                ]
            )
            .isin(
                normalized_requested_aggregators
            )
        )

        enriched_sales = (
            enriched_sales.loc[
                delivery_mask
                & aggregator_mask
            ].copy()
        )

    return enriched_sales


# =========================================================
# CATEGORY AND ITEM FILTER
# =========================================================


def _apply_product_filter(
    filtered_sales: pd.DataFrame,
    data: dict,
    ral_request: dict,
) -> pd.DataFrame:
    """
    Apply canonical Category and Item filters.

    Category matching deliberately uses two valid paths:

    1. Direct match against the physical Category column.
    2. Membership of Item Name in the Product Builder's
       category-to-item dictionary.

    This prevents a genuine category result from becoming
    zero merely because some transaction rows contain an
    inconsistent, blank or visually different Category value.
    """
    requested_categories = ral_request[
        "categories"
    ]

    requested_items = ral_request[
        "items"
    ]

    if (
        not requested_categories
        and not requested_items
    ):
        return filtered_sales

    product_dictionary = (
        build_product_dictionary(
            data=data
        )
    )

    normalized_category_definitions = {
        _normalize_text(
            category_name
        ): category_definition
        for (
            category_name,
            category_definition,
        ) in product_dictionary.items()
    }

    valid_categories = set(
        normalized_category_definitions.keys()
    )

    valid_items: set[str] = set()

    for category_definition in (
        product_dictionary.values()
    ):
        items = category_definition.get(
            "items",
            {},
        )

        for (
            item_name,
            item_definition,
        ) in items.items():
            valid_items.add(
                _normalize_text(
                    item_name
                )
            )

            for raw_name in item_definition.get(
                "raw_names",
                [],
            ):
                valid_items.add(
                    _normalize_text(
                        raw_name
                    )
                )

            for alias in item_definition.get(
                "aliases",
                [],
            ):
                valid_items.add(
                    _normalize_text(
                        alias
                    )
                )

    normalized_requested_categories = {
        _normalize_text(
            category_name
        )
        for category_name
        in requested_categories
    }

    normalized_requested_items = {
        _normalize_text(
            item_name
        )
        for item_name
        in requested_items
    }

    unknown_categories = (
        normalized_requested_categories
        - valid_categories
    )

    if unknown_categories:
        raise ValueError(
            "Unknown category selection: "
            + ", ".join(
                sorted(
                    unknown_categories
                )
            )
        )

    unknown_items = (
        normalized_requested_items
        - valid_items
    )

    if unknown_items:
        raise ValueError(
            "Unknown item selection: "
            + ", ".join(
                sorted(
                    unknown_items
                )
            )
        )

    if requested_categories:
        accepted_category_item_names: set[str] = set()

        for normalized_category in (
            normalized_requested_categories
        ):
            category_definition = (
                normalized_category_definitions[
                    normalized_category
                ]
            )

            category_items = (
                category_definition.get(
                    "items",
                    {},
                )
            )

            for (
                item_name,
                item_definition,
            ) in category_items.items():
                accepted_category_item_names.add(
                    _normalize_text(
                        item_name
                    )
                )

                for raw_name in item_definition.get(
                    "raw_names",
                    [],
                ):
                    accepted_category_item_names.add(
                        _normalize_text(
                            raw_name
                        )
                    )

                for alias in item_definition.get(
                    "aliases",
                    [],
                ):
                    accepted_category_item_names.add(
                        _normalize_text(
                            alias
                        )
                    )

        direct_category_mask = (
            _normalized_series(
                filtered_sales[
                    CATEGORY_COLUMN
                ]
            ).isin(
                normalized_requested_categories
            )
        )

        item_membership_mask = (
            _normalized_series(
                filtered_sales[
                    ITEM_COLUMN
                ]
            ).isin(
                accepted_category_item_names
            )
        )

        category_mask = (
            direct_category_mask
            | item_membership_mask
        )

        filtered_sales = filtered_sales.loc[
            category_mask
        ].copy()

    if requested_items:
        item_mask = (
            _normalized_series(
                filtered_sales[
                    ITEM_COLUMN
                ]
            ).isin(
                normalized_requested_items
            )
        )

        filtered_sales = filtered_sales.loc[
            item_mask
        ].copy()

    return filtered_sales


# =========================================================
# PUBLIC FILTER ENGINE
# =========================================================


def apply_ral_filters(
    data: dict,
    ral_request: dict,
) -> pd.DataFrame:
    """
    Apply all currently supported RAL dimensions to the
    active client's sales data.

    Filter order:

        1. Time
        2. Store
        3. Channel
        4. Aggregator
        5. Category
        6. Item

    Returns a new filtered DataFrame.

    This function deliberately does not calculate:

    - Sales
    - Quantity
    - Transactions
    - ADS
    - ADT
    - APT

    Metric calculations remain the responsibility of
    services/vocabulary/metrics.py.
    """
    _validate_filter_inputs(
        data=data,
        ral_request=ral_request,
    )

    sales = data[
        SALES_SHEET_KEY
    ].copy()

    sales.columns = (
        sales.columns
        .astype(str)
        .str.strip()
    )

    _validate_sales_columns(
        sales
    )

    filtered_sales = _apply_time_filter(
        sales=sales,
        ral_request=ral_request,
    )

    filtered_sales = _apply_store_filter(
        filtered_sales=filtered_sales,
        data=data,
        ral_request=ral_request,
    )

    filtered_sales = _apply_channel_filter(
        filtered_sales=filtered_sales,
        data=data,
        ral_request=ral_request,
    )

    filtered_sales = _apply_product_filter(
        filtered_sales=filtered_sales,
        data=data,
        ral_request=ral_request,
    )

    return filtered_sales.reset_index(
        drop=True
    )