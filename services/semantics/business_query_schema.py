from typing import Final

BUSINESS_QUERY_VERSION: Final[str] = "3.1"

SUPPORTED_CONTEXT_RELATIONS = {
    "new",
    "continue",
    "modify",
    "ambiguous",
}

SUPPORTED_DOMAIN_STATUSES = {
    "business_query",
    "conversational",
    "ambiguous",
    "out_of_domain",
}

SUPPORTED_OPERATIONS = {
    "retrieve",
    "compare",
    "rank",
    "trend",
    "contribution",
    "diagnose",
    "filter",
    "summarize",
}

SUPPORTED_COMPARISONS = {
    "none",
    "previous_period",
    "same_period_last_year",
}

SUPPORTED_PRESENTATIONS = {
    "auto",
    "text",
    "image_table",
    "chart",
    "excel",
}

SUPPORTED_GROUPING_DIMENSIONS = {
    "store",
    "channel",
}

METRICS = ["sales", "transactions", "apt", "ads", "adt"]

PERIOD_SCHEMA = {
    "type": "object",
    "properties": {
        "start_date": {"type": ["string", "null"]},
        "end_date": {"type": ["string", "null"]},
    },
    "required": ["start_date", "end_date"],
    "additionalProperties": False,
}

BUSINESS_QUERY_JSON_SCHEMA = {
    "type": "object",
    "properties": {
        "version": {"type": "string", "enum": [BUSINESS_QUERY_VERSION]},
        "context_relation": {
            "type": "string",
            "enum": sorted(SUPPORTED_CONTEXT_RELATIONS),
        },
        "domain_status": {
            "type": "string",
            "enum": sorted(SUPPORTED_DOMAIN_STATUSES),
        },
        "time": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": [
                        "today",
                        "yesterday",
                        "day_before_yesterday",
                        "this_week",
                        "last_week",
                        "this_month",
                        "last_month",
                        "this_quarter",
                        "last_quarter",
                        "ytd",
                        "specific_date",
                        "date_range",
                        "unspecified",
                    ],
                },
                "start_date": {"type": ["string", "null"]},
                "end_date": {"type": ["string", "null"]},
            },
            "required": ["type", "start_date", "end_date"],
            "additionalProperties": False,
        },
        "stores": {
            "type": "array",
            "items": {"type": "string"},
        },
        "channels": {
            "type": "array",
            "items": {"type": "string"},
        },
        "metrics": {
            "type": "array",
            "items": {"type": "string", "enum": METRICS},
        },
        "operation": {
            "type": "string",
            "enum": sorted(SUPPORTED_OPERATIONS),
        },
        "comparison": {
            "type": "string",
            "enum": sorted(SUPPORTED_COMPARISONS),
        },
        "comparison_detail": {
            "type": "object",
            "properties": {
                "mode": {
                    "type": "string",
                    "enum": [
                        "none",
                        "previous_period",
                        "same_period_last_year",
                        "custom_period",
                        "pre_post",
                    ],
                },
                "reference_period": PERIOD_SCHEMA,
            },
            "required": ["mode", "reference_period"],
            "additionalProperties": False,
        },
        "group_by": {
            "type": "array",
            "items": {
                "type": "string",
                "enum": sorted(SUPPORTED_GROUPING_DIMENSIONS),
            },
        },
        "selection": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "direction": {
                    "type": "string",
                    "enum": ["none", "top", "bottom"],
                },
                "limit": {"type": ["integer", "null"], "minimum": 1},
                "sort_metric": {"type": ["string", "null"], "enum": METRICS + [None]},
                "sort_measure": {
                    "type": "string",
                    "enum": ["value", "change", "growth_pct", "contribution_pct"],
                },
            },
            "required": [
                "enabled",
                "direction",
                "limit",
                "sort_metric",
                "sort_measure",
            ],
            "additionalProperties": False,
        },
        "conditions": {
            "type": "object",
            "properties": {
                "logic": {"type": "string", "enum": ["none", "and", "or"]},
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "metric": {"type": "string", "enum": METRICS},
                            "measure": {
                                "type": "string",
                                "enum": ["value", "change", "growth_pct", "contribution_pct"],
                            },
                            "operator": {
                                "type": "string",
                                "enum": ["gt", "gte", "lt", "lte", "eq", "neq"],
                            },
                            "reference": {
                                "type": "string",
                                "enum": [
                                    "zero",
                                    "absolute_value",
                                    "comparison_period",
                                    "company_average",
                                ],
                            },
                            "value": {"type": ["number", "null"]},
                        },
                        "required": [
                            "metric",
                            "measure",
                            "operator",
                            "reference",
                            "value",
                        ],
                        "additionalProperties": False,
                    },
                },
            },
            "required": ["logic", "items"],
            "additionalProperties": False,
        },
        "contribution": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "target_metric": {"type": ["string", "null"], "enum": METRICS + [None]},
                "group_dimension": {
                    "type": "string",
                    "enum": ["none", "store", "channel"],
                },
                "basis": {
                    "type": "string",
                    "enum": ["absolute_change", "growth_pct"],
                },
            },
            "required": ["enabled", "target_metric", "group_dimension", "basis"],
            "additionalProperties": False,
        },
        "intervention": {
            "type": "object",
            "properties": {
                "enabled": {"type": "boolean"},
                "event_description": {"type": ["string", "null"]},
                "intervention_date": {"type": ["string", "null"]},
                "window_days_before": {"type": ["integer", "null"], "minimum": 1},
                "window_days_after": {"type": ["integer", "null"], "minimum": 1},
                "treatment_stores": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "control_store_mode": {
                    "type": "string",
                    "enum": ["none", "remaining_stores", "explicit_stores"],
                },
                "control_stores": {
                    "type": "array",
                    "items": {"type": "string"},
                },
                "pre_period": PERIOD_SCHEMA,
                "post_period": PERIOD_SCHEMA,
                "net_of_control": {"type": "boolean"},
            },
            "required": [
                "enabled",
                "event_description",
                "intervention_date",
                "window_days_before",
                "window_days_after",
                "treatment_stores",
                "control_store_mode",
                "control_stores",
                "pre_period",
                "post_period",
                "net_of_control",
            ],
            "additionalProperties": False,
        },
        "contains_product_dimension": {"type": "boolean"},
        "presentation": {
            "type": "string",
            "enum": sorted(SUPPORTED_PRESENTATIONS),
        },
        "understood_request": {"type": "string"},
        "needs_clarification": {"type": "boolean"},
        "clarification_question": {"type": ["string", "null"]},
    },
    "required": [
        "version",
        "context_relation",
        "domain_status",
        "time",
        "stores",
        "channels",
        "metrics",
        "operation",
        "comparison",
        "comparison_detail",
        "group_by",
        "selection",
        "conditions",
        "contribution",
        "intervention",
        "contains_product_dimension",
        "presentation",
        "understood_request",
        "needs_clarification",
        "clarification_question",
    ],
    "additionalProperties": False,
}
