from __future__ import annotations

import re
import unicodedata
from typing import Any, Final

import pandas as pd


# =========================================================
# CANONICAL RESTAURANTAI CHANNELS
# =========================================================

CHANNEL_DINE_IN: Final[str] = "Dine In"
CHANNEL_DELIVERY: Final[str] = "Delivery"
CHANNEL_TAKE_AWAY: Final[str] = "Take Away"
CHANNEL_OTHERS: Final[str] = "Others"

AGGREGATOR_SWIGGY: Final[str] = "Swiggy"
AGGREGATOR_ZOMATO: Final[str] = "Zomato"
AGGREGATOR_OTHERS: Final[str] = "Others"

DERIVED_CHANNEL_COLUMN: Final[str] = "__RestaurantAI_Channel"
DERIVED_AGGREGATOR_COLUMN: Final[str] = "__RestaurantAI_Aggregator"


# =========================================================
# AUBERRY PHYSICAL SOURCE COLUMNS
# =========================================================

# Petpooja exports have appeared with minor capitalization
# differences over time. We therefore resolve these columns
# case-insensitively instead of hard-coding one spelling.
ORDER_TYPE_CANDIDATES: Final[tuple[str, ...]] = (
    "Order Type",
    "Order type",
    "order type",
)

AREA_CANDIDATES: Final[tuple[str, ...]] = (
    "Area",
    "area",
)


# =========================================================
# TEXT HELPERS
# =========================================================


def _clean_text(value: Any) -> str:
    if pd.isna(value):
        return ""

    cleaned = unicodedata.normalize(
        "NFKC",
        str(value),
    )

    return " ".join(
        cleaned.strip().split()
    )


def _normalize_text(value: Any) -> str:
    cleaned = _clean_text(value).lower()

    cleaned = re.sub(
        r"[^a-z0-9]+",
        " ",
        cleaned,
    ).strip()

    return cleaned


def _compact_text(value: Any) -> str:
    return _normalize_text(value).replace(
        " ",
        "",
    )


def _normalized_column_key(value: Any) -> str:
    return re.sub(
        r"[^a-z0-9]+",
        "",
        str(value).strip().lower(),
    )


def _resolve_column_name(
    sales: pd.DataFrame,
    candidates: tuple[str, ...],
) -> str:
    normalized_columns = {
        _normalized_column_key(column): column
        for column in sales.columns
    }

    for candidate in candidates:
        matching_column = normalized_columns.get(
            _normalized_column_key(candidate)
        )

        if matching_column is not None:
            return matching_column

    raise ValueError(
        "Sales data is missing required column. "
        "Expected one of: "
        + ", ".join(candidates)
    )


# =========================================================
# AUBERRY CHANNEL CLASSIFICATION
# =========================================================


def classify_channel_from_order_type(
    order_type: Any,
) -> str:
    """
    Auberry parent-channel rule.

    Petpooja source:
        Order Type

    Business mapping:
        Dine In          -> Dine In
        Delivery(Parcel) -> Delivery
        Pick Up          -> Take Away
        anything else    -> Others

    Matching is tolerant of spaces, hyphens, brackets and
    ordinary capitalization differences.
    """
    normalized = _normalize_text(
        order_type
    )

    compact = _compact_text(
        order_type
    )

    if (
        normalized == "dine in"
        or "dinein" in compact
    ):
        return CHANNEL_DINE_IN

    if (
        normalized.startswith(
            "delivery"
        )
        or "deliveryparcel" in compact
        or compact == "delivery"
    ):
        return CHANNEL_DELIVERY

    if (
        normalized in {
            "pick up",
            "pickup",
        }
        or compact == "pickup"
    ):
        return CHANNEL_TAKE_AWAY

    return CHANNEL_OTHERS


def classify_delivery_aggregator(
    channel: str,
    area: Any,
) -> str:
    """
    Auberry Delivery aggregator rule.

    Area is used ONLY after the row has been classified as
    Delivery from Order Type.

    Delivery + Area contains Swiggy -> Swiggy
    Delivery + Area contains Zomato -> Zomato
    Delivery + blank/unknown Area   -> Others

    For non-Delivery rows aggregator is not applicable and is
    kept blank. This prevents Dine In / Take Away from being
    incorrectly counted as aggregator 'Others'.
    """
    if channel != CHANNEL_DELIVERY:
        return ""

    normalized_area = _normalize_text(
        area
    )

    if "swiggy" in normalized_area:
        return AGGREGATOR_SWIGGY

    if "zomato" in normalized_area:
        return AGGREGATOR_ZOMATO

    return AGGREGATOR_OTHERS


def enrich_channel_dimensions(
    sales: pd.DataFrame,
) -> pd.DataFrame:
    """
    Return a copy of sales with deterministic RestaurantAI
    Channel and Aggregator columns added.

    This is the single source of truth used by BOTH filtering
    and grouping, so the same business rule cannot diverge
    across engines.
    """
    enriched = sales.copy()

    order_type_column = _resolve_column_name(
        enriched,
        ORDER_TYPE_CANDIDATES,
    )

    area_column = _resolve_column_name(
        enriched,
        AREA_CANDIDATES,
    )

    enriched[DERIVED_CHANNEL_COLUMN] = (
        enriched[order_type_column]
        .map(
            classify_channel_from_order_type
        )
    )

    enriched[DERIVED_AGGREGATOR_COLUMN] = [
        classify_delivery_aggregator(
            channel=channel,
            area=area,
        )
        for channel, area in zip(
            enriched[DERIVED_CHANNEL_COLUMN],
            enriched[area_column],
        )
    ]

    return enriched


# =========================================================
# CLIENT CHANNEL DICTIONARY
# =========================================================


def build_channel_dictionary(
    data: dict,
) -> dict[str, dict]:
    """
    Build Auberry's active channel hierarchy.

    Channels are defined from Order Type.
    Aggregators are defined from Area, under Delivery only.

    The structure is used by the language/vocabulary layer;
    business execution itself uses enrich_channel_dimensions().
    """
    if not isinstance(data, dict):
        raise ValueError(
            "Client data must be an object."
        )

    if "sales" not in data:
        raise ValueError(
            "Sales data was not found."
        )

    sales = data["sales"].copy()

    sales.columns = (
        sales.columns
        .astype(str)
        .str.strip()
    )

    enriched = enrich_channel_dimensions(
        sales
    )

    # Preserve actual source examples for transparency/debugging.
    order_type_column = _resolve_column_name(
        sales,
        ORDER_TYPE_CANDIDATES,
    )

    area_column = _resolve_column_name(
        sales,
        AREA_CANDIDATES,
    )

    raw_order_types_by_channel: dict[str, list[str]] = {}

    for channel_name in (
        CHANNEL_DINE_IN,
        CHANNEL_DELIVERY,
        CHANNEL_TAKE_AWAY,
        CHANNEL_OTHERS,
    ):
        mask = (
            enriched[DERIVED_CHANNEL_COLUMN]
            == channel_name
        )

        raw_values = sorted(
            {
                _clean_text(value)
                for value in sales.loc[
                    mask,
                    order_type_column,
                ]
                if _clean_text(value)
            },
            key=str.lower,
        )

        raw_order_types_by_channel[
            channel_name
        ] = raw_values

    delivery_mask = (
        enriched[DERIVED_CHANNEL_COLUMN]
        == CHANNEL_DELIVERY
    )

    aggregator_raw_values: dict[str, list[str]] = {}

    for aggregator_name in (
        AGGREGATOR_SWIGGY,
        AGGREGATOR_ZOMATO,
        AGGREGATOR_OTHERS,
    ):
        aggregator_mask = (
            delivery_mask
            & (
                enriched[
                    DERIVED_AGGREGATOR_COLUMN
                ]
                == aggregator_name
            )
        )

        raw_values = sorted(
            {
                _clean_text(value)
                for value in sales.loc[
                    aggregator_mask,
                    area_column,
                ]
                if _clean_text(value)
            },
            key=str.lower,
        )

        aggregator_raw_values[
            aggregator_name
        ] = raw_values

    return {
        CHANNEL_DINE_IN: {
            "aliases": [
                "Dine In",
                "Dine-In",
                "Dining",
                "Walk In",
                "Walk-In",
            ],
            "source_column": order_type_column,
            "raw_values": raw_order_types_by_channel[
                CHANNEL_DINE_IN
            ],
            "aggregators": {},
        },
        CHANNEL_DELIVERY: {
            "aliases": [
                "Delivery",
                "Online Delivery",
                "Home Delivery",
                "Online",
            ],
            "source_column": order_type_column,
            "raw_values": raw_order_types_by_channel[
                CHANNEL_DELIVERY
            ],
            "aggregators": {
                AGGREGATOR_SWIGGY: {
                    "aliases": [
                        "Swiggy",
                    ],
                    "source_column": area_column,
                    "raw_values": aggregator_raw_values[
                        AGGREGATOR_SWIGGY
                    ],
                },
                AGGREGATOR_ZOMATO: {
                    "aliases": [
                        "Zomato",
                    ],
                    "source_column": area_column,
                    "raw_values": aggregator_raw_values[
                        AGGREGATOR_ZOMATO
                    ],
                },
                AGGREGATOR_OTHERS: {
                    "aliases": [
                        "Others",
                        "Other Delivery",
                        "Unmapped Delivery",
                    ],
                    "source_column": area_column,
                    "raw_values": aggregator_raw_values[
                        AGGREGATOR_OTHERS
                    ],
                },
            },
        },
        CHANNEL_TAKE_AWAY: {
            "aliases": [
                "Take Away",
                "Takeaway",
                "Take-Away",
                "Pick Up",
                "Pickup",
                "Pick-Up",
            ],
            "source_column": order_type_column,
            "raw_values": raw_order_types_by_channel[
                CHANNEL_TAKE_AWAY
            ],
            "aggregators": {},
        },
        CHANNEL_OTHERS: {
            "aliases": [
                "Others",
                "Other",
            ],
            "source_column": order_type_column,
            "raw_values": raw_order_types_by_channel[
                CHANNEL_OTHERS
            ],
            "aggregators": {},
        },
    }


# =========================================================
# VOCABULARY PROMPT
# =========================================================


def build_channel_vocabulary_prompt(
    channel_dictionary: dict[str, dict],
) -> str:
    """
    Build the client channel/aggregator vocabulary shown to
    the language-understanding layer.

    No business numbers are exposed here.
    """
    lines = [
        "ACTIVE CLIENT CHANNELS AND AGGREGATORS",
        "",
    ]

    for (
        channel_name,
        channel_definition,
    ) in channel_dictionary.items():
        aliases = channel_definition.get(
            "aliases",
            [],
        )

        lines.append(
            f"Channel: {channel_name}"
        )

        if aliases:
            lines.append(
                "Aliases: "
                + ", ".join(aliases)
            )

        aggregators = channel_definition.get(
            "aggregators",
            {},
        )

        if aggregators:
            lines.append(
                "Aggregators: "
                + ", ".join(
                    aggregators.keys()
                )
            )

        lines.append("")

    lines.extend(
        [
            "Auberry execution rule:",
            "- Parent Channel is derived from Order Type.",
            "- Delivery aggregator is derived from Area.",
            "- A Delivery row with no recognized Swiggy/Zomato "
            "Area is classified as aggregator Others.",
        ]
    )

    return "\n".join(lines)
