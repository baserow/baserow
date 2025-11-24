from copy import deepcopy
from typing import Optional
from uuid import uuid4

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.dispatch import receiver

from loguru import logger

from baserow.core.action.signals import ActionCommandType, action_done
from baserow.core.models import Workspace
from baserow.core.utils import exception_capturer

_posthog = None


def get_posthog_client():
    """
    Returns the Posthog instance configured according to the settings. If Posthog is
    disabled, the instance will have the `disabled` attribute set to True.
    """

    from posthog import Posthog

    global _posthog
    if _posthog is None:
        _posthog = Posthog(
            settings.POSTHOG_PROJECT_API_KEY,
            host=settings.POSTHOG_HOST,
            disabled=not settings.POSTHOG_ENABLED,
        )
    return _posthog


def capture_event(distinct_id: str, event: str, properties: dict):
    """
    Capture a single Posthog event.

    :param distinct_id: The distinct ID of the event.
    :param event: The event type name.
    :param properties: A dictionary containing all properties that must be added to
        the event.
    """

    posthog_client = get_posthog_client()
    if posthog_client.disabled:
        return

    try:
        posthog_client.capture(
            distinct_id=distinct_id,
            event=event,
            properties=properties,
        )
    except Exception as e:
        logger.warning(
            "Failed to log to Posthog because of {e}.",
            e=str(e),
        )
        exception_capturer(e)


def capture_user_event(
    user: AbstractUser,
    event: str,
    properties: dict,
    session: Optional[str] = None,
    workspace: Optional[Workspace] = None,
):
    """
    Captures a Posthog event of a user in a consistent property format.

    :param user: The user that performed the event.
    :param event: Unique name identifying the event.
    :param properties: A dictionary containing the properties that must be added.
        Note that the `user_email`, `user_session`, `workspace_id`,
        and `workspace_name` will be overwritten.
    :param session: A unique session id that identifies the user throughout their
        session.
    :param workspace: Optionally the workspace related to the event.
    """

    if user is None or user.is_anonymous:
        # The user_id cannot be None. It's needed by Posthog to identify the user
        user_id = str(uuid4())
        user_email = None
    else:
        user_id = user.id
        user_email = user.email

    properties["user_email"] = user_email

    if session is not None:
        properties["user_session"] = session

    if workspace is not None:
        properties["workspace_id"] = workspace.id

    capture_event(user_id, event, properties)


@receiver(action_done)
def capture_event_action_done(
    sender,
    user,
    action_type,
    action_params,
    action_timestamp,
    action_command_type,
    workspace,
    session,
    **kwargs,
):
    # Only capture do commands for now because the undo might make it more difficult
    # to do analytics on the data.
    if action_command_type == ActionCommandType.DO:
        action_params_copy = deepcopy(action_params)
        properties = {
            key: action_params_copy.get(key, None)
            for key in action_type.analytics_params
        }
        capture_user_event(
            user, action_type.type, properties, workspace=workspace, session=session
        )
