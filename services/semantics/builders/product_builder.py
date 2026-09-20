from typing import Any, Final

import pandas as pd


# =========================================================
# DEFAULT CLIENT DATA LOCATION
# =========================================================

DEFAULT_CATEGORY_SHEET_KEY: Final[str] = (
    "item_category"
)

DEFAULT_SALES_SHEET_KEY: Final[str] = "sales"

DEFAULT_ITEM_COLUMN: Final[str] = "Item Name"

DEFAULT_CATEGORY_COLUMN: Final[str] = "Category"


# =========================================================
# STANDARD VALUES
# =========================================================

UNMAPPED_CATEGORY: Final[str] = "Unmapped"


# =========================================================
# TEXT HELPERS
# =========================================================


def _clean_text(
    value: Any,
) -> str:
    """
    Convert a value into clean display text.
    """
    if pd.isna(value):
        return ""

    return " ".join(
        str(value).strip().split()
    )


def _normalize_alias(
    value: str,
) -> str:
    """
    Normalize text for deterministic matching.

    Examples:

        "Classic  Glazed"
            -> "classic glazed"

        " DONUTS "
            -> "donuts"
    """
    return " ".join(
        str(value).strip().lower().split()
    )


def _add_unique_text(
    values: list[str],
    new_value: str,
) -> None:
    """
    Add clean text only when its normalized form
    does not already exist.
    """
    cleaned_value = _clean_text(
        new_value
    )

    if not cleaned_value:
        return

    normalized_value = _normalize_alias(
        cleaned_value
    )

    normalized_existing_values = {
        _normalize_alias(
            existing_value
        )
        for existing_value in values
    }

    if (
        normalized_value
        not in normalized_existing_values
    ):
        values.append(
            cleaned_value
        )


# =========================================================
# PRODUCT STRUCTURE HELPERS
# =========================================================


def _create_category_definition(
    category_name: str,
) -> dict:
    """
    Create one canonical category definition.
    """
    category_definition = {
        "canonical_name": category_name,
        "aliases": [],
        "items": {},
    }

    _add_unique_text(
        category_definition["aliases"],
        category_name,
    )

    return category_definition


def _create_item_definition(
    item_name: str,
    category_name: str,
) -> dict:
    """
    Create one canonical item definition.
    """
    item_definition = {
        "canonical_name": item_name,
        "category_name": category_name,
        "aliases": [],
        "raw_names": [],
    }

    _add_unique_text(
        item_definition["aliases"],
        item_name,
    )

    _add_unique_text(
        item_definition["raw_names"],
        item_name,
    )

    return item_definition


def _ensure_category(
    product_dictionary: dict[str, dict],
    category_name: str,
) -> dict:
    """
    Ensure that a category exists and return it.
    """
    if category_name not in product_dictionary:
        product_dictionary[
            category_name
        ] = _create_category_definition(
            category_name
        )

    return product_dictionary[
        category_name
    ]


def _add_item_to_category(
    product_dictionary: dict[str, dict],
    category_name: str,
    item_name: str,
    raw_item_name: str | None = None,
) -> None:
    """
    Add an item under its canonical category.
    """
    category_definition = _ensure_category(
        product_dictionary=(
            product_dictionary
        ),
        category_name=category_name,
    )

    items = category_definition[
        "items"
    ]

    if item_name not in items:
        items[
            item_name
        ] = _create_item_definition(
            item_name=item_name,
            category_name=category_name,
        )

    item_definition = items[
        item_name
    ]

    _add_unique_text(
        item_definition["aliases"],
        item_name,
    )

    _add_unique_text(
        item_definition["raw_names"],
        item_name,
    )

    if raw_item_name:
        _add_unique_text(
            item_definition["aliases"],
            raw_item_name,
        )

        _add_unique_text(
            item_definition["raw_names"],
            raw_item_name,
        )


# =========================================================
# MAIN PRODUCT BUILDER
# =========================================================


def build_product_dictionary(
    data: dict,
    category_sheet_key: str = (
        DEFAULT_CATEGORY_SHEET_KEY
    ),
    sales_sheet_key: str = (
        DEFAULT_SALES_SHEET_KEY
    ),
    item_column: str = DEFAULT_ITEM_COLUMN,
    category_column: str = (
        DEFAULT_CATEGORY_COLUMN
    ),
) -> dict[str, dict]:
    """
    Build the client-specific Category–Item hierarchy.

    Primary source:

        data[category_sheet_key]

    This source is expected to contain:

        Item Name
        Category

    Secondary source:

        data[sales_sheet_key]

    The sales data is used to identify items that exist in
    transactions but are absent from the category master.

    Such items are placed under:

        Unmapped

    The builder never guesses a missing category.

    This function contains no:

    - Auberry category names,
    - Auberry item names,
    - GPT calls,
    - sales calculations,
    - WhatsApp routing.
    """
    if category_sheet_key not in data:
        raise ValueError(
            "Category master sheet was not found: "
            f"{category_sheet_key}"
        )

    if sales_sheet_key not in data:
        raise ValueError(
            "Sales sheet was not found: "
            f"{sales_sheet_key}"
        )

    category_data = data[
        category_sheet_key
    ].copy()

    sales_data = data[
        sales_sheet_key
    ].copy()

    category_data.columns = (
        category_data.columns
        .astype(str)
        .str.strip()
    )

    sales_data.columns = (
        sales_data.columns
        .astype(str)
        .str.strip()
    )

    required_category_columns = {
        item_column,
        category_column,
    }

    missing_category_columns = (
        required_category_columns
        - set(category_data.columns)
    )

    if missing_category_columns:
        raise ValueError(
            "Category master is missing columns: "
            + ", ".join(
                sorted(
                    missing_category_columns
                )
            )
        )

    if item_column not in sales_data.columns:
        raise ValueError(
            "Sales data is missing the item column: "
            f"{item_column}"
        )

    product_dictionary: dict[
        str,
        dict,
    ] = {}

    mapped_item_lookup: dict[
        str,
        tuple[str, str],
    ] = {}

    # -----------------------------------------------------
    # BUILD CATEGORY–ITEM MASTER
    # -----------------------------------------------------

    for _, row in category_data.iterrows():
        raw_item_name = _clean_text(
            row[item_column]
        )

        raw_category_name = _clean_text(
            row[category_column]
        )

        if not raw_item_name:
            continue

        category_name = (
            raw_category_name
            if raw_category_name
            else UNMAPPED_CATEGORY
        )

        item_name = raw_item_name

        normalized_item = _normalize_alias(
            raw_item_name
        )

        existing_mapping = (
            mapped_item_lookup.get(
                normalized_item
            )
        )

        if existing_mapping is not None:
            (
                existing_category,
                existing_item,
            ) = existing_mapping

            # Do not silently move one item between
            # conflicting categories.
            if (
                existing_category
                != category_name
            ):
                continue

            _add_item_to_category(
                product_dictionary=(
                    product_dictionary
                ),
                category_name=(
                    existing_category
                ),
                item_name=existing_item,
                raw_item_name=raw_item_name,
            )

            continue

        mapped_item_lookup[
            normalized_item
        ] = (
            category_name,
            item_name,
        )

        _add_item_to_category(
            product_dictionary=(
                product_dictionary
            ),
            category_name=category_name,
            item_name=item_name,
            raw_item_name=raw_item_name,
        )

    # -----------------------------------------------------
    # IDENTIFY ITEMS PRESENT IN SALES BUT NOT IN MASTER
    # -----------------------------------------------------

    sales_item_values = (
        sales_data[item_column]
        .dropna()
        .map(_clean_text)
    )

    sales_item_values = (
        sales_item_values[
            sales_item_values.ne("")
        ]
        .drop_duplicates()
        .tolist()
    )

    for sales_item_name in sales_item_values:
        normalized_sales_item = (
            _normalize_alias(
                sales_item_name
            )
        )

        if (
            normalized_sales_item
            in mapped_item_lookup
        ):
            (
                mapped_category,
                mapped_item_name,
            ) = mapped_item_lookup[
                normalized_sales_item
            ]

            _add_item_to_category(
                product_dictionary=(
                    product_dictionary
                ),
                category_name=(
                    mapped_category
                ),
                item_name=mapped_item_name,
                raw_item_name=(
                    sales_item_name
                ),
            )

            continue

        _add_item_to_category(
            product_dictionary=(
                product_dictionary
            ),
            category_name=(
                UNMAPPED_CATEGORY
            ),
            item_name=sales_item_name,
            raw_item_name=sales_item_name,
        )

    return product_dictionary


# =========================================================
# CATEGORY LOOKUP HELPERS
# =========================================================


def get_canonical_category_names(
    product_dictionary: dict[
        str,
        dict,
    ],
    include_unmapped: bool = True,
) -> list[str]:
    """
    Return canonical category names in sorted order.
    """
    category_names = list(
        product_dictionary.keys()
    )

    if not include_unmapped:
        category_names = [
            category_name
            for category_name
            in category_names
            if category_name
            != UNMAPPED_CATEGORY
        ]

    return sorted(
        category_names,
        key=str.lower,
    )


def get_category_alias_map(
    product_dictionary: dict[
        str,
        dict,
    ],
) -> dict[str, str]:
    """
    Return a normalized category-alias map.

    Example:

        "donuts" -> "Donuts"
    """
    alias_map: dict[
        str,
        str,
    ] = {}

    for (
        canonical_category,
        category_definition,
    ) in product_dictionary.items():
        aliases = category_definition.get(
            "aliases",
            [],
        )

        for alias in aliases:
            normalized_alias = (
                _normalize_alias(
                    alias
                )
            )

            if normalized_alias:
                alias_map[
                    normalized_alias
                ] = canonical_category

    return alias_map


def resolve_category_name(
    requested_category: str,
    product_dictionary: dict[
        str,
        dict,
    ],
) -> str | None:
    """
    Resolve an exact normalized category alias.

    Fuzzy guessing is deliberately excluded.
    """
    normalized_request = (
        _normalize_alias(
            requested_category
        )
    )

    if not normalized_request:
        return None

    alias_map = get_category_alias_map(
        product_dictionary
    )

    return alias_map.get(
        normalized_request
    )


# =========================================================
# ITEM LOOKUP HELPERS
# =========================================================


def get_canonical_item_names(
    product_dictionary: dict[
        str,
        dict,
    ],
    include_unmapped: bool = True,
) -> list[str]:
    """
    Return all canonical item names in sorted order.
    """
    item_names: list[str] = []

    for (
        category_name,
        category_definition,
    ) in product_dictionary.items():
        if (
            not include_unmapped
            and category_name
            == UNMAPPED_CATEGORY
        ):
            continue

        items = category_definition.get(
            "items",
            {},
        )

        for item_name in items:
            _add_unique_text(
                item_names,
                item_name,
            )

    return sorted(
        item_names,
        key=str.lower,
    )


def get_item_alias_map(
    product_dictionary: dict[
        str,
        dict,
    ],
) -> dict[str, list[dict[str, str]]]:
    """
    Return normalized aliases mapped to possible items.

    A list is used because the same item name may exist
    under more than one category.

    Example:

        {
            "cold coffee": [
                {
                    "category": "Beverages",
                    "item": "Cold Coffee"
                }
            ]
        }
    """
    alias_map: dict[
        str,
        list[dict[str, str]],
    ] = {}

    for (
        category_name,
        category_definition,
    ) in product_dictionary.items():
        items = category_definition.get(
            "items",
            {},
        )

        for (
            item_name,
            item_definition,
        ) in items.items():
            aliases = item_definition.get(
                "aliases",
                [],
            )

            for alias in aliases:
                normalized_alias = (
                    _normalize_alias(
                        alias
                    )
                )

                if not normalized_alias:
                    continue

                if normalized_alias not in alias_map:
                    alias_map[
                        normalized_alias
                    ] = []

                candidate = {
                    "category": (
                        category_name
                    ),
                    "item": item_name,
                }

                if (
                    candidate
                    not in alias_map[
                        normalized_alias
                    ]
                ):
                    alias_map[
                        normalized_alias
                    ].append(
                        candidate
                    )

    return alias_map


def resolve_item_name(
    requested_item: str,
    product_dictionary: dict[
        str,
        dict,
    ],
) -> dict[str, str] | None:
    """
    Resolve an item only when one exact unambiguous
    normalized alias exists.

    Returns:

        {
            "category": "Donuts",
            "item": "Classic Glazed"
        }

    Returns None when:

    - no exact item exists,
    - multiple items share the same alias.
    """
    normalized_request = (
        _normalize_alias(
            requested_item
        )
    )

    if not normalized_request:
        return None

    alias_map = get_item_alias_map(
        product_dictionary
    )

    matches = alias_map.get(
        normalized_request,
        [],
    )

    if len(matches) != 1:
        return None

    return dict(
        matches[0]
    )


# =========================================================
# PRODUCT VOCABULARY PROMPT
# =========================================================


def build_product_vocabulary_prompt(
    product_dictionary: dict[
        str,
        dict,
    ],
    maximum_items_per_category: int = 50,
) -> str:
    """
    Build client-specific Category and Item context for GPT.

    The prompt teaches the hierarchy:

        Category
            └── Items

    It contains no:

    - sales values,
    - quantities,
    - prices,
    - transaction rows,
    - analytics calculations.
    """
    prompt_lines = [
        "Product hierarchy for the active client:",
        "",
    ]

    category_names = (
        get_canonical_category_names(
            product_dictionary=(
                product_dictionary
            ),
            include_unmapped=True,
        )
    )

    if not category_names:
        return (
            "Product hierarchy for the active client:\n"
            "- No valid categories or items were found."
        )

    for category_name in category_names:
        category_definition = (
            product_dictionary[
                category_name
            ]
        )

        prompt_lines.append(
            (
                "- Canonical category: "
                f"{category_name}"
            )
        )

        category_aliases = (
            category_definition.get(
                "aliases",
                [],
            )
        )

        if category_aliases:
            prompt_lines.append(
                (
                    "  Known category names: "
                    + ", ".join(
                        category_aliases
                    )
                )
            )

        items = category_definition.get(
            "items",
            {},
        )

        if not items:
            prompt_lines.append(
                "  Items: none"
            )

            continue

        prompt_lines.append(
            "  Canonical items:"
        )

        sorted_item_names = sorted(
            items.keys(),
            key=str.lower,
        )

        for item_name in (
            sorted_item_names[
                :maximum_items_per_category
            ]
        ):
            item_definition = items[
                item_name
            ]

            item_aliases = (
                item_definition.get(
                    "aliases",
                    [],
                )
            )

            prompt_lines.append(
                (
                    "    - Canonical item: "
                    f"{item_name}"
                )
            )

            if item_aliases:
                prompt_lines.append(
                    (
                        "      Known names: "
                        + ", ".join(
                            item_aliases
                        )
                    )
                )

        remaining_item_count = (
            len(sorted_item_names)
            - maximum_items_per_category
        )

        if remaining_item_count > 0:
            prompt_lines.append(
                (
                    "    - Additional items not shown: "
                    f"{remaining_item_count}"
                )
            )

    prompt_lines.extend(
        [
            "",
            "Product interpretation rules:",
            (
                "- A category request must populate "
                "categories and leave items empty unless "
                "specific items were also requested."
            ),
            (
                "- An item request must populate items."
            ),
            (
                "- When an item's category is known, also "
                "populate its canonical category."
            ),
            (
                "- Never treat a whole category as one item."
            ),
            (
                "- Never treat an individual item as a "
                "category."
            ),
            (
                "- Always return only canonical category "
                "and item names listed above."
            ),
            (
                "- Never guess a category for an unmapped "
                "item."
            ),
            (
                "- If an item or category cannot be resolved "
                "confidently, preserve the user's wording "
                "and request clarification."
            ),
        ]
    )

    return "\n".join(
        prompt_lines
    )