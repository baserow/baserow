from contextlib import contextmanager

from django.contrib.auth.models import AbstractUser

from baserow.api.sessions import (
    get_client_undo_redo_action_group_id,
    get_untrusted_client_session_id,
    set_client_undo_redo_action_group_id,
    set_untrusted_client_session_id,
)


@contextmanager
def without_undo_redo_registration(user: AbstractUser):
    """
    Runs undoable actions without them entering the user's undo stack.

    Actions are still registered and still send `action_done`, so row history,
    the audit log, webhooks and realtime updates behave normally. Only the
    session id is cleared, and `ActionHandler.undo`/`redo` select on it, so
    these actions can never be picked up.

    :param user: The user whose session id should be suppressed for the block.
    """

    previous_session_id = get_untrusted_client_session_id(user)
    previous_action_group_id = get_client_undo_redo_action_group_id(user)
    set_untrusted_client_session_id(user, None)
    set_client_undo_redo_action_group_id(user, None)
    try:
        yield
    finally:
        set_untrusted_client_session_id(user, previous_session_id)
        set_client_undo_redo_action_group_id(user, previous_action_group_id)
