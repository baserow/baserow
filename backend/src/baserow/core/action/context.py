from contextlib import contextmanager
from typing import Iterator

from django.contrib.auth.models import AbstractUser

from baserow.api.sessions import (
    get_client_undo_redo_action_group_id,
    get_untrusted_client_session_id,
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
)


@contextmanager
def undo_redo_session(
    user: AbstractUser, session_id: str | None, action_group_id: str | None
) -> Iterator[None]:
    """
    Runs undoable actions in the given undo session and action group, like a
    request with those headers, and puts back the previous ones afterwards.

    :param user: The user doing the actions.
    :param session_id: The session that `ActionHandler.undo`/`redo` select on.
    :param action_group_id: The group of actions that are undone together.
    """

    previous_session_id = get_untrusted_client_session_id(user)
    previous_action_group_id = get_client_undo_redo_action_group_id(user)
    set_untrusted_client_session_id(user, session_id)
    set_client_undo_redo_action_group_id(user, action_group_id)
    try:
        yield
    finally:
        set_untrusted_client_session_id(user, previous_session_id)
        set_client_undo_redo_action_group_id(user, previous_action_group_id)


@contextmanager
def without_undo_redo_registration(user: AbstractUser) -> Iterator[None]:
    """
    Runs undoable actions without them entering the user's undo stack.

    Actions are still registered and still send `action_done`, so row history,
    the audit log, webhooks and realtime updates behave normally. Only the
    session id is cleared, and `ActionHandler.undo`/`redo` select on it, so
    these actions can never be picked up.

    :param user: The user whose session id should be suppressed for the block.
    """

    with undo_redo_session(user, None, None):
        yield
