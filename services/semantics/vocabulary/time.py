from copy import deepcopy
from datetime import date, datetime, timedelta
from typing import Any, Final
from zoneinfo import ZoneInfo


# =========================================================
# CANONICAL TIME TYPES
# =========================================================

TIME_YESTERDAY: Final[str] = "yesterday"
TIME_TODAY: Final[str] = "today"
TIME_SPECIFIC_DATE: Final[str] = "specific_date"
TIME_DATE_RANGE: Final[str] = "date_range"
TIME_THIS_WEEK: Final[str] = "this_week"
TIME_LAST_WEEK: Final[str] = "last_week"
TIME_THIS_MONTH: Final[str] = "this_month"
TIME_LAST_MONTH: Final[str] = "last_month"
TIME_THIS_QUARTER: Final[str] = "this_quarter"
TIME_LAST_QUARTER: Final[str] = "last_quarter"
TIME_CUSTOM: Final[str] = "custom"
TIME_UNSPECIFIED: Final[str] = "unspecified"


SUPPORTED_TIME_TYPES: Final[set[str]] = {
    TIME_YESTERDAY,
    TIME_TODAY,
    TIME_SPECIFIC_DATE,
    TIME_DATE_RANGE,
    TIME_THIS_WEEK,
    TIME_LAST_WEEK,
    TIME_THIS_MONTH,
    TIME_LAST_MONTH,
    TIME_THIS_QUARTER,
    TIME_LAST_QUARTER,
    TIME_CUSTOM,
    TIME_UNSPECIFIED,
}


# =========================================================
# DEFAULT BUSINESS CALENDAR SETTINGS
# =========================================================

DEFAULT_TIMEZONE: Final[str] = "Asia/Kolkata"

# Python weekday numbering:
# Monday = 0
# Sunday = 6
DEFAULT_WEEK_START_DAY: Final[int] = 0


# =========================================================
# BUSINESS TIME VOCABULARY
# =========================================================

BUSINESS_TIME_TYPES: Final[dict[str, dict]] = {
    TIME_YESTERDAY: {
        "display_name": "Yesterday",
        "description": (
            "The previous calendar date in the client's "
            "configured business timezone."
        ),
        "synonyms": [
            "yesterday",
            "yesterday's",
            "previous day",
            "last day",
            "day before today",
            "kal",
            "kal ka",
            "kal ki",
            "ninna",
            "ninne",
            "yday",
            "ystday",
            "ystrday",
            "yestrday",
        ],
    },

    TIME_TODAY: {
        "display_name": "Today",
        "description": (
            "The current calendar date in the client's "
            "configured business timezone."
        ),
        "synonyms": [
            "today",
            "today's",
            "current day",
            "so far today",
            "till now today",
            "aaj",
            "aaj ka",
            "aaj ki",
            "ivala",
            "eeroju",
            "this day",
        ],
    },

    TIME_THIS_WEEK: {
        "display_name": "This Week",
        "description": (
            "The current calendar week according to the "
            "platform's configured week definition."
        ),
        "synonyms": [
            "this week",
            "current week",
            "week to date",
            "wtd",
            "so far this week",
            "this week's",
            "iss hafte",
            "ee week",
        ],
    },

    TIME_LAST_WEEK: {
        "display_name": "Last Week",
        "description": (
            "The complete calendar week immediately before "
            "the current week."
        ),
        "synonyms": [
            "last week",
            "previous week",
            "prior week",
            "past week",
            "last week's",
            "pichla hafta",
            "pichle hafte",
            "last seven-day week",
        ],
    },

    TIME_THIS_MONTH: {
        "display_name": "This Month",
        "description": (
            "The current calendar month, interpreted as "
            "month-to-date when the month is incomplete."
        ),
        "synonyms": [
            "this month",
            "current month",
            "month to date",
            "month-to-date",
            "mtd",
            "so far this month",
            "this month's",
            "iss mahine",
            "ee month",
        ],
    },

    TIME_LAST_MONTH: {
        "display_name": "Last Month",
        "description": (
            "The complete calendar month immediately before "
            "the current month."
        ),
        "synonyms": [
            "last month",
            "previous month",
            "prior month",
            "past month",
            "last month's",
            "pichla mahina",
            "pichle mahine",
            "previous calendar month",
        ],
    },

    TIME_THIS_QUARTER: {
        "display_name": "This Quarter",
        "description": (
            "The current calendar quarter, interpreted as "
            "quarter-to-date when incomplete."
        ),
        "synonyms": [
            "this quarter",
            "current quarter",
            "quarter to date",
            "quarter-to-date",
            "qtd",
            "so far this quarter",
            "current qtr",
        ],
    },

    TIME_LAST_QUARTER: {
        "display_name": "Last Quarter",
        "description": (
            "The complete calendar quarter immediately before "
            "the current quarter."
        ),
        "synonyms": [
            "last quarter",
            "previous quarter",
            "prior quarter",
            "last qtr",
            "previous qtr",
        ],
    },

    TIME_SPECIFIC_DATE: {
        "display_name": "Specific Date",
        "description": (
            "One explicitly identified calendar date."
        ),
        "synonyms": [
            "on",
            "for the date",
            "on the date",
            "that day",
            "specific date",
            "single date",
        ],
    },

    TIME_DATE_RANGE: {
        "display_name": "Date Range",
        "description": (
            "An inclusive period between a start date "
            "and an end date."
        ),
        "synonyms": [
            "from",
            "to",
            "between",
            "during",
            "for the period",
            "date range",
            "time period",
            "period from",
            "starting",
            "ending",
        ],
    },

    TIME_CUSTOM: {
        "display_name": "Custom Time Period",
        "description": (
            "A meaningful time expression that cannot yet be "
            "represented by another canonical RAL time type."
        ),
        "synonyms": [
            "last sunday",
            "this sunday",
            "last weekend",
            "this weekend",
            "same weekend last month",
            "last 7 days",
            "last 30 days",
            "rolling 7 days",
            "rolling 30 days",
            "first week",
            "second week",
            "first half",
            "second half",
            "breakfast",
            "lunch",
            "dinner",
            "shift",
            "festival period",
        ],
    },

    TIME_UNSPECIFIED: {
        "display_name": "Unspecified Time",
        "description": (
            "The user did not provide a sufficiently clear "
            "time period."
        ),
        "synonyms": [],
    },
}


# =========================================================
# TIME LOOKUP HELPERS
# =========================================================


def get_time_definition(
    time_type: str,
) -> dict:
    """
    Return the vocabulary definition for a canonical time type.
    """
    normalized_time_type = (
        str(time_type)
        .strip()
        .lower()
    )

    if normalized_time_type not in BUSINESS_TIME_TYPES:
        raise ValueError(
            f"Unsupported business time type: {time_type}"
        )

    definition = BUSINESS_TIME_TYPES[
        normalized_time_type
    ]

    return {
        **definition,
        "synonyms": list(
            definition["synonyms"]
        ),
    }


def get_time_display_name(
    time_type: str,
) -> str:
    """
    Return the display name for a canonical time type.
    """
    definition = get_time_definition(
        time_type
    )

    return str(
        definition["display_name"]
    )


def get_time_synonyms(
    time_type: str,
) -> list[str]:
    """
    Return known natural-language expressions for a time type.
    """
    definition = get_time_definition(
        time_type
    )

    return list(
        definition["synonyms"]
    )


def get_all_time_synonyms() -> dict[str, list[str]]:
    """
    Return every canonical time type and its vocabulary.
    """
    return {
        time_type: list(
            definition["synonyms"]
        )
        for (
            time_type,
            definition,
        ) in BUSINESS_TIME_TYPES.items()
    }


def build_time_vocabulary_prompt() -> str:
    """
    Build compact time-vocabulary instructions for the
    RAL intent parser.

    GPT identifies the business meaning of the time phrase.

    Python later resolves relative time types into actual
    calendar dates.
    """
    prompt_lines = [
        "Supported business time types:",
    ]

    for (
        time_type,
        definition,
    ) in BUSINESS_TIME_TYPES.items():
        display_name = definition[
            "display_name"
        ]

        description = definition[
            "description"
        ]

        synonyms = definition[
            "synonyms"
        ]

        prompt_lines.append(
            f"- Canonical time type: {time_type}"
        )

        prompt_lines.append(
            f"  Display name: {display_name}"
        )

        prompt_lines.append(
            f"  Meaning: {description}"
        )

        if synonyms:
            prompt_lines.append(
                "  Common expressions: "
                + ", ".join(
                    synonyms
                )
            )

    return "\n".join(
        prompt_lines
    )


# =========================================================
# DETERMINISTIC DATE HELPERS
# =========================================================


def _get_local_current_date(
    timezone_name: str,
) -> date:
    """
    Return the current date in the configured client timezone.
    """
    try:
        client_timezone = ZoneInfo(
            timezone_name
        )

    except Exception as error:
        raise ValueError(
            f"Invalid timezone: {timezone_name}"
        ) from error

    return datetime.now(
        client_timezone
    ).date()


def _to_iso_date(
    date_value: date,
) -> str:
    """
    Convert a Python date into YYYY-MM-DD format.
    """
    return date_value.isoformat()


def _parse_iso_date(
    value: Any,
    field_name: str,
) -> date:
    """
    Parse and validate a YYYY-MM-DD date value.
    """
    if not isinstance(
        value,
        str,
    ):
        raise ValueError(
            f"{field_name} must be a YYYY-MM-DD string."
        )

    try:
        return date.fromisoformat(
            value
        )

    except ValueError as error:
        raise ValueError(
            f"{field_name} must use YYYY-MM-DD format."
        ) from error


def _get_start_of_week(
    reference_date: date,
    week_start_day: int,
) -> date:
    """
    Return the beginning of the configured calendar week.

    Default:
        Monday to Sunday
    """
    if week_start_day not in range(
        0,
        7,
    ):
        raise ValueError(
            "week_start_day must be between 0 and 6."
        )

    days_since_start = (
        reference_date.weekday()
        - week_start_day
    ) % 7

    return (
        reference_date
        - timedelta(
            days=days_since_start
        )
    )


def _get_previous_month_period(
    reference_date: date,
) -> tuple[date, date]:
    """
    Return the complete previous calendar month.
    """
    current_month_start = date(
        reference_date.year,
        reference_date.month,
        1,
    )

    previous_month_end = (
        current_month_start
        - timedelta(
            days=1
        )
    )

    previous_month_start = date(
        previous_month_end.year,
        previous_month_end.month,
        1,
    )

    return (
        previous_month_start,
        previous_month_end,
    )


def _get_quarter_start_month(
    month_number: int,
) -> int:
    """
    Return the first month number of a calendar quarter.
    """
    return (
        (
            month_number - 1
        )
        // 3
        * 3
        + 1
    )


def _get_previous_quarter_period(
    reference_date: date,
) -> tuple[date, date]:
    """
    Return the complete previous calendar quarter.
    """
    current_quarter_start_month = (
        _get_quarter_start_month(
            reference_date.month
        )
    )

    current_quarter_start = date(
        reference_date.year,
        current_quarter_start_month,
        1,
    )

    previous_quarter_end = (
        current_quarter_start
        - timedelta(
            days=1
        )
    )

    previous_quarter_start_month = (
        _get_quarter_start_month(
            previous_quarter_end.month
        )
    )

    previous_quarter_start = date(
        previous_quarter_end.year,
        previous_quarter_start_month,
        1,
    )

    return (
        previous_quarter_start,
        previous_quarter_end,
    )


# =========================================================
# RAL TIME RESOLUTION
# =========================================================


def resolve_ral_time(
    ral_request: dict[str, Any],
    timezone_name: str = DEFAULT_TIMEZONE,
    week_start_day: int = DEFAULT_WEEK_START_DAY,
    reference_date: date | None = None,
) -> dict[str, Any]:
    """
    Resolve the RAL time type into deterministic calendar dates.

    GPT identifies the meaning:

        last_month

    Python resolves it:

        start_date = YYYY-MM-01
        end_date = final date of previous month

    Supported deterministic resolution:

    - yesterday
    - today
    - this week
    - last week
    - this month
    - last month
    - this quarter
    - last quarter
    - specific date
    - explicit date range

    Custom and unspecified time expressions remain unchanged
    until their business rules are implemented.
    """
    if not isinstance(
        ral_request,
        dict,
    ):
        raise ValueError(
            "RAL request must be an object."
        )

    if "time" not in ral_request:
        raise ValueError(
            "RAL request does not contain time."
        )

    resolved_request = deepcopy(
        ral_request
    )

    time_value = resolved_request[
        "time"
    ]

    if not isinstance(
        time_value,
        dict,
    ):
        raise ValueError(
            "RAL time must be an object."
        )

    time_type = time_value.get(
        "type"
    )

    if time_type not in SUPPORTED_TIME_TYPES:
        raise ValueError(
            f"Unsupported RAL time type: {time_type}"
        )

    current_date = (
        reference_date
        if reference_date is not None
        else _get_local_current_date(
            timezone_name
        )
    )

    resolved_start_date: date | None = None
    resolved_end_date: date | None = None

    if time_type == TIME_YESTERDAY:
        resolved_start_date = (
            current_date
            - timedelta(
                days=1
            )
        )

        resolved_end_date = (
            resolved_start_date
        )

    elif time_type == TIME_TODAY:
        resolved_start_date = current_date
        resolved_end_date = current_date

    elif time_type == TIME_THIS_WEEK:
        resolved_start_date = (
            _get_start_of_week(
                reference_date=current_date,
                week_start_day=week_start_day,
            )
        )

        resolved_end_date = current_date

    elif time_type == TIME_LAST_WEEK:
        current_week_start = (
            _get_start_of_week(
                reference_date=current_date,
                week_start_day=week_start_day,
            )
        )

        resolved_end_date = (
            current_week_start
            - timedelta(
                days=1
            )
        )

        resolved_start_date = (
            resolved_end_date
            - timedelta(
                days=6
            )
        )

    elif time_type == TIME_THIS_MONTH:
        resolved_start_date = date(
            current_date.year,
            current_date.month,
            1,
        )

        resolved_end_date = current_date

    elif time_type == TIME_LAST_MONTH:
        (
            resolved_start_date,
            resolved_end_date,
        ) = _get_previous_month_period(
            current_date
        )

    elif time_type == TIME_THIS_QUARTER:
        quarter_start_month = (
            _get_quarter_start_month(
                current_date.month
            )
        )

        resolved_start_date = date(
            current_date.year,
            quarter_start_month,
            1,
        )

        resolved_end_date = current_date

    elif time_type == TIME_LAST_QUARTER:
        (
            resolved_start_date,
            resolved_end_date,
        ) = _get_previous_quarter_period(
            current_date
        )

    elif time_type == TIME_SPECIFIC_DATE:
        explicit_start_date = (
            _parse_iso_date(
                time_value.get(
                    "start_date"
                ),
                "time.start_date",
            )
        )

        explicit_end_date = (
            _parse_iso_date(
                time_value.get(
                    "end_date"
                ),
                "time.end_date",
            )
        )

        if (
            explicit_start_date
            != explicit_end_date
        ):
            raise ValueError(
                "A specific date must have identical "
                "start_date and end_date."
            )

        resolved_start_date = (
            explicit_start_date
        )

        resolved_end_date = (
            explicit_end_date
        )

    elif time_type == TIME_DATE_RANGE:
        resolved_start_date = (
            _parse_iso_date(
                time_value.get(
                    "start_date"
                ),
                "time.start_date",
            )
        )

        resolved_end_date = (
            _parse_iso_date(
                time_value.get(
                    "end_date"
                ),
                "time.end_date",
            )
        )

        if (
            resolved_start_date
            > resolved_end_date
        ):
            raise ValueError(
                "The RAL start date cannot be after "
                "the RAL end date."
            )

    elif time_type in {
        TIME_CUSTOM,
        TIME_UNSPECIFIED,
    }:
        return resolved_request

    if (
        resolved_start_date is None
        or resolved_end_date is None
    ):
        return resolved_request

    time_value["start_date"] = (
        _to_iso_date(
            resolved_start_date
        )
    )

    time_value["end_date"] = (
        _to_iso_date(
            resolved_end_date
        )
    )

    return resolved_request