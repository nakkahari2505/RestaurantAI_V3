import json
import re
import shutil
import threading
import time
from pathlib import Path
from uuid import uuid4

from services.core.data_loader import (
    load_auberry_workbook,
)
from services.reports.kpi_comparison.report import (
    get_kpi_period_comparison_report,
)
from services.reports.kpi_comparison.image import (
    generate_kpi_period_comparison_image,
)
from services.reports.sales_period.report import (
    get_store_performance_report,
)
from services.reports.sales_period.image import (
    generate_sales_for_a_period_image,
)
from services.reports.yesterday.morning_report import (
    format_yesterday_morning_narrative,
    get_yesterday_morning_report,
)
from services.reports.yesterday.morning_report_image import (
    generate_yesterday_morning_report_image,
)


# =========================================================
# EXISTING FIXED-COMMAND PATTERNS
# =========================================================

DATE_TOKEN_PATTERN = (
    r"\d{1,2}(?:-[a-zA-Z]{3}-|\s+[a-zA-Z]{3}\s+)\d{4}"
)


SALES_PERIOD_PATTERN = re.compile(
    rf"^sales\s+from\s+"
    rf"({DATE_TOKEN_PATTERN})"
    rf"\s+to\s+"
    rf"({DATE_TOKEN_PATTERN})$",
    re.IGNORECASE,
)


COMPARISON_PATTERN = re.compile(
    rf"^compare\s+"
    rf"({DATE_TOKEN_PATTERN})\s+"
    rf"({DATE_TOKEN_PATTERN})\s+"
    rf"({DATE_TOKEN_PATTERN})\s+"
    rf"({DATE_TOKEN_PATTERN})$",
    re.IGNORECASE,
)


# =========================================================
# BOUNDED CLARIFICATION CONTEXT
# =========================================================

# Clarification state is deliberately tiny and short-lived.
#
# IMPORTANT:
# Do not keep this only in a Python module-level dictionary.
# The WhatsApp endpoint runs work in background tasks and Uvicorn
# may reload/recreate module state during local development. A tiny
# file-backed cache makes the second turn deterministic across those
# boundaries.
_CLARIFICATION_TTL_SECONDS = 15 * 60

_CLARIFICATION_STATE_PATH = (
    Path("runtime")
    / "clarification_context.json"
)

_CLARIFICATION_STATE_LOCK = (
    threading.Lock()
)


def _load_clarification_state() -> dict:
    with _CLARIFICATION_STATE_LOCK:
        if not _CLARIFICATION_STATE_PATH.exists():
            return {}

        try:
            raw = json.loads(
                _CLARIFICATION_STATE_PATH.read_text(
                    encoding="utf-8"
                )
            )
        except Exception:
            return {}

        if not isinstance(
            raw,
            dict,
        ):
            return {}

        return raw


def _save_clarification_state(
    state: dict,
) -> None:
    with _CLARIFICATION_STATE_LOCK:
        _CLARIFICATION_STATE_PATH.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        _CLARIFICATION_STATE_PATH.write_text(
            json.dumps(
                state,
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )


def _clean_expired_clarifications(
    state: dict,
) -> dict:
    now = time.time()

    cleaned = {}

    for key, value in state.items():
        if not isinstance(
            value,
            dict,
        ):
            continue

        created_at = float(
            value.get(
                "created_at",
                0.0,
            )
        )

        if (
            now - created_at
            <= _CLARIFICATION_TTL_SECONDS
        ):
            cleaned[key] = value

    return cleaned


def _get_pending_clarification(
    conversation_id: str,
) -> dict | None:
    state = _clean_expired_clarifications(
        _load_clarification_state()
    )

    _save_clarification_state(
        state
    )

    pending = state.get(
        conversation_id
    )

    if isinstance(
        pending,
        dict,
    ):
        return pending

    return None


def _set_pending_clarification(
    conversation_id: str,
    original_message: str,
) -> None:
    state = _clean_expired_clarifications(
        _load_clarification_state()
    )

    state[
        conversation_id
    ] = {
        "original_message": (
            original_message
        ),
        "created_at": time.time(),
    }

    _save_clarification_state(
        state
    )

    print(
        "Clarification context stored for:",
        conversation_id,
    )


def _clear_pending_clarification(
    conversation_id: str,
) -> None:
    state = _clean_expired_clarifications(
        _load_clarification_state()
    )

    if conversation_id in state:
        state.pop(
            conversation_id,
            None,
        )

        _save_clarification_state(
            state
        )

        print(
            "Clarification context cleared for:",
            conversation_id,
        )


def _prepare_conversation_message(
    message: str,
    conversation_id: str | None,
) -> tuple[str, bool]:
    """
    Merge one clarification answer back into the ORIGINAL request.

    Example:
        Original:
            How is Punjagutta store doing?
            Can you plot its KPIs for last one year

        Clarification:
            ADS

        Parser receives:
            Original request + explicit clarification answer.

    This prevents RestaurantAI from forgetting store, period, grouping
    or presentation context after asking one question.
    """
    if not conversation_id:
        return message, False

    pending = _get_pending_clarification(
        conversation_id
    )

    if not pending:
        print(
            "No clarification context found for:",
            conversation_id,
        )

        return message, False

    original_message = str(
        pending.get(
            "original_message",
            "",
        )
    ).strip()

    if not original_message:
        _clear_pending_clarification(
            conversation_id
        )

        return message, False

    combined_message = (
        f"{original_message}. "
        f"The user answered the clarification question with: "
        f"{message}. "
        f"Use this answer to fill the missing information in the "
        f"original request. Preserve all store, time-period, grouping "
        f"and presentation details already present in the original "
        f"request."
    )

    print(
        "Clarification context restored:",
        combined_message,
    )

    return combined_message, True


def _finalize_conversation_response(
    response: dict,
    conversation_id: str | None,
    original_incoming_message: str,
    was_followup: bool,
) -> dict:
    """
    Product rule:
        Supported + complete -> execute.
        Supported + one missing essential input -> ask once.
        After that follow-up -> execute or stop. Never interrogate.
    """
    if not conversation_id:
        response.pop(
            "_clarification_required",
            None,
        )

        return response

    needs_clarification = bool(
        response.get(
            "_clarification_required",
            False,
        )
    )

    if needs_clarification:
        if was_followup:
            _clear_pending_clarification(
                conversation_id
            )

            return _build_text_response(
                "I understood the request, but I cannot execute it "
                "reliably in the current version. This is outside my "
                "current supported scope."
            )

        _set_pending_clarification(
            conversation_id=conversation_id,
            original_message=(
                original_incoming_message
            ),
        )

        response.pop(
            "_clarification_required",
            None,
        )

        return response

    _clear_pending_clarification(
        conversation_id
    )

    response.pop(
        "_clarification_required",
        None,
    )

    return response


# =========================================================
# COMMON HELPERS
# =========================================================


def _display_date(
    date_text: str,
) -> str:
    """
    Convert any accepted input date into the official
    RestaurantAI display format: DD-Mmm-YYYY.
    """
    cleaned_date = " ".join(
        str(date_text).strip().split()
    )

    cleaned_date = cleaned_date.replace(
        " ",
        "-",
    )

    parts = cleaned_date.split("-")

    if len(parts) != 3:
        return cleaned_date

    day_text, month_text, year_text = parts

    try:
        day_number = int(
            day_text
        )

    except ValueError:
        return cleaned_date

    return (
        f"{day_number:02d}-"
        f"{month_text.title()}-"
        f"{year_text}"
    )


def _build_text_response(
    body: str,
) -> dict:
    """
    Build one standard WhatsApp text response.
    """
    return {
        "response_type": "text",
        "body": str(body),
    }


def _build_media_response(
    body: str,
    relative_media_url: str,
) -> dict:
    """
    Build one standard WhatsApp media response.

    main.py already converts relative_media_url into the
    public Railway/local URL used by Twilio.
    """
    return {
        "response_type": "media",
        "body": str(body),
        "relative_media_url": str(
            relative_media_url
        ),
    }


def _publish_chart_for_whatsapp(
    chart_path: Path,
) -> str:
    """
    Copy a generated chart into the existing /static mount so
    Twilio can retrieve it through a public URL.

    Chart Engine owns rendering.
    Message Router owns delivery preparation.

    A unique filename is used so WhatsApp/Twilio cannot show
    a stale cached image from an earlier request.
    """
    source_path = Path(
        chart_path
    )

    if not source_path.exists():
        raise FileNotFoundError(
            "Generated chart file was not found: "
            f"{source_path}"
        )

    project_root = (
        Path(__file__)
        .resolve()
        .parent
        .parent
        .parent
    )

    static_reports_directory = (
        project_root
        / "static"
        / "reports"
    )

    static_reports_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    public_file_name = (
        f"restaurantai_chart_"
        f"{uuid4().hex}.png"
    )

    public_file_path = (
        static_reports_directory
        / public_file_name
    )

    shutil.copy2(
        source_path,
        public_file_path,
    )

    return (
        f"/static/reports/"
        f"{public_file_name}"
    )


def _build_chart_caption(
    chart_spec: dict,
) -> str:
    """
    Build the short text that accompanies a WhatsApp chart.
    """
    title = str(
        chart_spec.get(
            "title",
            "RestaurantAI",
        )
    ).strip()

    subtitle = str(
        chart_spec.get(
            "subtitle",
            "",
        )
    ).strip()

    if subtitle:
        return (
            f"📊 {title}\n"
            f"{subtitle}"
        )

    return (
        f"📊 {title}"
    )


# =========================================================
# EXISTING CAPABILITY 1: YESTERDAY SALES
# =========================================================


def _run_yesterday_sales() -> dict:
    """
    Run the management-style morning report for the fixed
    "Yesterday sales" command.

    Output:
    - narrative management summary in WhatsApp text,
    - professional three-section PNG report as media.
    """
    try:
        data = load_auberry_workbook()

        report = (
            get_yesterday_morning_report(
                data
            )
        )

        data_status = report.get(
            "data_status",
            {},
        )

        if not data_status.get(
            "yesterday_available",
            False,
        ):
            requested_date = (
                report[
                    "labels"
                ][
                    "yesterday_full"
                ]
            )

            latest_available = (
                data_status.get(
                    "latest_available_date"
                )
            )

            latest_text = (
                latest_available
                if latest_available
                else "No sales date available"
            )

            return _build_text_response(
                "⚠️ No sales data is available for "
                f"{requested_date}.\n"
                f"Latest available data: {latest_text}."
            )

        narrative = (
            format_yesterday_morning_narrative(
                report,
                data=data,
            )
        )

        image_result = (
            generate_yesterday_morning_report_image(
                report=report,
                file_name=(
                    f"yesterday_morning_"
                    f"{uuid4().hex}.png"
                ),
                narrative=narrative,
            )
        )

        relative_media_url = (
            _publish_chart_for_whatsapp(
                Path(
                    image_result[
                        "file_path"
                    ]
                )
            )
        )

        short_caption = (
            "📊 Yesterday Sales Report – "
            + report["labels"]["yesterday_full"]
        )

        return _build_media_response(
            body=short_caption,
            relative_media_url=(
                relative_media_url
            ),
        )

    except ValueError as error:
        print(
            "Yesterday morning report validation error:",
            repr(error),
        )

        return _build_text_response(
            str(error)
        )

    except Exception as error:
        print(
            "Yesterday morning report error:",
            repr(error),
        )

        return _build_text_response(
            "The morning sales report could not be generated. "
            "Please try again."
        )


def _try_yesterday_morning_report_semantic(
    user_message: str,
) -> dict | None:
    """
    Route natural-language equivalents of the overall
    Yesterday Sales question to the management morning report.

    This deliberately uses the existing RAL language-understanding
    layer instead of maintaining a long list of phrases, spelling
    variants or Hinglish expressions.

    Only the plain OVERALL Sales + Yesterday request is intercepted.
    Requests that add a store, channel, aggregator, category, item,
    grouping, trend or comparison continue through the normal RAL
    analytics pipeline.
    """
    try:
        from services.semantics.intent_parser import (
            parse_ral_request,
        )

        ral_request = parse_ral_request(
            user_message=user_message
        )

        print(
            "Yesterday semantic RAL:",
            ral_request,
        )

        if not isinstance(ral_request, dict):
            return None

        if ral_request.get(
            "needs_clarification",
            False,
        ):
            return None

        if ral_request.get(
            "clarification_question"
        ):
            return None

        metric_name = str(
            ral_request.get(
                "metric",
                "",
            )
        ).strip().lower()

        if metric_name != "sales":
            return None

        time_value = ral_request.get(
            "time",
            {},
        )

        if not isinstance(time_value, dict):
            return None

        time_type = str(
            time_value.get(
                "type",
                "",
            )
        ).strip().lower()

        # The parser's semantic time label is the primary signal.
        # The explicit word check is only a safe fallback for a parser
        # version that resolves the date but labels the type differently.
        normalized_text = " ".join(
            str(user_message).lower().split()
        )

        yesterday_semantic = (
            time_type == "yesterday"
            or "yesterday" in normalized_text
            or "kal" in normalized_text
        )

        if not yesterday_semantic:
            return None

        # Morning Report is specifically the overall business view.
        # Any analytical slice must remain with the generic RAL engine.
        for filter_key in (
            "stores",
            "regions",
            "channels",
            "aggregators",
            "categories",
            "items",
        ):
            if ral_request.get(
                filter_key,
                [],
            ):
                return None

        grouping = ral_request.get(
            "grouping",
            {},
        )

        if (
            isinstance(grouping, dict)
            and grouping.get(
                "enabled",
                False,
            )
        ):
            return None

        trend = ral_request.get(
            "trend",
            {},
        )

        if (
            isinstance(trend, dict)
            and trend.get(
                "enabled",
                False,
            )
        ):
            return None

        comparison = ral_request.get(
            "comparison",
            {},
        )

        if (
            isinstance(comparison, dict)
            and comparison.get(
                "enabled",
                False,
            )
        ):
            return None

        print(
            "Routing to Yesterday Morning Report."
        )

        return _run_yesterday_sales()

    except Exception as error:
        # Semantic interception must never break the existing router.
        # If understanding fails here, normal Selection/RAL handling
        # below still gets its chance to execute the request.
        print(
            "Yesterday semantic routing error:",
            repr(error),
        )

        return None


# =========================================================
# GENERIC RAL EXECUTION
# =========================================================


def _ral_is_ready_for_execution(
    ral_request: dict,
) -> bool:
    """
    Decide whether a RAL request is safe for the generic
    deterministic execution flow.

    The generic flow currently supports:

    - one metric,
    - one resolved date period,
    - stores,
    - channels,
    - aggregators,
    - categories,
    - items,
    - single or multi-dimensional grouping,
    - daily / weekly / monthly trends,
    - text presentation,
    - line-chart presentation,
    - bar-chart presentation.

    It does not yet execute:

    - unresolved time periods,
    - comparisons through the generic RAL path,
    - clarification-dependent requests,
    - region filters.
    """
    if not isinstance(
        ral_request,
        dict,
    ):
        return False

    if ral_request.get(
        "needs_clarification",
        False,
    ):
        return False

    clarification_question = (
        ral_request.get(
            "clarification_question"
        )
    )

    if clarification_question:
        return False

    time_value = ral_request.get(
        "time",
        {},
    )

    if not isinstance(
        time_value,
        dict,
    ):
        return False

    start_date = time_value.get(
        "start_date"
    )

    end_date = time_value.get(
        "end_date"
    )

    if not isinstance(
        start_date,
        str,
    ):
        return False

    if not isinstance(
        end_date,
        str,
    ):
        return False

    comparison = ral_request.get(
        "comparison",
        {},
    )

    if (
        isinstance(
            comparison,
            dict,
        )
        and comparison.get(
            "enabled",
            False,
        )
    ):
        return False

    if ral_request.get(
        "regions",
        [],
    ):
        return False

    metric_name = ral_request.get(
        "metric"
    )

    if not isinstance(
        metric_name,
        str,
    ):
        return False

    if not metric_name.strip():
        return False

    return True


def _build_clarification_response(
    ral_request: dict,
) -> dict | None:
    """V1 rule: never ask a follow-up question. Execute or stop."""
    if not ral_request.get("needs_clarification", False):
        return None

    return _build_text_response(
        "Sorry, I’m unable to answer this question with my current capabilities."
    )

def _try_selection_execution(
    user_message: str,
) -> dict | None:
    """
    Execute top-one / bottom-one "which / what / when"
    questions without disturbing ordinary RAL execution.

    Architecture:

        Natural language
            ↓
        Existing RAL parser
            ↓
        Selection detector
            ↓
        Time default/selection preparation
            ↓
        Existing Filter Engine
            ↓
        Existing Grouping OR Trend Engine
            ↓
        Selection Engine picks max/min
            ↓
        WhatsApp text

    This keeps all existing filter/business rules reusable.
    """
    try:
        from services.analytics.filter_engine import (
            apply_ral_filters,
        )
        from services.semantics.intent_parser import (
            parse_ral_request,
        )
        from services.analytics.selection_engine import (
            detect_selection_plan,
            execute_selection,
            format_selection_result,
            prepare_selection_ral,
        )

        # First use the same language-understanding layer that
        # already understands Store/Channel/Category/Item
        # filters. Selection does not create another LLM parser.
        ral_request = parse_ral_request(
            user_message=user_message
        )

        plan = detect_selection_plan(
            user_message=user_message,
            ral_request=ral_request,
        )

        if plan is None:
            return None

        (
            prepared_ral,
            time_meta,
        ) = prepare_selection_ral(
            user_message=user_message,
            ral_request=ral_request,
        )

        print(
            "Selection plan:",
            plan,
        )

        print(
            "Selection RAL:",
            prepared_ral,
        )

        # Preserve any genuine ambiguity that Selection did not
        # deterministically resolve (for example product ambiguity).
        clarification_response = (
            _build_clarification_response(
                prepared_ral
            )
        )

        if clarification_response is not None:
            return clarification_response

        time_value = prepared_ral.get(
            "time",
            {},
        )

        if (
            not isinstance(
                time_value,
                dict,
            )
            or not time_value.get(
                "start_date"
            )
            or not time_value.get(
                "end_date"
            )
        ):
            return _build_text_response(
                "Sorry, I’m unable to answer this question with my current capabilities."
            )

        data = load_auberry_workbook()

        filtered_sales = apply_ral_filters(
            data=data,
            ral_request=prepared_ral,
        )

        if len(filtered_sales) == 0:
            return _build_text_response(
                "I could not find any matching sales records "
                "for that combination, so I have not treated "
                "the result as zero."
            )

        selection_result = execute_selection(
            filtered_sales=filtered_sales,
            data=data,
            ral_request=prepared_ral,
            plan=plan,
            time_meta=time_meta,
        )

        print(
            "Selection result:",
            selection_result,
        )

        return _build_text_response(
            format_selection_result(
                selection_result
            )
        )

    except ValueError as error:
        print(
            "Selection validation/execution error:",
            repr(error),
        )

        return _build_text_response(
            str(error)
        )

    except Exception as error:
        print(
            "Selection execution error:",
            repr(error),
        )

        return _build_text_response(
            "I understood the ranking question, but the result "
            "could not be generated safely. Please try again."
        )


def _try_generic_ral_execution(
    user_message: str,
) -> dict | None:
    """
    Execute the generic RestaurantAI pipeline.

        Natural language
            ↓
        RAL
            ↓
        Deterministic filters
            ↓
        One of:
            - Metric Engine
            - Grouping Engine
            - Trend Engine
            ↓
        Presentation Engine
            ↓
        One of:
            - WhatsApp text
            - Chart Engine -> PNG -> WhatsApp media

    Stable fixed commands are still handled before this
    function by route_message().
    """
    try:
        from services.presentation.chart_engine import (
            render_chart,
        )
        from services.analytics.filter_engine import (
            apply_ral_filters,
        )
        from services.presentation.formatter import (
            format_ral_metric_reply,
        )
        from services.analytics.grouping_engine import (
            calculate_grouped_metric,
        )
        from services.semantics.intent_parser import (
            parse_ral_request,
        )
        from services.presentation.presentation_engine import (
            present_result,
        )
        from services.presentation.pivot_table_image import (
            generate_grouped_pivot_image,
        )
        from services.analytics.trend_engine import (
            calculate_trend,
        )
        from services.semantics.vocabulary.metrics import (
            calculate_metric,
        )

        # =================================================
        # 1. UNDERSTAND
        # =================================================

        ral_request = parse_ral_request(
            user_message=user_message
        )

        print(
            "Generic RAL request:",
            ral_request,
        )

        clarification_response = (
            _build_clarification_response(
                ral_request
            )
        )

        if clarification_response is not None:
            return clarification_response

        if not _ral_is_ready_for_execution(
            ral_request
        ):
            return None

        # =================================================
        # 2. FILTER
        # =================================================

        data = load_auberry_workbook()

        filtered_sales = apply_ral_filters(
            data=data,
            ral_request=ral_request,
        )

        print(
            "Generic RAL filtered rows:",
            len(
                filtered_sales
            ),
        )

        # Important business guardrail:
        # no matching rows must not silently become "0".
        if len(filtered_sales) == 0:
            return _build_text_response(
                "I could not find any matching sales records "
                "for that combination, so I have not treated "
                "the result as zero."
            )

        trend = ral_request.get(
            "trend",
            {},
        )

        grouping = ral_request.get(
            "grouping",
            {},
        )

        trend_enabled = bool(
            isinstance(
                trend,
                dict,
            )
            and trend.get(
                "enabled",
                False,
            )
        )

        grouping_enabled = bool(
            isinstance(
                grouping,
                dict,
            )
            and grouping.get(
                "enabled",
                False,
            )
        )

        # =================================================
        # 3A. TREND EXECUTION
        # =================================================

        if trend_enabled:
            analytics_result = (
                calculate_trend(
                    filtered_sales=filtered_sales,
                    data=data,
                    ral_request=ral_request,
                )
            )

            presentation_result = (
                present_result(
                    result=analytics_result,
                    result_type="trend",
                    ral_request=ral_request,
                )
            )

            print(
                "Generic RAL trend result:",
                {
                    "metric": analytics_result.get(
                        "metric"
                    ),
                    "grain": analytics_result.get(
                        "grain"
                    ),
                    "point_count": analytics_result.get(
                        "point_count"
                    ),
                    "grouping_enabled": (
                        analytics_result.get(
                            "grouping_enabled"
                        )
                    ),
                },
            )

            if (
                presentation_result.get(
                    "mode"
                )
                == "text"
            ):
                return _build_text_response(
                    presentation_result.get(
                        "text",
                        "",
                    )
                )

            if (
                presentation_result.get(
                    "mode"
                )
                == "chart"
            ):
                chart_spec = (
                    presentation_result[
                        "chart_spec"
                    ]
                )

                chart_file_name = (
                    f"restaurantai_"
                    f"{uuid4().hex}.png"
                )

                chart_path = render_chart(
                    chart_spec=chart_spec,
                    file_name=chart_file_name,
                )

                relative_media_url = (
                    _publish_chart_for_whatsapp(
                        chart_path
                    )
                )

                return _build_media_response(
                    body=_build_chart_caption(
                        chart_spec
                    ),
                    relative_media_url=(
                        relative_media_url
                    ),
                )

            raise ValueError(
                "Trend presentation returned an "
                "unsupported mode."
            )

        # =================================================
        # 3B. GROUPED EXECUTION
        # =================================================

        if grouping_enabled:
            analytics_result = (
                calculate_grouped_metric(
                    filtered_sales=filtered_sales,
                    data=data,
                    ral_request=ral_request,
                )
            )

            print(
                "Generic RAL grouped result:",
                {
                    "metric": analytics_result.get(
                        "metric"
                    ),
                    "grouping_dimensions": (
                        analytics_result.get(
                            "grouping_dimensions"
                        )
                    ),
                    "row_count": analytics_result.get(
                        "row_count"
                    ),
                },
            )

            presentation_result = (
                present_result(
                    result=analytics_result,
                    result_type="grouped",
                    ral_request=ral_request,
                )
            )

            presentation_mode = (
                presentation_result.get(
                    "mode"
                )
            )

            if presentation_mode == "text":
                return _build_text_response(
                    presentation_result.get(
                        "text",
                        "",
                    )
                )

            if presentation_mode == "chart":
                chart_spec = (
                    presentation_result[
                        "chart_spec"
                    ]
                )

                chart_file_name = (
                    f"restaurantai_"
                    f"{uuid4().hex}.png"
                )

                chart_path = render_chart(
                    chart_spec=chart_spec,
                    file_name=chart_file_name,
                )

                relative_media_url = (
                    _publish_chart_for_whatsapp(
                        chart_path
                    )
                )

                return _build_media_response(
                    body=_build_chart_caption(
                        chart_spec
                    ),
                    relative_media_url=(
                        relative_media_url
                    ),
                )

            if presentation_mode == "pivot_table":
                pivot_spec = (
                    presentation_result[
                        "pivot_spec"
                    ]
                )

                pivot_file_name = (
                    f"restaurantai_pivot_"
                    f"{uuid4().hex}.png"
                )

                pivot_result = (
                    generate_grouped_pivot_image(
                        pivot_spec=pivot_spec,
                        file_name=(
                            pivot_file_name
                        ),
                    )
                )

                relative_media_url = (
                    _publish_chart_for_whatsapp(
                        Path(
                            pivot_result[
                                "file_path"
                            ]
                        )
                    )
                )

                title = str(
                    pivot_spec.get(
                        "title",
                        "RestaurantAI Analysis",
                    )
                )

                subtitle = str(
                    pivot_spec.get(
                        "subtitle",
                        "",
                    )
                )

                body = (
                    f"📊 {title}"
                )

                if subtitle:
                    body += (
                        f"\n{subtitle}"
                    )

                return _build_media_response(
                    body=body,
                    relative_media_url=(
                        relative_media_url
                    ),
                )

            raise ValueError(
                "Grouped presentation returned an "
                "unsupported mode."
            )

        # =================================================
        # 3C. SINGLE METRIC EXECUTION
        # =================================================

        metric_value = calculate_metric(
            metric_name=ral_request[
                "metric"
            ],
            filtered_df=filtered_sales,
        )

        reply_text = format_ral_metric_reply(
            ral_request=ral_request,
            metric_value=metric_value,
        )

        print(
            "Generic RAL metric result:",
            {
                "metric": ral_request[
                    "metric"
                ],
                "matching_rows": len(
                    filtered_sales
                ),
                "metric_value": metric_value,
            },
        )

        return _build_text_response(
            reply_text
        )

    except ValueError as error:
        print(
            "Generic RAL validation/execution error:",
            repr(error),
        )

        return _build_text_response(
            str(error)
        )

    except Exception as error:
        print(
            "Generic RAL execution error:",
            repr(error),
        )

        return _build_text_response(
            "I understood the request, but the result "
            "could not be generated safely. Please try again."
        )



# =========================================================
# RESTAURANTAI V2 CORE BUSINESS QUERY
# =========================================================

def _try_business_query_v2(
    user_message: str,
    conversation_id: str | None,
) -> dict | None:
    """
    V2 semantic-planner path for the first analytical layer:

        Time × Store × Channel × KPI × Operation
        + conversation context
        + tolerant natural WhatsApp language

    This path is intentionally additive. Product/category requests and
    operations not yet executable here fall through to the proven V1/RAL
    paths instead of breaking existing capabilities.
    """
    try:
        from services.analytics.business_query_engine import (
            execute_business_query,
        )
        from services.presentation.business_query_presenter import (
            present_business_query,
        )
        from services.semantics.business_query_parser import (
            parse_business_query,
        )
        from services.semantics.conversation_state import (
            get_conversation_query,
            set_conversation_query,
        )

        previous_query = get_conversation_query(
            conversation_id
        )

        business_query = parse_business_query(
            user_message=user_message,
            previous_query=previous_query,
        )

        print(
            "V2 BusinessQuery:",
            business_query,
        )

        # Domain gate: unrelated/general-chat messages must terminate here.
        # They must NOT fall through to the legacy RAL/router, where a model
        # could accidentally force them into restaurant analytics semantics.
        domain_status = str(
            business_query.get(
                "domain_status",
                "business_query",
            )
        ).strip().lower()

        if domain_status == "out_of_domain":
            return _build_text_response(
                "I can help with questions about your restaurant business "
                "— sales, transactions, APT, stores, channels, products, "
                "performance, comparisons and related analysis. "
                "That question is outside my business scope."
            )

        if domain_status == "conversational":
            return _build_text_response(
                "Sure. Ask me anything about your restaurant business."
            )

        # A domain-level ambiguity is still a legitimate RestaurantAI turn.
        # Let the normal clarification contract handle it rather than sending
        # it to unrelated legacy routes.
        if domain_status == "ambiguous":
            question = business_query.get(
                "clarification_question"
            )
            if question:
                return _build_text_response(str(question))
            return _build_text_response(
                "I think this may be a restaurant business question, but I "
                "need a little more detail to understand what you want to "
                "analyse."
            )

        # Menu/category/item remains on the existing product-aware RAL path
        # for this milestone. Never silently drop that business dimension.
        if business_query.get(
            "contains_product_dimension",
            False,
        ):
            return None

        result = execute_business_query(
            data=load_auberry_workbook(),
            query=business_query,
        )

        if result.get("status") == "not_yet_executable":
            return None

        response = present_business_query(
            query=business_query,
            result=result,
        )

        if response.get("status") == "fallback":
            return None

        if (
            result.get("status") == "ok"
            and not business_query.get("needs_clarification", False)
        ):
            set_conversation_query(
                conversation_id,
                business_query,
            )

        return response

    except Exception as error:
        # V2 is introduced as a safe parallel path. A planner/execution
        # failure must never remove an already-working V1 capability.
        print(
            "V2 BusinessQuery execution error:",
            repr(error),
        )
        return None

# =========================================================
# MANAGEMENT INTELLIGENCE
# =========================================================


def _run_management_intelligence() -> dict:
    """
    Build the current RestaurantAI management-intelligence message
    and return it through the standard WhatsApp text-response shape.

    The import stays local deliberately so unfinished/local
    intelligence work can never prevent the normal router from loading.
    """
    from services.intelligence.intelligence_orchestrator import (
        build_management_message,
    )

    message = build_management_message()

    return _build_text_response(
        message
    )


# =========================================================
# MAIN WHATSAPP ROUTER
# =========================================================


def route_message(
    message: str,
    conversation_id: str | None = None,
) -> dict:
    """
    Route a WhatsApp message.

    Routing order:

    1. Stable existing deterministic commands.
    2. Generic RAL execution.
    3. Specific invalid-command guidance.
    4. Unsupported-request message.
    """
    original_incoming_message = " ".join(
        str(message).strip().split()
    )

    # V1 is deliberately single-turn: no clarification context is restored.
    # Every incoming message must stand on its own.
    was_followup = False
    normalized_message = " ".join(
        str(original_incoming_message).strip().split()
    )

    normalized_lower = (
        normalized_message.lower()
    )

    if not original_incoming_message:
        return _build_text_response(
            "Please send a restaurant business question."
        )

    # Product-master questions are deterministic and must be checked
    # before the semantic/RAL pipeline. The lookup itself owns detection
    # for MRP / price / COGS / cost / gross-margin wording and typo variants.
    from services.analytics.product_master_lookup import (
        answer_product_master_question,
    )

    product_master_answer = answer_product_master_question(
        data=load_auberry_workbook(),
        message=normalized_message,
    )

    if product_master_answer is not None:
        return _build_text_response(product_master_answer)

    # =====================================================
    # V2 CORE SEMANTIC PLANNER
    # =====================================================
    v2_response = _try_business_query_v2(
        user_message=normalized_message,
        conversation_id=conversation_id,
    )

    if v2_response is not None:
        return v2_response

    # =====================================================
    # MONTHLY TREND CHART
    # Sales / Transactions / ADS / ADT / APT
    # Company or one store
    # Last 1-6 completed calendar months
    # =====================================================
    from services.analytics.sales_trend import (
        get_sales_trend_report,
        is_sales_trend_question,
    )

    if is_sales_trend_question(
        normalized_message
    ):
        from services.reports.trends.sales_trend_image import (
            generate_sales_trend_image,
        )

        data = load_auberry_workbook()

        try:
            trend_report = get_sales_trend_report(
                data=data,
                message=normalized_message,
            )

            chart_path = generate_sales_trend_image(
                trend_report
            )

            relative_media_url = (
                _publish_chart_for_whatsapp(
                    chart_path
                )
            )

            return _build_media_response(
                body=(
                    "📈 "
                    + str(
                        trend_report[
                            "title"
                        ]
                    )
                ),
                relative_media_url=(
                    relative_media_url
                ),
            )

        except ValueError as error:
            return _build_text_response(
                str(error)
            )

        except Exception as error:
            print(
                "Monthly trend report error:",
                repr(error),
            )

            return _build_text_response(
                "The monthly trend chart could not be generated. "
                "Please try again."
            )

    management_intelligence_commands = {
        "management intelligence",
    }

    # =====================================================
    # MANAGEMENT INTELLIGENCE
    # FIXED COMMAND - FIRST OWNER-FACING BI MESSAGE
    # =====================================================

    if (
        normalized_lower
        in management_intelligence_commands
    ):
        return _run_management_intelligence()

    yesterday_commands = {
        "yesterday sales",
        "yesterdays sales",
        "yesterday sale",
    }

    # =====================================================
    # CAPABILITY 1: YESTERDAY SALES
    # STABLE EXISTING COMMAND
    # =====================================================

    if normalized_lower in yesterday_commands:
        return _run_yesterday_sales()

    # Natural-language equivalents such as:
    # - What were yesterday's sales?
    # - How was business yesterday?
    # - Kal ka dhandha?
    # - typo / paraphrase variants understood by the RAL parser
    # are semantically routed to the SAME morning report.
    # Requests with dimensions/filters are intentionally not
    # intercepted and continue to the analytical RAL pipeline.
    yesterday_semantic_response = (
        _try_yesterday_morning_report_semantic(
            user_message=normalized_message
        )
    )

    if yesterday_semantic_response is not None:
        return yesterday_semantic_response

    # =====================================================
    # CAPABILITY 2: SALES FOR A PERIOD
    # STABLE EXISTING COMMAND
    # =====================================================

    sales_period_match = (
        SALES_PERIOD_PATTERN.match(
            normalized_message
        )
    )

    if sales_period_match:
        start_date_text = (
            sales_period_match.group(1)
        )

        end_date_text = (
            sales_period_match.group(2)
        )

        data = load_auberry_workbook()

        try:
            report = (
                get_store_performance_report(
                    data=data,
                    start_date_text=(
                        start_date_text
                    ),
                    end_date_text=(
                        end_date_text
                    ),
                )
            )

            image_result = (
                generate_sales_for_a_period_image(
                    report
                )
            )

        except ValueError as error:
            return _build_text_response(
                str(error)
            )

        except Exception as error:
            print(
                "Sales-for-period report error:",
                repr(error),
            )

            return _build_text_response(
                "The sales report could not be generated. "
                "Please try again."
            )

        start_date_display = _display_date(
            start_date_text
        )

        end_date_display = _display_date(
            end_date_text
        )

        return {
            "response_type": "media",
            "body": (
                "📊 Sales Performance\n"
                f"{start_date_display} to "
                f"{end_date_display}"
            ),
            "relative_media_url": (
                image_result[
                    "relative_url"
                ]
            ),
        }

    # =====================================================
    # CAPABILITY 3: KPI PERIOD COMPARISON
    # STABLE EXISTING COMMAND
    # =====================================================

    comparison_match = (
        COMPARISON_PATTERN.match(
            normalized_message
        )
    )

    if comparison_match:
        from_start_date_text = (
            comparison_match.group(1)
        )

        from_end_date_text = (
            comparison_match.group(2)
        )

        to_start_date_text = (
            comparison_match.group(3)
        )

        to_end_date_text = (
            comparison_match.group(4)
        )

        data = load_auberry_workbook()

        try:
            report = (
                get_kpi_period_comparison_report(
                    data=data,
                    from_start_date_text=(
                        from_start_date_text
                    ),
                    from_end_date_text=(
                        from_end_date_text
                    ),
                    to_start_date_text=(
                        to_start_date_text
                    ),
                    to_end_date_text=(
                        to_end_date_text
                    ),
                )
            )

            image_result = (
                generate_kpi_period_comparison_image(
                    report
                )
            )

        except ValueError as error:
            return _build_text_response(
                str(error)
            )

        except Exception as error:
            print(
                "KPI comparison report error:",
                repr(error),
            )

            return _build_text_response(
                "The comparison report could not "
                "be generated. Please try again."
            )

        from_start_display = _display_date(
            from_start_date_text
        )

        from_end_display = _display_date(
            from_end_date_text
        )

        to_start_display = _display_date(
            to_start_date_text
        )

        to_end_display = _display_date(
            to_end_date_text
        )

        return {
            "response_type": "media",
            "body": (
                "📊 Store Performance Comparison\n"
                f"{from_start_display} to "
                f"{from_end_display}\n"
                "vs\n"
                f"{to_start_display} to "
                f"{to_end_display}"
            ),
            "relative_media_url": (
                image_result[
                    "relative_url"
                ]
            ),
        }

    # =====================================================
    # SELECTION / EXTREME CAPABILITY
    # =====================================================

    selection_response = (
        _try_selection_execution(
            user_message=normalized_message
        )
    )

    if selection_response is not None:
        return _finalize_conversation_response(
            response=selection_response,
            conversation_id=conversation_id,
            original_incoming_message=(
                original_incoming_message
            ),
            was_followup=was_followup,
        )

    # =====================================================
    # GENERIC RAL EXECUTION
    # =====================================================

    generic_response = (
        _try_generic_ral_execution(
            user_message=normalized_message
        )
    )

    if generic_response is not None:
        return _finalize_conversation_response(
            response=generic_response,
            conversation_id=conversation_id,
            original_incoming_message=(
                original_incoming_message
            ),
            was_followup=was_followup,
        )

    # =====================================================
    # INVALID FIXED-COMMAND GUIDANCE
    # =====================================================

    if normalized_lower.startswith(
        "compare"
    ):
        return _build_text_response(
            "This comparison could not yet be executed.\n\n"
            "For the existing comparison report, use:\n\n"
            "Compare DD-Mmm-YYYY DD-Mmm-YYYY "
            "DD-Mmm-YYYY DD-Mmm-YYYY\n\n"
            "Example:\n"
            "Compare 01-Apr-2025 30-Jun-2025 "
            "01-Apr-2026 30-Jun-2026"
        )

    if normalized_lower.startswith(
        "sales from"
    ):
        return _build_text_response(
            "Please use the sales-period command "
            "in this format:\n\n"
            "Sales from DD-Mmm-YYYY "
            "to DD-Mmm-YYYY\n\n"
            "Example:\n"
            "Sales from 01-Jul-2026 "
            "to 14-Jul-2026"
        )

    # =====================================================
    # CURRENTLY UNSUPPORTED REQUEST
    # =====================================================

    return _build_text_response(
        "Sorry, I’m unable to answer this question with my current capabilities."
    )