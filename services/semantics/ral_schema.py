from typing import Any, Final

from services.semantics.vocabulary.metrics import (
    METRIC_SALES,
    SUPPORTED_METRICS,
)
from services.semantics.vocabulary.time import (
    SUPPORTED_TIME_TYPES,
    TIME_UNSPECIFIED,
)


# =========================================================
# RAL VERSION
# =========================================================

RAL_VERSION: Final[str] = "2.0"


# =========================================================
# SUPPORTED INTENTS
# =========================================================

SUPPORTED_INTENTS: Final[set[str]] = {
    "sales",
    "compare",
    "unsupported",
}


# =========================================================
# GROUPING
# =========================================================

GROUP_BY_STORE: Final[str] = "store"
GROUP_BY_CHANNEL: Final[str] = "channel"
GROUP_BY_AGGREGATOR: Final[str] = "aggregator"
GROUP_BY_CATEGORY: Final[str] = "category"
GROUP_BY_ITEM: Final[str] = "item"


SUPPORTED_GROUPING_DIMENSIONS: Final[set[str]] = {
    GROUP_BY_STORE,
    GROUP_BY_CHANNEL,
    GROUP_BY_AGGREGATOR,
    GROUP_BY_CATEGORY,
    GROUP_BY_ITEM,
}


# =========================================================
# TREND
# =========================================================

TREND_GRAIN_DAY: Final[str] = "day"
TREND_GRAIN_WEEK: Final[str] = "week"
TREND_GRAIN_MONTH: Final[str] = "month"


SUPPORTED_TREND_GRAINS: Final[set[str]] = {
    TREND_GRAIN_DAY,
    TREND_GRAIN_WEEK,
    TREND_GRAIN_MONTH,
}


# =========================================================
# PRESENTATION
# =========================================================

PRESENTATION_TEXT: Final[str] = "text"
PRESENTATION_TABLE: Final[str] = "table"
PRESENTATION_BAR_CHART: Final[str] = "bar_chart"
PRESENTATION_LINE_CHART: Final[str] = "line_chart"


SUPPORTED_PRESENTATION_TYPES: Final[set[str]] = {
    PRESENTATION_TEXT,
    PRESENTATION_TABLE,
    PRESENTATION_BAR_CHART,
    PRESENTATION_LINE_CHART,
}


# =========================================================
# RAL JSON SCHEMA
# =========================================================

RAL_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "ral_version": {
            "type": "string",
            "enum": [
                RAL_VERSION,
            ],
        },

        "intent": {
            "type": "string",
            "enum": sorted(
                SUPPORTED_INTENTS
            ),
        },

        "metric": {
            "type": "string",
            "enum": sorted(
                SUPPORTED_METRICS
            ),
        },

        # =================================================
        # TIME
        # =================================================

        "time": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": sorted(
                        SUPPORTED_TIME_TYPES
                    ),
                },

                "start_date": {
                    "type": [
                        "string",
                        "null",
                    ],
                },

                "end_date": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
            },

            "required": [
                "type",
                "start_date",
                "end_date",
            ],

            "additionalProperties": False,
        },

        # =================================================
        # BUSINESS FILTER DIMENSIONS
        # =================================================

        "stores": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },

        "regions": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },

        "channels": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },

        "aggregators": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },

        "categories": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },

        "items": {
            "type": "array",
            "items": {
                "type": "string",
            },
        },

        # =================================================
        # GROUPING
        # =================================================

        "grouping": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                },

                "dimensions": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": sorted(
                            SUPPORTED_GROUPING_DIMENSIONS
                        ),
                    },
                },
            },

            "required": [
                "enabled",
                "dimensions",
            ],

            "additionalProperties": False,
        },

        # =================================================
        # TREND
        # =================================================

        "trend": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                },

                "grain": {
                    "type": [
                        "string",
                        "null",
                    ],

                    "enum": (
                        sorted(
                            SUPPORTED_TREND_GRAINS
                        )
                        + [
                            None,
                        ]
                    ),
                },
            },

            "required": [
                "enabled",
                "grain",
            ],

            "additionalProperties": False,
        },

        # =================================================
        # COMPARISON
        # =================================================

        "comparison": {
            "type": "object",
            "properties": {
                "enabled": {
                    "type": "boolean",
                },

                "from_start_date": {
                    "type": [
                        "string",
                        "null",
                    ],
                },

                "from_end_date": {
                    "type": [
                        "string",
                        "null",
                    ],
                },

                "to_start_date": {
                    "type": [
                        "string",
                        "null",
                    ],
                },

                "to_end_date": {
                    "type": [
                        "string",
                        "null",
                    ],
                },
            },

            "required": [
                "enabled",
                "from_start_date",
                "from_end_date",
                "to_start_date",
                "to_end_date",
            ],

            "additionalProperties": False,
        },

        # =================================================
        # PRESENTATION
        # =================================================

        "presentation": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": sorted(
                        SUPPORTED_PRESENTATION_TYPES
                    ),
                },
            },

            "required": [
                "type",
            ],

            "additionalProperties": False,
        },

        # =================================================
        # INTERPRETATION / CLARIFICATION
        # =================================================

        "understood_request": {
            "type": "string",
        },

        "needs_clarification": {
            "type": "boolean",
        },

        "clarification_question": {
            "type": [
                "string",
                "null",
            ],
        },
    },

    "required": [
        "ral_version",
        "intent",
        "metric",
        "time",
        "stores",
        "regions",
        "channels",
        "aggregators",
        "categories",
        "items",
        "grouping",
        "trend",
        "comparison",
        "presentation",
        "understood_request",
        "needs_clarification",
        "clarification_question",
    ],

    "additionalProperties": False,
}


# =========================================================
# EMPTY RAL REQUEST
# =========================================================


def create_empty_ral_request() -> dict[str, Any]:
    """
    Return a safe empty RAL request.

    Default behaviour represents:

        - Sales metric
        - No usable time
        - No filters
        - No grouping
        - No trend
        - No comparison
        - Text presentation
        - Unsupported request
    """
    return {
        "ral_version": RAL_VERSION,

        "intent": "unsupported",

        "metric": METRIC_SALES,

        "time": {
            "type": TIME_UNSPECIFIED,
            "start_date": None,
            "end_date": None,
        },

        "stores": [],

        "regions": [],

        "channels": [],

        "aggregators": [],

        "categories": [],

        "items": [],

        "grouping": {
            "enabled": False,
            "dimensions": [],
        },

        "trend": {
            "enabled": False,
            "grain": None,
        },

        "comparison": {
            "enabled": False,
            "from_start_date": None,
            "from_end_date": None,
            "to_start_date": None,
            "to_end_date": None,
        },

        "presentation": {
            "type": PRESENTATION_TEXT,
        },

        "understood_request": (
            "The request could not be interpreted."
        ),

        "needs_clarification": False,

        "clarification_question": None,
    }


# =========================================================
# PUBLIC VALIDATOR
# =========================================================


def validate_ral_request(
    ral_request: dict[str, Any],
) -> None:
    """
    Perform deterministic validation of a RAL request.

    GPT proposes RAL.

    Python verifies:

        - exact top-level structure,
        - allowed metric,
        - allowed time,
        - business filters,
        - grouping structure,
        - trend structure,
        - comparison structure,
        - presentation structure,
        - clarification consistency.
    """
    if not isinstance(
        ral_request,
        dict,
    ):
        raise ValueError(
            "RAL request must be an object."
        )

    required_fields = {
        "ral_version",
        "intent",
        "metric",
        "time",
        "stores",
        "regions",
        "channels",
        "aggregators",
        "categories",
        "items",
        "grouping",
        "trend",
        "comparison",
        "presentation",
        "understood_request",
        "needs_clarification",
        "clarification_question",
    }

    received_fields = set(
        ral_request.keys()
    )

    missing_fields = (
        required_fields
        - received_fields
    )

    if missing_fields:
        raise ValueError(
            "RAL request is missing fields: "
            + ", ".join(
                sorted(
                    missing_fields
                )
            )
        )

    unexpected_fields = (
        received_fields
        - required_fields
    )

    if unexpected_fields:
        raise ValueError(
            "RAL request contains unexpected fields: "
            + ", ".join(
                sorted(
                    unexpected_fields
                )
            )
        )

    # =====================================================
    # VERSION
    # =====================================================

    if (
        ral_request[
            "ral_version"
        ]
        != RAL_VERSION
    ):
        raise ValueError(
            "Unsupported RAL version."
        )

    # =====================================================
    # INTENT
    # =====================================================

    if (
        ral_request[
            "intent"
        ]
        not in SUPPORTED_INTENTS
    ):
        raise ValueError(
            "Unsupported RAL intent."
        )

    # =====================================================
    # METRIC
    # =====================================================

    if (
        ral_request[
            "metric"
        ]
        not in SUPPORTED_METRICS
    ):
        raise ValueError(
            "Unsupported RAL metric."
        )

    # =====================================================
    # TIME
    # =====================================================

    _validate_time(
        ral_request[
            "time"
        ]
    )

    # =====================================================
    # BUSINESS FILTERS
    # =====================================================

    _validate_string_list(
        ral_request[
            "stores"
        ],
        "stores",
    )

    _validate_string_list(
        ral_request[
            "regions"
        ],
        "regions",
    )

    _validate_string_list(
        ral_request[
            "channels"
        ],
        "channels",
    )

    _validate_string_list(
        ral_request[
            "aggregators"
        ],
        "aggregators",
    )

    _validate_string_list(
        ral_request[
            "categories"
        ],
        "categories",
    )

    _validate_string_list(
        ral_request[
            "items"
        ],
        "items",
    )

    # =====================================================
    # GROUPING
    # =====================================================

    _validate_grouping(
        ral_request[
            "grouping"
        ]
    )

    # =====================================================
    # TREND
    # =====================================================

    _validate_trend(
        ral_request[
            "trend"
        ]
    )

    # =====================================================
    # COMPARISON
    # =====================================================

    _validate_comparison(
        ral_request[
            "comparison"
        ]
    )

    # =====================================================
    # PRESENTATION
    # =====================================================

    _validate_presentation(
        ral_request[
            "presentation"
        ]
    )

    # =====================================================
    # UNDERSTOOD REQUEST
    # =====================================================

    understood_request = (
        ral_request[
            "understood_request"
        ]
    )

    if not isinstance(
        understood_request,
        str,
    ):
        raise ValueError(
            "RAL understood_request must be text."
        )

    if not understood_request.strip():
        raise ValueError(
            "RAL understood_request cannot be empty."
        )

    # =====================================================
    # CLARIFICATION
    # =====================================================

    needs_clarification = (
        ral_request[
            "needs_clarification"
        ]
    )

    if not isinstance(
        needs_clarification,
        bool,
    ):
        raise ValueError(
            "RAL needs_clarification must "
            "be true or false."
        )

    clarification_question = (
        ral_request[
            "clarification_question"
        ]
    )

    if (
        clarification_question
        is not None
        and not isinstance(
            clarification_question,
            str,
        )
    ):
        raise ValueError(
            "RAL clarification_question must "
            "be text or null."
        )

    if (
        needs_clarification
        and (
            clarification_question is None
            or not clarification_question.strip()
        )
    ):
        raise ValueError(
            "A clarification question is required "
            "when needs_clarification is true."
        )

    if (
        not needs_clarification
        and clarification_question
        is not None
    ):
        raise ValueError(
            "clarification_question must be null "
            "when needs_clarification is false."
        )


# =========================================================
# TIME VALIDATOR
# =========================================================


def _validate_time(
    time_value: Any,
) -> None:
    """
    Validate the RAL time object.
    """
    if not isinstance(
        time_value,
        dict,
    ):
        raise ValueError(
            "RAL time must be an object."
        )

    required_time_fields = {
        "type",
        "start_date",
        "end_date",
    }

    received_time_fields = set(
        time_value.keys()
    )

    if (
        received_time_fields
        != required_time_fields
    ):
        raise ValueError(
            "RAL time must contain exactly: "
            "type, start_date and end_date."
        )

    if (
        time_value[
            "type"
        ]
        not in SUPPORTED_TIME_TYPES
    ):
        raise ValueError(
            "Unsupported RAL time type."
        )

    for date_field in {
        "start_date",
        "end_date",
    }:
        date_value = (
            time_value[
                date_field
            ]
        )

        if (
            date_value is not None
            and not isinstance(
                date_value,
                str,
            )
        ):
            raise ValueError(
                f"RAL time {date_field} must "
                "be text or null."
            )


# =========================================================
# STRING-LIST VALIDATOR
# =========================================================


def _validate_string_list(
    field_value: Any,
    field_name: str,
) -> None:
    """
    Validate a RAL dimension list.
    """
    if not isinstance(
        field_value,
        list,
    ):
        raise ValueError(
            f"RAL {field_name} must be a list."
        )

    for item_value in field_value:
        if not isinstance(
            item_value,
            str,
        ):
            raise ValueError(
                f"Every RAL {field_name} value "
                "must be text."
            )

        if not item_value.strip():
            raise ValueError(
                f"RAL {field_name} cannot contain "
                "an empty value."
            )


# =========================================================
# GROUPING VALIDATOR
# =========================================================


def _validate_grouping(
    grouping_value: Any,
) -> None:
    """
    Validate grouping instructions.

    Examples:

        Store-wise:
            enabled = True
            dimensions = ["store"]

        Store-wise + channel-wise:
            enabled = True
            dimensions = [
                "store",
                "channel",
            ]

        No grouping:
            enabled = False
            dimensions = []
    """
    if not isinstance(
        grouping_value,
        dict,
    ):
        raise ValueError(
            "RAL grouping must be an object."
        )

    required_grouping_fields = {
        "enabled",
        "dimensions",
    }

    received_grouping_fields = set(
        grouping_value.keys()
    )

    if (
        received_grouping_fields
        != required_grouping_fields
    ):
        raise ValueError(
            "RAL grouping must contain exactly: "
            "enabled and dimensions."
        )

    enabled = grouping_value[
        "enabled"
    ]

    if not isinstance(
        enabled,
        bool,
    ):
        raise ValueError(
            "RAL grouping enabled must "
            "be true or false."
        )

    dimensions = grouping_value[
        "dimensions"
    ]

    if not isinstance(
        dimensions,
        list,
    ):
        raise ValueError(
            "RAL grouping dimensions "
            "must be a list."
        )

    seen_dimensions: set[str] = set()

    for dimension in dimensions:
        if not isinstance(
            dimension,
            str,
        ):
            raise ValueError(
                "Every RAL grouping dimension "
                "must be text."
            )

        if (
            dimension
            not in SUPPORTED_GROUPING_DIMENSIONS
        ):
            raise ValueError(
                "Unsupported RAL grouping dimension: "
                f"{dimension}"
            )

        if dimension in seen_dimensions:
            raise ValueError(
                "RAL grouping dimensions "
                "cannot contain duplicates."
            )

        seen_dimensions.add(
            dimension
        )

    if (
        enabled
        and not dimensions
    ):
        raise ValueError(
            "RAL grouping dimensions cannot "
            "be empty when grouping is enabled."
        )

    if (
        not enabled
        and dimensions
    ):
        raise ValueError(
            "RAL grouping dimensions must be empty "
            "when grouping is disabled."
        )


# =========================================================
# TREND VALIDATOR
# =========================================================


def _validate_trend(
    trend_value: Any,
) -> None:
    """
    Validate trend instructions.

    Examples:

        Daily trend:
            enabled = True
            grain = "day"

        Weekly trend:
            enabled = True
            grain = "week"

        No trend:
            enabled = False
            grain = None
    """
    if not isinstance(
        trend_value,
        dict,
    ):
        raise ValueError(
            "RAL trend must be an object."
        )

    required_trend_fields = {
        "enabled",
        "grain",
    }

    received_trend_fields = set(
        trend_value.keys()
    )

    if (
        received_trend_fields
        != required_trend_fields
    ):
        raise ValueError(
            "RAL trend must contain exactly: "
            "enabled and grain."
        )

    enabled = trend_value[
        "enabled"
    ]

    grain = trend_value[
        "grain"
    ]

    if not isinstance(
        enabled,
        bool,
    ):
        raise ValueError(
            "RAL trend enabled must "
            "be true or false."
        )

    if (
        grain is not None
        and not isinstance(
            grain,
            str,
        )
    ):
        raise ValueError(
            "RAL trend grain must "
            "be text or null."
        )

    if (
        grain is not None
        and grain
        not in SUPPORTED_TREND_GRAINS
    ):
        raise ValueError(
            "Unsupported RAL trend grain."
        )

    if (
        enabled
        and grain is None
    ):
        raise ValueError(
            "RAL trend grain is required "
            "when trend is enabled."
        )

    if (
        not enabled
        and grain is not None
    ):
        raise ValueError(
            "RAL trend grain must be null "
            "when trend is disabled."
        )


# =========================================================
# COMPARISON VALIDATOR
# =========================================================


def _validate_comparison(
    comparison_value: Any,
) -> None:
    """
    Validate the RAL comparison object.
    """
    if not isinstance(
        comparison_value,
        dict,
    ):
        raise ValueError(
            "RAL comparison must be an object."
        )

    required_comparison_fields = {
        "enabled",
        "from_start_date",
        "from_end_date",
        "to_start_date",
        "to_end_date",
    }

    received_comparison_fields = set(
        comparison_value.keys()
    )

    if (
        received_comparison_fields
        != required_comparison_fields
    ):
        raise ValueError(
            "RAL comparison must contain exactly: "
            "enabled, from_start_date, from_end_date, "
            "to_start_date and to_end_date."
        )

    if not isinstance(
        comparison_value[
            "enabled"
        ],
        bool,
    ):
        raise ValueError(
            "RAL comparison enabled must "
            "be true or false."
        )

    comparison_date_fields = {
        "from_start_date",
        "from_end_date",
        "to_start_date",
        "to_end_date",
    }

    for date_field in (
        comparison_date_fields
    ):
        date_value = (
            comparison_value[
                date_field
            ]
        )

        if (
            date_value is not None
            and not isinstance(
                date_value,
                str,
            )
        ):
            raise ValueError(
                f"RAL comparison {date_field} "
                "must be text or null."
            )


# =========================================================
# PRESENTATION VALIDATOR
# =========================================================


def _validate_presentation(
    presentation_value: Any,
) -> None:
    """
    Validate how the user requested the result to be shown.

    Presentation does not calculate business numbers.

    It only describes the preferred output format.
    """
    if not isinstance(
        presentation_value,
        dict,
    ):
        raise ValueError(
            "RAL presentation must be an object."
        )

    required_presentation_fields = {
        "type",
    }

    received_presentation_fields = set(
        presentation_value.keys()
    )

    if (
        received_presentation_fields
        != required_presentation_fields
    ):
        raise ValueError(
            "RAL presentation must contain exactly: type."
        )

    presentation_type = (
        presentation_value[
            "type"
        ]
    )

    if (
        presentation_type
        not in SUPPORTED_PRESENTATION_TYPES
    ):
        raise ValueError(
            "Unsupported RAL presentation type."
        )