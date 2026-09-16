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


# Enough for http to https to a canonical host to a locale. The deadline is what
# bounds how long a request takes; this only stops an endless chain early.
MAX_REDIRECTS = 10


class _DeadlineMixin:
    """
    Gives every hop of a request only the time left until one deadline.
    Requests passes the same `timeout` to every hop of a redirect chain, and
    applies it per socket operation, so on its own it bounds neither.
    """

    deadline: float

    def send(self, request, **kwargs):
        remaining = self.deadline - time.monotonic()
        if remaining <= 0:
            raise request_exceptions.Timeout("The request did not finish in time.")
        # `resolve_redirects` calls `send` again for every hop, so each one
        # gets what is left rather than the whole budget.
        kwargs["timeout"] = remaining
        return super().send(request, **kwargs)


class _DeadlineSession(_DeadlineMixin, requests.Session):
    pass


class _DeadlineAdvocateSession(_DeadlineMixin, advocate.Session):
    # Only `send` is overridden, so advocate's validating adapter still checks
    # the address of every hop, redirects included.
    pass


def send_http_request(
    method: str, url: str, deadline: float, **kwargs
) -> requests.Response:
    """
    Sends a request that is over by `deadline`, redirects included, and returns
    the final response with its body still unread.

    The body is left for `read_response_within_limit`, which the caller hands
    the same deadline, so the whole exchange shares one budget.

    :param method: The HTTP method.
    :param url: Where to send it.
    :param deadline: The `time.monotonic()` value the request must be over by.
    :param kwargs: Anything else `requests.Session.request` accepts, except
        `timeout` and `stream`, which this sets.
    :return: The final response, streamed.
    :raises requests.exceptions.Timeout: When the deadline passes.
    :raises requests.exceptions.TooManyRedirects: Past `MAX_REDIRECTS`.
    :raises UnacceptableAddressException: When a hop resolves to an address
        this installation does not allow.
    """

    session_class = (
        _DeadlineSession
        if settings.INTEGRATIONS_ALLOW_PRIVATE_ADDRESS is True
        else _DeadlineAdvocateSession
    )

    def read_redirect_body(response, *args, **hook_kwargs):
        # Requests reads a redirect's body itself before following it, with no
        # deadline and no size ceiling. Hooks run first, so reading it here
        # puts it under both.
        if response.is_redirect:
            read_response_within_limit(response, 0, deadline=deadline)

    # Closed on return, the same as `requests.request` does: that only drops
    # the idle connections in the pool, not the one the response is streaming
    # from.
    with session_class() as session:
        session.deadline = deadline
        session.max_redirects = MAX_REDIRECTS
        return session.request(
            method=method,
            url=url,
            stream=True,
            hooks={"response": [read_redirect_body]},
            **kwargs,
        )
