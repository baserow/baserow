from contextlib import contextmanager
from typing import Any, Iterator, Sequence

import sentry_sdk
from sentry_sdk.integrations import Integration
from sentry_sdk.transport import Transport

TEST_SENTRY_DSN = "https://public@example.invalid/1"


class CollectingSentryTransport(Transport):
    """Keeps the events Sentry would send instead of sending them."""

    def __init__(self, options=None):
        super().__init__(options)
        self.events: list[dict[str, Any]] = []

    def capture_envelope(self, envelope):
        self.events.extend(
            item.payload.json for item in envelope.items if item.type == "event"
        )


@contextmanager
def collect_sentry_events(
    integrations: Sequence[Integration] = (),
) -> Iterator[list[dict[str, Any]]]:
    """
    Sends the Sentry events captured inside the block to the returned list instead
    of to Sentry. Set `settings.SENTRY_DSN` too for code that checks it.

    :param integrations: The Sentry integrations to enable, none by default.
    """

    transport = CollectingSentryTransport()
    client = sentry_sdk.Client(
        dsn=TEST_SENTRY_DSN,
        transport=transport,
        default_integrations=False,
        integrations=list(integrations),
    )
    try:
        with sentry_sdk.isolation_scope() as scope:
            scope.set_client(client)
            yield transport.events
    finally:
        client.close()


def sent_exception_types(events: list[dict[str, Any]]) -> list[str]:
    """The type of the exception of each collected Sentry event."""

    return [event["exception"]["values"][-1]["type"] for event in events]


def make_openai_error(status_code: int = 429, message: str = "Provider error"):
    """
    Builds the error the OpenAI SDK raises for a response with this status, like
    `RateLimitError` for a 429.

    :param status_code: The status the provider answered with.
    :param message: The error message.
    """

    import httpx
    import openai

    error_class = {
        400: openai.BadRequestError,
        401: openai.AuthenticationError,
        403: openai.PermissionDeniedError,
        404: openai.NotFoundError,
        409: openai.ConflictError,
        422: openai.UnprocessableEntityError,
        429: openai.RateLimitError,
    }.get(
        status_code,
        openai.InternalServerError if status_code >= 500 else openai.APIStatusError,
    )
    request = httpx.Request("POST", "https://api.openai.com/v1/responses")
    return error_class(
        message, response=httpx.Response(status_code, request=request), body=None
    )


def make_openai_connection_error(
    url: str = "https://api.openai.com/v1/responses",
):
    """Builds the error the OpenAI SDK raises when the provider can't be reached."""

    import httpx
    import openai

    return openai.APIConnectionError(request=httpx.Request("POST", url))


def make_openai_stream_error(code: str | int | None, error_type: str | None = None):
    """
    Builds the error the OpenAI SDK raises for an error object inside a streamed
    answer, after the provider answered with a 200, so without a status.

    :param code: The code of the error object.
    :param error_type: The type of the error object.
    """

    import httpx2
    import openai

    return openai.APIError(
        "Stream failed",
        request=httpx2.Request("POST", "https://api.openai.com/v1/chat/completions"),
        body={"code": code, "type": error_type, "message": "Stream failed"},
    )


def raised_from(error: BaseException, cause: BaseException) -> BaseException:
    """Raises `error` from `cause`, like `raise error from cause`, and returns it."""

    try:
        raise error from cause
    except BaseException as exc:
        return exc
