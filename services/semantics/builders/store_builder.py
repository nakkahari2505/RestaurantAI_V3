from typing import Any

import pandas as pd


DEFAULT_STORE_SHEET_KEY = "store_info"
DEFAULT_SOURCE_STORE_COLUMN = "Restaurant"
DEFAULT_CANONICAL_STORE_COLUMN = "Store"


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
    Normalize store text for comparison.

    Examples:

        "AMB Mall"  -> "amb mall"
        " AMB   Mall " -> "amb mall"

    This normalized value is for matching only.
    The user-facing canonical name remains unchanged.
    """
    return " ".join(
        str(value).strip().lower().split()
    )


def build_store_dictionary(
    data: dict,
    sheet_key: str = DEFAULT_STORE_SHEET_KEY,
    source_column: str = DEFAULT_SOURCE_STORE_COLUMN,
    canonical_column: str = (
        DEFAULT_CANONICAL_STORE_COLUMN
    ),
) -> dict[str, dict]:
    """
    Build a client-specific store dictionary from the
    supplied client data.

    This function is generic.

    It does not contain:
    - Auberry store names,
    - client-specific Python logic,
    - GPT calls,
    - analytics calculations.

    For Auberry, the current defaults mean:

        data["store_info"]
        source column = "Restaurant"
        canonical column = "Store"

    A future client can use the same function with different
    sheet and column parameters.
    """
    if sheet_key not in data:
        raise ValueError(
            f"Store master sheet was not found: "
            f"{sheet_key}"
        )

    store_info = data[
        sheet_key
    ].copy()

    store_info.columns = (
        store_info.columns
        .astype(str)
        .str.strip()
    )

    required_columns = {
        source_column,
        canonical_column,
    }

    missing_columns = (
        required_columns
        - set(store_info.columns)
    )

    if missing_columns:
        raise ValueError(
            "Store master is missing columns: "
            + ", ".join(
                sorted(missing_columns)
            )
        )

    store_dictionary: dict[
        str,
        dict,
    ] = {}

    for _, row in store_info.iterrows():
        source_name = _clean_text(
            row[source_column]
        )

        canonical_name = _clean_text(
            row[canonical_column]
        )

        if not canonical_name:
            continue

        if canonical_name not in store_dictionary:
            store_dictionary[
                canonical_name
            ] = {
                "canonical_name": (
                    canonical_name
                ),
                "aliases": [],
            }

        possible_aliases = {
            canonical_name,
        }

        if source_name:
            possible_aliases.add(
                source_name
            )

        for alias in possible_aliases:
            cleaned_alias = _clean_text(
                alias
            )

            if not cleaned_alias:
                continue

            existing_aliases = (
                store_dictionary[
                    canonical_name
                ]["aliases"]
            )

            normalized_existing_aliases = {
                _normalize_alias(
                    existing_alias
                )
                for existing_alias
                in existing_aliases
            }

            if (
                _normalize_alias(
                    cleaned_alias
                )
                not in normalized_existing_aliases
            ):
                existing_aliases.append(
                    cleaned_alias
                )

    return store_dictionary


def get_canonical_store_names(
    store_dictionary: dict[
        str,
        dict,
    ],
) -> list[str]:
    """
    Return the canonical store names in sorted order.
    """
    return sorted(
        store_dictionary.keys(),
        key=str.lower,
    )


def get_store_alias_map(
    store_dictionary: dict[
        str,
        dict,
    ],
) -> dict[str, str]:
    """
    Return a normalized alias-to-canonical-store map.

    Example:

        {
            "amb mall": "AMB Mall",
            "auberry amb restaurant": "AMB Mall",
        }

    Python can later use this for deterministic validation.
    """
    alias_map: dict[
        str,
        str,
    ] = {}

    for (
        canonical_name,
        store_definition,
    ) in store_dictionary.items():
        aliases = store_definition.get(
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
                ] = canonical_name

    return alias_map


def resolve_store_name(
    requested_store: str,
    store_dictionary: dict[
        str,
        dict,
    ],
) -> str | None:
    """
    Resolve a requested store name deterministically.

    Returns the canonical store name when an exact normalized
    alias exists.

    Returns None when there is no exact alias match.

    This function deliberately does not perform fuzzy guessing.
    Ambiguous spelling resolution can be added later with
    controlled guardrails.
    """
    normalized_request = (
        _normalize_alias(
            requested_store
        )
    )

    if not normalized_request:
        return None

    alias_map = get_store_alias_map(
        store_dictionary
    )

    return alias_map.get(
        normalized_request
    )


def build_store_vocabulary_prompt(
    store_dictionary: dict[
        str,
        dict,
    ],
) -> str:
    """
    Build compact client-specific store context for GPT.

    This prompt contains only valid store names and aliases.

    It does not contain:
    - sales data,
    - KPIs,
    - formulas,
    - Excel rows,
    - business calculations.
    """
    prompt_lines = [
        "Valid stores for the active client:",
    ]

    canonical_names = (
        get_canonical_store_names(
            store_dictionary
        )
    )

    if not canonical_names:
        prompt_lines.append(
            "- No valid stores were found."
        )

        return "\n".join(
            prompt_lines
        )

    for canonical_name in canonical_names:
        store_definition = (
            store_dictionary[
                canonical_name
            ]
        )

        aliases = store_definition.get(
            "aliases",
            [],
        )

        prompt_lines.append(
            (
                "- Canonical store: "
                f"{canonical_name}"
            )
        )

        if aliases:
            prompt_lines.append(
                (
                    "  Known names: "
                    + ", ".join(
                        aliases
                    )
                )
            )

    prompt_lines.extend(
        [
            "",
            (
                "Always return only the canonical "
                "store name in RAL."
            ),
            (
                "Do not invent a store that is not "
                "listed above."
            ),
            (
                "If the requested store cannot be "
                "identified confidently, preserve the "
                "user's wording and mark the request "
                "for clarification."
            ),
        ]
    )

    return "\n".join(
        prompt_lines
    )