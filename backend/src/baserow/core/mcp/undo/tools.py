from typing import Callable, List

from django.db import transaction
from django.db.models import QuerySet

from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import LockConflict
from baserow.core.mcp.groups import GROUP_WORKSPACE_UNDO
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import MCPTool
from baserow.core.tools.errors import ToolFailedError
from baserow.core.tools.types import BaseModel

LOCKED_MESSAGE = "Something else is changing the same data. Try again in a moment."


class NoInput(BaseModel):
    pass


def _describe(actions: List[Action]) -> list[dict]:
    return [
        {
            "action": action_type_registry.get(action.type).get_short_description(),
            "failed": action.error is not None,
        }
        for action in actions
    ]


def _replay(
    endpoint: MCPEndpoint, replay: Callable, next_in_line: Callable[[], QuerySet]
) -> list[dict]:
    """
    Undoes or redoes the latest tool call of the endpoint. `ActionHandler` takes at
    most `MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP` actions of a group at a time, so
    it's called again while the next action in line is still from the same call.
    """

    # Only the changes made through this endpoint share its session, and an
    # endpoint belongs to one workspace, so no scope is needed to narrow them.
    user, session = endpoint.user, endpoint.undo_session_id
    replayed = []
    try:
        with transaction.atomic():
            while True:
                actions = replay(user, [], session)
                replayed.extend(actions)
                group = actions[0].action_group if actions else None
                if group is None:
                    break
                following = next_in_line().filter(user=user, session=session).first()
                if following is None or following.action_group != group:
                    break
    except LockConflict as exc:
        raise ToolFailedError(LOCKED_MESSAGE) from exc
    return _describe(replayed)


class UndoMcpTool(MCPTool):
    """
    Undoes the latest change made through this endpoint key or connected app.
    Everything one tool call changed is undone together. Changes made in the
    Baserow web app are never undone. Every client and chat that uses the same
    key or app shares these changes, so the latest one can come from another
    chat. Returns the undone actions, an empty list when there was nothing to
    undo. An action with `failed` true could not be undone, for example because
    what it changed was deleted since.
    """

    type = "undo"
    group = GROUP_WORKSPACE_UNDO
    title = "Undo the last change"
    destructive = True
    input_schema = NoInput

    def _sync_call(self, endpoint: MCPEndpoint, args: NoInput) -> list[dict]:
        return _replay(
            endpoint,
            ActionHandler.undo,
            lambda: Action.objects.filter(undone_at__isnull=True).order_by(
                "-created_on", "-id"
            ),
        )


class RedoMcpTool(MCPTool):
    """
    Redoes the latest change undone with `undo`. Nothing is redone once another
    change was made through this endpoint key or connected app after the undo.
    Returns the redone actions, an empty list when there was nothing to redo. An
    action with `failed` true had not been undone because its undo failed, so
    nothing was changed for it.
    """

    type = "redo"
    group = GROUP_WORKSPACE_UNDO
    title = "Redo the last undone change"
    destructive = True
    input_schema = NoInput

    def _sync_call(self, endpoint: MCPEndpoint, args: NoInput) -> list[dict]:
        return _replay(
            endpoint,
            ActionHandler.redo,
            lambda: Action.objects.filter(undone_at__isnull=False).order_by(
                "-undone_at", "-created_on", "-id"
            ),
        )
