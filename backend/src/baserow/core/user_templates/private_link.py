"""
The token of the private link of a user template that the current request was made
with. While a user has a template open through its private link, the frontend
sends the token in a header with every request, so that the template, its content,
its install and its download are allowed by the token itself, without anything
stored for the user.
"""

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

_TOKEN_RE = re.compile(r"\A[0-9a-f]{64}\Z")

_private_link_token: ContextVar[Optional[str]] = ContextVar(
    "template_private_link_token", default=None
)


def get_private_link_token() -> Optional[str]:
    """
    The token of the private link the current request was made with. None without
    one, and outside a request, like in a job or a websocket consumer, so that
    those fail closed.
    """

    return _private_link_token.get()


@contextmanager
def private_link_token(token: Optional[str]) -> Iterator[None]:
    """
    Makes `token` the token of the private link of the code run in the block. A
    token that can't be the one of a link is ignored, like no token.

    :param token: The token sent with the request, if any.
    """

    if token is not None and not _TOKEN_RE.match(token):
        token = None
    reset_token = _private_link_token.set(token)
    try:
        yield
    finally:
        _private_link_token.reset(reset_token)
