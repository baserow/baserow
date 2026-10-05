import uuid
from typing import Any
from unittest.mock import MagicMock

from django.db import transaction

from baserow.api.sessions import (
    get_client_undo_redo_action_group_id,
    get_untrusted_client_session_id,
    set_client_undo_redo_action_group_id,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow_enterprise.assistant.deps import AssistantDeps, ToolHelpers
from baserow_enterprise.assistant.model_profiles import ResolvedAssistantModelProfile


def start_message(user: Any) -> None:
    """
    Group the actions that follow, as the assistant view does for each message.

    :param user: The user the tools run as.
    """

    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))


def actions_in_message(user: Any) -> list[str]:
    """
    List the action types recorded in the user's current message group.

    :param user: The user the tools ran as.
    :return: The action types, oldest first.
    """

    group = get_client_undo_redo_action_group_id(user)
    actions = Action.objects.filter(action_group=group).order_by("id")
    return list(actions.values_list("type", flat=True))


def undo_message(user: Any, scopes: list[str]) -> None:
    """
    Undo the newest message group reachable from the given scopes.

    :param user: The user the tools ran as.
    :param scopes: The undo scopes the editor would send.
    """

    with transaction.atomic():
        ActionHandler.undo(user, scopes, get_untrusted_client_session_id(user))


def redo_message(user: Any, scopes: list[str]) -> None:
    """
    Redo the oldest undone message group reachable from the given scopes.

    :param user: The user the tools ran as.
    :param scopes: The undo scopes the editor would send.
    """

    with transaction.atomic():
        ActionHandler.redo(user, scopes, get_untrusted_client_session_id(user))


def create_fake_tool_helpers(
    model_profile: ResolvedAssistantModelProfile | None = None,
) -> ToolHelpers:
    """Create fresh tool helpers for a test.

    :param model_profile: The resolved profile nested agents should use. A mock
        profile is created when the test does not exercise model behavior.
    :return: A fresh helper container.
    """

    if model_profile is None:
        model_profile = MagicMock(spec=ResolvedAssistantModelProfile)
    return ToolHelpers(
        lambda x: None,
        lambda x: None,
        model_profile=model_profile,
    )


def make_test_ctx(
    user: Any,
    workspace: Any,
    tool_helpers: ToolHelpers | None = None,
    model_profile: ResolvedAssistantModelProfile | None = None,
) -> MagicMock:
    """
    Build a mock ``RunContext[AssistantDeps]`` for unit-testing tool functions.

    :param user: The user on whose behalf the tool runs.
    :param workspace: The workspace that scopes the tool run.
    :param tool_helpers: Optional pre-built helpers for the context.
    :param model_profile: The profile to use when creating default helpers.
    :return: A mock context whose ``deps`` is a real ``AssistantDeps`` instance.
    """

    if tool_helpers is None:
        tool_helpers = create_fake_tool_helpers(model_profile=model_profile)
    ctx = MagicMock()
    ctx.deps = AssistantDeps(
        user=user,
        workspace=workspace,
        tool_helpers=tool_helpers,
    )
    return ctx
