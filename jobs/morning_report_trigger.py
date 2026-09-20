import os
import sys
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


def main() -> int:
    """
    Lightweight Railway Cron entry point.

    It does NOT generate the report itself. It calls the live
    RestaurantAI web service so the PNG is created on the same
    filesystem that FastAPI exposes at /static/reports.
    """
    public_base_url = os.getenv(
        "PUBLIC_BASE_URL"
    )
    scheduler_secret = os.getenv(
        "SCHEDULER_SECRET"
    )

    if not public_base_url:
        print(
            "PUBLIC_BASE_URL environment variable "
            "is not configured."
        )
        return 1

    if not scheduler_secret:
        print(
            "SCHEDULER_SECRET environment variable "
            "is not configured."
        )
        return 1

    endpoint = (
        f"{public_base_url.rstrip('/')}"
        "/internal/send-yesterday-report"
    )

    request = Request(
        endpoint,
        data=b"",
        method="POST",
        headers={
            "X-Scheduler-Token": (
                scheduler_secret
            ),
            "User-Agent": (
                "RestaurantAI-Railway-Cron/1.0"
            ),
        },
    )

    try:
        with urlopen(
            request,
            timeout=120,
        ) as response:
            response_body = (
                response.read()
                .decode(
                    "utf-8",
                    errors="replace",
                )
            )

            print(
                "Morning report trigger status:",
                response.status,
            )
            print(
                "Morning report trigger response:",
                response_body,
            )

            if 200 <= response.status < 300:
                return 0

            return 1

    except HTTPError as error:
        response_body = (
            error.read()
            .decode(
                "utf-8",
                errors="replace",
            )
        )

        print(
            "Morning report trigger HTTP error:",
            error.code,
        )
        print(
            response_body
        )
        return 1

    except URLError as error:
        print(
            "Morning report trigger network error:",
            repr(error),
        )
        return 1

    except Exception as error:
        print(
            "Morning report trigger error:",
            repr(error),
        )
        return 1


if __name__ == "__main__":
    sys.exit(
        main()
    )
