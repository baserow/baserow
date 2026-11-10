"""
This module handles the storage of request-specific variables, particularly:

* workspace_id: Represents the ID of the current workspace related to the request.
    This ID can be utilized by storage backends to generate URLs specific to the
    workspace.
* private_link_token: The token of the private link of a user template that the
    request was made with. While a user has a template open through its private
    link, the frontend sends the token in a header with every request, so that the
    template, its content, its install and its download are allowed by the token
    itself, without anything stored for the user.
"""

import re
from contextlib import contextmanager
from contextvars import ContextVar
from typing import Iterator, Optional

from asgiref.local import Local

_thread_locals = Local()


def get_current_workspace_id():
    return getattr(_thread_locals, "workspace_id", None)


def set_current_workspace_id(workspace_id):
    # FIXME: Temporarily setting the current workspace ID for URL generation in
    # storage backends, enabling permission checks at download time.
    _thread_locals.workspace_id = workspace_id


def clear_current_workspace_id():
    _thread_locals.workspace_id = None


PRIVATE_LINK_TOKEN_PATTERN = r"\A[0-9a-f]{64}\Z"
_PRIVATE_LINK_TOKEN_RE = re.compile(PRIVATE_LINK_TOKEN_PATTERN)

_private_link_token: ContextVar[Optional[str]] = ContextVar(
    "template_private_link_token", default=None
)


def get_private_link_token() -> Optional[str]:
    """
    The token of the private link the current request was made with. None without
    one, and outside a request unless set with `private_link_token()`.
    """

    return _private_link_token.get()


@contextmanager
def private_link_token(token: Optional[str]) -> Iterator[None]:
    """
    Makes `token` the token of the private link of the code run in the block. A
    token that can't be the one of a link is ignored, like no token.

    :param token: The token sent with the request, if any.
    """

    if token is not None and not _PRIVATE_LINK_TOKEN_RE.match(token):
        token = None
    reset_token = _private_link_token.set(token)
    try:
        yield
    finally:
        _private_link_token.reset(reset_token)
