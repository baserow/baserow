import time
from typing import Callable, Optional

from django.conf import settings

import requests
from requests import exceptions as request_exceptions
from urllib3.exceptions import DecodeError, ProtocolError, ReadTimeoutError

import advocate
from baserow.core.services.exceptions import ResponseTooLargeDispatchException


def get_http_request_function() -> Callable:
    """
    Return the appropriate request function based on production environment
    or settings.
    In production mode, the advocate library is used so that the internal
    network can't be reached. This can be disabled by changing the Django
    setting INTEGRATIONS_ALLOW_PRIVATE_ADDRESS.
    """

    if settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS is True:
        return requests.request
    else:
        return advocate.request


def read_response_within_limit(
    response, timeout: int, deadline: Optional[float] = None
) -> None:
    """
    Pulls the body in with a ceiling on its size and a deadline on how long it
    may take, and hangs up on an endpoint that goes past either.

    Buffering it whole and measuring afterwards is too late: the memory is
    already spent. The size ceiling is on what arrives after decompression, so
    a small answer that unpacks into a big one is caught. The deadline is wall
    clock, unlike the timeout Requests applies, which only starts again on
    every byte: a server sending one every few seconds would otherwise hold
    the dispatch open for as long as it liked, past the lock that guards the
    row.

    :param response: The streamed response.
    :param timeout: How long the whole body may take to arrive, in seconds,
        counted from now. Ignored when `deadline` is given.
    :param deadline: The `time.monotonic()` value the body must have arrived
        by, when the caller's budget started earlier than the body did.
    :raises ResponseTooLargeDispatchException: When the body is larger than the
        ceiling.
    :raises requests.exceptions.Timeout: When it takes longer than the
        deadline, or a single read times out, which the caller answers the same
        way as any other timeout.
    """

    # Read whatever the ceiling is set to. Returning early with the ceiling
    # off would leave the body unread under `stream=True`, so `response.json()`
    # would pull it in later, outside the block that maps a truncated or
    # corrupt answer onto a message the caller can use, and the deadline below
    # would never be armed either.
    max_bytes = settings.INTEGRATIONS_HTTP_MAX_RESPONSE_BYTES or None
    if deadline is None:
        deadline = time.monotonic() + timeout

    content = bytearray()

    try:
        while True:
            try:
                # `read1` hands back whatever has arrived. `iter_content` waits
                # inside urllib3 for a whole chunk, so a server sending a byte
                # at a time never let it return and the deadline below was
                # never looked at. Reading `raw` skips the translation
                # `iter_content` does, so its errors are translated here.
                chunk = response.raw.read1(64 * 1024, decode_content=True)
            except ReadTimeoutError as e:
                raise request_exceptions.Timeout(e) from e
            except ProtocolError as e:
                raise request_exceptions.ConnectionError(e) from e
            except DecodeError as e:
                raise request_exceptions.ContentDecodingError(e) from e
            if not chunk:
                break
            content += chunk
            if max_bytes is not None and len(content) > max_bytes:
                raise ResponseTooLargeDispatchException(
                    f"The response is larger than the {max_bytes} bytes this "
                    f"installation accepts."
                )
            if time.monotonic() > deadline:
                raise request_exceptions.Timeout(
                    "The response body did not arrive in time."
                )
    finally:
        response.close()

    # What `response.json()` and `response.text` read, so the rest of the
    # dispatch is unchanged.
    response._content = bytes(content)
    response._content_consumed = True
