from contextlib import asynccontextmanager
from datetime import date
import os

from fastapi import BackgroundTasks, FastAPI, Form, Header, HTTPException, Request
from fastapi.responses import FileResponse, PlainTextResponse
from fastapi.staticfiles import StaticFiles
from twilio.rest import Client
from twilio.twiml.messaging_response import MessagingResponse

from services.core.data_loader import load_auberry_workbook
from services.presentation.formatter import format_yesterday_sales_report
from services.reports.kpi_comparison.report import (
    get_kpi_period_comparison_report,
)
from services.reports.kpi_comparison.image import (
    generate_kpi_period_comparison_image,
)
from services.routing.message_router import route_message
import services.semantics.vocabulary.metrics as metrics
from services.reports.sales_period.report import (
    get_store_performance_report,
)
from services.reports.sales_period.image import (
    generate_sales_for_a_period_image,
)
from services.reports.yesterday.legacy_report import (
    get_yesterday_sales_report,
)
from services.semantics.builders.store_builder import (
    build_store_dictionary,
)
from services.intelligence.intelligence_orchestrator import (
    build_management_message,
)

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(
        "Loading Auberry workbook into memory..."
    )

    data = load_auberry_workbook()

    print(
        "Workbook loaded successfully:",
        f"{len(data['sales'])} sales rows",
    )

    yield


app = FastAPI(
    lifespan=lifespan
)


app.mount(
    "/static",
    StaticFiles(
        directory="static"
    ),
    name="static",
)


# =========================================================
# APPLICATION STATUS
# =========================================================


@app.get("/")
def home():
    return {
        "status": "running",
        "application": "RestaurantAI_Cloud",
    }


@app.get("/test-data")
def test_data():
    data = load_auberry_workbook()

    return {
        "sales_rows": len(
            data["sales"]
        ),
        "store_rows": len(
            data["store_info"]
        ),
        "category_rows": len(
            data["item_category"]
        ),
    }


# =========================================================
# CAPABILITY 1: YESTERDAY SALES
# =========================================================


@app.get("/yesterday")
def yesterday_sales():
    data = load_auberry_workbook()

    return get_yesterday_sales_report(
        data
    )


@app.get(
    "/yesterday-message",
    response_class=PlainTextResponse,
)
def yesterday_sales_message():
    data = load_auberry_workbook()

    report = get_yesterday_sales_report(
        data
    )

    return format_yesterday_sales_report(
        report
    )


# =========================================================
# CAPABILITY 2: SALES FOR A PERIOD
# =========================================================


@app.get("/sales-for-a-period-image")
def sales_for_a_period_image(
    start_date: str = "01-Apr-2026",
    end_date: str = "30-Apr-2026",
):
    data = load_auberry_workbook()

    report = get_store_performance_report(
        data=data,
        start_date_text=start_date,
        end_date_text=end_date,
    )

    image_result = (
        generate_sales_for_a_period_image(
            report
        )
    )

    return FileResponse(
        path=image_result["file_path"],
        media_type="image/png",
    )


# =========================================================
# CAPABILITY 3: KPI PERIOD COMPARISON
# =========================================================


@app.get("/compare-test")
def compare_test():
    data = load_auberry_workbook()

    report = (
        get_kpi_period_comparison_report(
            data=data,
            from_start_date_text=(
                "01-Apr-2025"
            ),
            from_end_date_text=(
                "30-Jun-2025"
            ),
            to_start_date_text=(
                "01-Apr-2026"
            ),
            to_end_date_text=(
                "30-Jun-2026"
            ),
        )
    )

    return report


@app.get("/compare-image-test")
def compare_image_test():
    data = load_auberry_workbook()

    report = (
        get_kpi_period_comparison_report(
            data=data,
            from_start_date_text=(
                "01-Apr-2025"
            ),
            from_end_date_text=(
                "30-Jun-2025"
            ),
            to_start_date_text=(
                "01-Apr-2026"
            ),
            to_end_date_text=(
                "30-Jun-2026"
            ),
        )
    )

    image_result = (
        generate_kpi_period_comparison_image(
            report
        )
    )

    return FileResponse(
        path=image_result["file_path"],
        media_type="image/png",
    )


# =========================================================
# GPT CONNECTION TEST
# =========================================================


@app.get("/llm-test")
def llm_test():
    """
    Test basic OpenAI connectivity without involving:

    - WhatsApp
    - message routing
    - sales calculations
    - report generation
    """
    try:
        from services.core.llm_service import (
            llm_service,
        )

        response_text = (
            llm_service.test_connection()
        )

        return {
            "status": "success",
            "response": response_text,
        }

    except Exception as error:
        print(
            "LLM connection test error:",
            repr(error),
        )

        return {
            "status": "error",
            "error_type": type(
                error
            ).__name__,
            "message": str(
                error
            ),
        }


# =========================================================
# GPT INTENT TEST
# =========================================================


@app.get("/intent-test")
def intent_test(
    message: str = (
        "How did we perform yesterday?"
    ),
):
    """
    Test RestaurantAI's natural-language intent parser.

    This endpoint only performs:

        User message
            ↓
        GPT intent extraction
            ↓
        Structured JSON

    It does not:

    - run a business engine,
    - read sales data,
    - generate a report,
    - change WhatsApp routing.
    """
    try:
        from services.semantics.intent_parser import (
            parse_intent,
        )

        intent_result = parse_intent(
            user_message=message
        )

        return {
            "status": "success",
            "input_message": message,
            "intent": intent_result,
        }

    except Exception as error:
        print(
            "Intent parser test error:",
            repr(error),
        )

        return {
            "status": "error",
            "input_message": message,
            "error_type": type(
                error
            ).__name__,
            "message": str(
                error
            ),
        }


@app.get("/ral-test")
def ral_test(
    message: str = "How did we perform yesterday?",
):
    """
    Shows the complete RestaurantAI Language (RAL)
    generated by GPT before any routing occurs.
    """
    try:
        from services.semantics.intent_parser import (
            parse_ral_request,
        )

        ral_request = parse_ral_request(
            message
        )

        return {
            "status": "success",
            "input_message": message,
            "ral": ral_request,
        }

    except Exception as error:
        return {
            "status": "error",
            "error_type": type(error).__name__,
            "message": str(error),
        }



# =========================================================
# V2 SEMANTIC PLANNER TEST BENCH
# =========================================================


@app.get("/v2/semantic-test")
def v2_semantic_test(
    message: str,
    conversation_id: str | None = None,
    remember: bool = False,
):
    """
    Inspect only RestaurantAI V2 semantic understanding.

    This endpoint deliberately does NOT:
    - execute analytics,
    - calculate business numbers,
    - route through WhatsApp,
    - choose a legacy capability.

    It exposes the generic five-factor BusinessQuery:
        Time × Store × Channel × KPI × Operation
    plus context relation, comparison, grouping and presentation intent.

    conversation_id is optional. When supplied, the current analytical
    state for that id is made available to the planner. Set remember=true
    to store the successfully parsed query as the next analytical context.
    """
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
        user_message=message,
        previous_query=previous_query,
    )

    if (
        remember
        and conversation_id
        and not business_query.get(
            "needs_clarification",
            False,
        )
    ):
        set_conversation_query(
            conversation_id,
            business_query,
        )

    return {
        "status": "success",
        "input_message": message,
        "conversation_id": conversation_id,
        "remembered": bool(
            remember and conversation_id
        ),
        "previous_query": previous_query,
        "business_query": business_query,
    }


@app.post("/v2/semantic-reset")
def v2_semantic_reset(
    conversation_id: str,
):
    """Clear one V2 analytical conversation state for test purposes."""
    from services.semantics.conversation_state import (
        clear_conversation_query,
    )

    clear_conversation_query(
        conversation_id
    )

    return {
        "status": "cleared",
        "conversation_id": conversation_id,
    }


# =========================================================
# V2 BUSINESS QUERY EXECUTION TEST
# =========================================================


@app.get("/v2/execute-test", response_class=PlainTextResponse)
def v2_execute_test(message: str):
    from services.analytics.business_query_engine import execute_business_query
    from services.presentation.business_query_presenter import present_business_query
    from services.semantics.business_query_parser import parse_business_query
    try:
        q=parse_business_query(user_message=message, previous_query=None)
        if q.get("needs_clarification", False):
            return q.get("clarification_question","I need a little more information.")
        result=execute_business_query(data=load_auberry_workbook(), query=q)
        p=present_business_query(query=q, result=result)
        if isinstance(p,str): return p
        if isinstance(p,dict):
            return p.get("body") or p.get("text") or p.get("message") or str(p)
        return str(p)
    except Exception as error:
        print("V2 execution test error:",repr(error))
        return f"RestaurantAI execution error: {type(error).__name__}: {error}"


# =========================================================
# MANAGEMENT INTELLIGENCE MESSAGE TEST
# =========================================================


@app.get(
    "/intelligence/management-message-test",
    response_class=PlainTextResponse,
)
def management_message_test(
    as_of_date: date = date(2026, 8, 12),
):
    """
    Return the management intelligence message as plain text.

    This is a test endpoint only. It does not send WhatsApp messages
    and does not modify the existing WhatsApp or scheduled-report flow.
    """
    return build_management_message(
        as_of_date
    )


# =========================================================
# WHATSAPP
# =========================================================


def _get_twilio_client() -> Client:
    """
    Build the Twilio REST client from environment variables.
    """
    account_sid = os.getenv(
        "TWILIO_ACCOUNT_SID"
    )
    auth_token = os.getenv(
        "TWILIO_AUTH_TOKEN"
    )

    if not account_sid:
        raise ValueError(
            "TWILIO_ACCOUNT_SID environment variable is not configured."
        )

    if not auth_token:
        raise ValueError(
            "TWILIO_AUTH_TOKEN environment variable is not configured."
        )

    return Client(
        account_sid,
        auth_token,
    )


def _send_routed_response_via_twilio(
    routed_response: dict,
    to_number: str,
    from_number: str,
    base_url: str,
) -> str:
    """
    Send one already-generated RestaurantAI response through
    Twilio's REST API.

    This helper is reused by:
    - normal inbound WhatsApp requests after async processing,
    - scheduled outbound reports.
    """
    client = _get_twilio_client()

    message_kwargs = {
        "body": routed_response["body"],
        "from_": from_number,
        "to": to_number,
    }

    if (
        routed_response["response_type"]
        == "media"
    ):
        relative_media_url = (
            routed_response[
                "relative_media_url"
            ]
        )

        public_media_url = (
            f"{base_url.rstrip('/')}"
            f"{relative_media_url}"
        )

        message_kwargs[
            "media_url"
        ] = [
            public_media_url
        ]

        print(
            "Sending WhatsApp media URL:",
            public_media_url,
        )

    sent_message = client.messages.create(
        **message_kwargs
    )

    print(
        "WhatsApp reply sent:",
        sent_message.sid,
    )

    return str(
        sent_message.sid
    )


def _send_whatsapp_reply_in_background(
    body: str,
    from_number: str,
    to_number: str,
    base_url: str,
) -> None:
    """
    Run every inbound WhatsApp message through the single RestaurantAI
    message router, then deliver exactly the response type chosen there.

    This is intentionally the same path used by the rest of the product.
    The router owns:
    - preservation of the established V2 Yesterday morning report,
    - semantic BusinessQuery execution,
    - comparison judgement,
    - trend/chart routing,
    - text vs image/media presentation,
    - legacy/product fallbacks.

    Keeping analytics/presentation logic out of this transport function
    prevents WhatsApp from bypassing product routing rules.
    """
    try:
        routed_response = route_message(
            message=body,
            conversation_id=from_number,
        )

        if not isinstance(routed_response, dict):
            routed_response = {
                "response_type": "text",
                "body": str(routed_response),
            }

        response_type = str(
            routed_response.get("response_type", "text")
        ).strip().lower()

        # Never expose internal router/presenter dictionaries to WhatsApp.
        if response_type not in {"text", "media"}:
            raise ValueError(
                f"Unsupported RestaurantAI response type: {response_type}"
            )

        if not routed_response.get("body"):
            raise ValueError(
                "RestaurantAI router returned an empty WhatsApp response."
            )

        if response_type == "media" and not routed_response.get(
            "relative_media_url"
        ):
            raise ValueError(
                "RestaurantAI media response is missing relative_media_url."
            )

        _send_routed_response_via_twilio(
            routed_response=routed_response,
            to_number=from_number,
            from_number=to_number,
            base_url=base_url,
        )

    except Exception as error:
        print(
            "Async V3 WhatsApp reply error:",
            repr(error),
        )

        # A routing failure must produce a user-safe message, never a Python
        # dict such as {'status': 'fallback'}.
        try:
            _send_routed_response_via_twilio(
                routed_response={
                    "response_type": "text",
                    "body": (
                        "I could not complete that analysis reliably. "
                        "Please try the request once more."
                    ),
                },
                to_number=from_number,
                from_number=to_number,
                base_url=base_url,
            )
        except Exception as send_error:
            print(
                "Async V3 WhatsApp error-message send failed:",
                repr(send_error),
            )


@app.post("/whatsapp")
async def whatsapp(
    request: Request,
    background_tasks: BackgroundTasks,
    Body: str = Form(...),
    From: str = Form(...),
    To: str = Form(...),
):
    """
    Acknowledge Twilio immediately, then process RestaurantAI
    in the background and send the final reply through Twilio's
    REST API.

    Twilio should never wait for GPT/RAL/analytics execution.
    """
    base_url = str(
        request.base_url
    ).rstrip("/")

    background_tasks.add_task(
        _send_whatsapp_reply_in_background,
        Body,
        From,
        To,
        base_url,
    )

    response = MessagingResponse()

    return PlainTextResponse(
        content=str(response),
        media_type="application/xml",
    )


# =========================================================
# SCHEDULED MORNING REPORT
# =========================================================


@app.post("/internal/send-yesterday-report")
def send_scheduled_yesterday_report(
    request: Request,
    x_scheduler_token: str | None = Header(
        default=None,
        alias="X-Scheduler-Token",
    ),
):
    """
    Generate and send the existing Yesterday Sales management
    report without requiring an inbound WhatsApp message.

    This endpoint is intended to be called only by the Railway
    cron trigger. It is protected by SCHEDULER_SECRET.

    MORNING_REPORT_TO may contain one or multiple WhatsApp
    numbers separated by commas. Each recipient is processed
    independently.
    """
    expected_token = os.getenv("SCHEDULER_SECRET")

    if not expected_token:
        raise HTTPException(
            status_code=503,
            detail=(
                "SCHEDULER_SECRET environment variable "
                "is not configured."
            ),
        )

    if (
        not x_scheduler_token
        or x_scheduler_token != expected_token
    ):
        raise HTTPException(
            status_code=401,
            detail="Invalid scheduler token.",
        )

    recipients_raw = os.getenv("MORNING_REPORT_TO")
    sender = os.getenv("TWILIO_WHATSAPP_FROM")

    if not recipients_raw:
        raise HTTPException(
            status_code=503,
            detail=(
                "MORNING_REPORT_TO environment variable "
                "is not configured."
            ),
        )

    if not sender:
        raise HTTPException(
            status_code=503,
            detail=(
                "TWILIO_WHATSAPP_FROM environment variable "
                "is not configured."
            ),
        )

    recipients = [
        number.strip()
        for number in recipients_raw.split(",")
        if number.strip()
    ]

    if not recipients:
        raise HTTPException(
            status_code=503,
            detail=(
                "MORNING_REPORT_TO does not contain "
                "any valid recipients."
            ),
        )

    public_base_url = (
        os.getenv("PUBLIC_BASE_URL")
        or str(request.base_url).rstrip("/")
    )

    routed_response = route_message("Yesterday sales")

    successful = []
    failed = []

    for recipient in recipients:
        try:
            message_sid = _send_routed_response_via_twilio(
                routed_response=routed_response,
                to_number=recipient,
                from_number=sender,
                base_url=public_base_url,
            )

            successful.append(
                {
                    "recipient": recipient,
                    "message_sid": message_sid,
                }
            )

            print(
                "Scheduled Yesterday Sales sent:",
                recipient,
                message_sid,
            )

        except Exception as error:
            failed.append(
                {
                    "recipient": recipient,
                    "error": str(error),
                }
            )

            print(
                "Scheduled Yesterday Sales failed:",
                recipient,
                repr(error),
            )

    return {
        "status": (
            "sent"
            if not failed
            else (
                "partial_success"
                if successful
                else "failed"
            )
        ),
        "report": "Yesterday sales",
        "recipient_count": len(recipients),
        "successful_count": len(successful),
        "failed_count": len(failed),
        "successful": successful,
        "failed": failed,
    }


@app.get("/store-builder-test")
def store_builder_test():

    data = load_auberry_workbook()

    store_dictionary = (
        build_store_dictionary(data)
    )

    return store_dictionary

@app.get("/channel-builder-test")
def channel_builder_test():
    """
    Test the client-specific restaurant channel hierarchy.

    This endpoint only:

    - loads the active client's workbook,
    - builds the channel dictionary,
    - returns the resulting hierarchy.

    It does not:

    - calculate sales,
    - call GPT,
    - modify WhatsApp routing,
    - execute any business report.
    """
    from services.semantics.builders.channel_builder import (
        build_channel_dictionary,
    )

    data = load_auberry_workbook()

    channel_dictionary = (
        build_channel_dictionary(
            data=data
        )
    )

    return channel_dictionary

@app.get("/product-builder-test")
def product_builder_test():
    """
    Test the active client's Category–Item hierarchy.

    This endpoint only:

    - loads the Auberry workbook,
    - builds the product dictionary,
    - returns categories and their mapped items.

    It does not:

    - call GPT,
    - calculate sales or quantity,
    - modify WhatsApp routing,
    - execute any report.
    """
    from services.semantics.builders.product_builder import (
        build_product_dictionary,
    )

    data = load_auberry_workbook()

    product_dictionary = (
        build_product_dictionary(
            data=data
        )
    )

    return product_dictionary

@app.get("/sales-columns-test")
def sales_columns_test():
    """
    Show the exact sales columns required before building
    the generic RAL execution engine.
    """
    data = load_auberry_workbook()

    sales = data["sales"]

    return {
        "columns": sales.columns.tolist(),
    }

@app.get("/ral-filter-test")
def ral_filter_test(
    message: str = (
        "How many cupcakes were sold last month "
        "at AMB Mall?"
    ),
):
    """
    Test the complete RestaurantAI execution flow.

    Natural Language
        ↓
    RAL
        ↓
    Deterministic Filters
        ↓
    Metric Calculation
    """
    import services.semantics.vocabulary.metrics as metrics

    print("=" * 80)
    print("METRICS FILE LOADED FROM:")
    print(metrics.__file__)
    print("=" * 80)

    print("HAS calculate_metric ?")
    print(hasattr(metrics, "calculate_metric"))

    print("AVAILABLE NAMES:")
    print([x for x in dir(metrics) if x.startswith("calculate")])
    print("=" * 80)

    from services.analytics.filter_engine import (
        apply_ral_filters,
    )
    from services.semantics.intent_parser import (
        parse_ral_request,
    )

    data = load_auberry_workbook()

    ral_request = parse_ral_request(
        user_message=message
    )

    filtered_sales = apply_ral_filters(
        data=data,
        ral_request=ral_request,
    )

    metric_value = metrics.calculate_metric(
        metric_name=ral_request["metric"],
        filtered_df=filtered_sales,
    )

    return {
        "ral": ral_request,
        "matching_rows": len(
            filtered_sales
        ),
        "metric_name": ral_request["metric"],
        "metric_value": metric_value,
        "sample_rows": (
            filtered_sales[
                [
                    "Date",
                    "Restaurant",
                    "Area",
                    "Item Name",
                    "Category",
                    "Qty",
                    "Sub Total",
                ]
            ]
            .head(10)
            .to_dict(
                orient="records"
            )
        ),
    }

@app.get("/metrics-debug")
def metrics_debug():

    import services.semantics.vocabulary.metrics as metrics

    return {
        "module_file": metrics.__file__,
        "has_calculate_metric": hasattr(
            metrics,
            "calculate_metric",
        ),
        "calculate_functions": [
            name
            for name in dir(metrics)
            if name.startswith("calculate")
        ],
    }

@app.get("/ral-group-test")
def ral_group_test(
    message: str = (
        "Store-wise sales last month"
    ),
):
    """
    Test the complete RestaurantAI grouped execution flow.

    Natural Language
        ↓
    RAL
        ↓
    Deterministic Filters
        ↓
    Grouping Engine
        ↓
    Metric Calculation per Group
    """
    from services.analytics.filter_engine import (
        apply_ral_filters,
    )
    from services.analytics.grouping_engine import (
        calculate_grouped_metric,
    )
    from services.semantics.intent_parser import (
        parse_ral_request,
    )

    data = load_auberry_workbook()

    ral_request = parse_ral_request(
        user_message=message
    )

    filtered_sales = apply_ral_filters(
        data=data,
        ral_request=ral_request,
    )

    grouped_result = calculate_grouped_metric(
        filtered_sales=filtered_sales,
        data=data,
        ral_request=ral_request,
    )

    return {
        "ral": ral_request,
        "filtered_rows": len(
            filtered_sales
        ),
        "grouped_result": (
            grouped_result
        ),
    }

@app.get("/ral-trend-test")
def ral_trend_test(
    message: str = (
        "Daily sales trend this month"
    ),
):
    """
    Test the complete RestaurantAI trend execution flow.

    Natural Language
        ↓
    RAL
        ↓
    Deterministic Filters
        ↓
    Trend Engine
        ↓
    Optional Grouping
        ↓
    Metric Engine
    """
    from services.analytics.filter_engine import (
        apply_ral_filters,
    )
    from services.semantics.intent_parser import (
        parse_ral_request,
    )
    from services.analytics.trend_engine import (
        calculate_trend,
    )

    data = load_auberry_workbook()

    ral_request = parse_ral_request(
        user_message=message
    )

    filtered_sales = apply_ral_filters(
        data=data,
        ral_request=ral_request,
    )

    trend_result = calculate_trend(
        filtered_sales=filtered_sales,
        data=data,
        ral_request=ral_request,
    )

    return {
        "ral": ral_request,

        "filtered_rows": len(
            filtered_sales
        ),

        "trend_result": (
            trend_result
        ),
    }

@app.get("/ral-chart-test")
def ral_chart_test(
    message: str = (
        "Plot daily sales trend this month"
    ),
):
    """
    Test RestaurantAI visual presentation pipeline.

    Supports:

        Trend -> Line Chart

        Grouping -> Bar Chart

        Trend + Grouping -> Chart
    """
    from services.presentation.chart_engine import (
        render_chart,
    )
    from services.analytics.filter_engine import (
        apply_ral_filters,
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
    from services.analytics.trend_engine import (
        calculate_trend,
    )

    data = load_auberry_workbook()

    ral_request = parse_ral_request(
        user_message=message
    )

    filtered_sales = apply_ral_filters(
        data=data,
        ral_request=ral_request,
    )

    # =====================================================
    # TREND
    # =====================================================

    if (
        ral_request[
            "trend"
        ][
            "enabled"
        ]
    ):

        analytics_result = (
            calculate_trend(
                filtered_sales=filtered_sales,
                data=data,
                ral_request=ral_request,
            )
        )

        result_type = "trend"

    # =====================================================
    # GROUPING
    # =====================================================

    elif (
        ral_request[
            "grouping"
        ][
            "enabled"
        ]
    ):

        analytics_result = (
            calculate_grouped_metric(
                filtered_sales=filtered_sales,
                data=data,
                ral_request=ral_request,
            )
        )

        result_type = "grouped"

    else:

        return {
            "status": "unsupported",
            "message": (
                "This chart test currently requires "
                "a grouped or trend request."
            ),
            "ral": ral_request,
        }

    presentation_result = (
        present_result(
            result=analytics_result,
            result_type=result_type,
            ral_request=ral_request,
        )
    )

    if (
        presentation_result[
            "mode"
        ]
        != "chart"
    ):

        return {
            "ral": ral_request,
            "presentation": (
                presentation_result
            ),
        }

    chart_spec = (
        presentation_result[
            "chart_spec"
        ]
    )

    chart_path = (
        render_chart(
            chart_spec=chart_spec,
            file_name=(
                "ral_chart_test.png"
            ),
        )
    )

    return {
        "ral": ral_request,

        "filtered_rows": len(
            filtered_sales
        ),

        "result_type": (
            result_type
        ),

        "analytics_result": (
            analytics_result
        ),

        "chart_spec": (
            chart_spec
        ),

        "chart_file": str(
            chart_path
        ),
    }