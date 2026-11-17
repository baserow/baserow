from typing import Callable, List

from django.db import transaction

from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.mcp.groups import GROUP_WORKSPACE_UNDO
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import MCPTool
from baserow.core.tools.types import BaseModel


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


def _replay(endpoint: MCPEndpoint, replay: Callable) -> list[dict]:
    # Only the changes made through this endpoint share its session, and an
    # endpoint belongs to one workspace, so no scope is needed to narrow them.
    with transaction.atomic():
        actions = replay(endpoint.user, [], endpoint.undo_session_id)
    return _describe(actions)


class UndoMcpTool(MCPTool):
    """
    Undoes the latest change made through this connection. Everything one tool
    call changed is undone together. Changes made in the Baserow web app or
    through another connection are never undone. Returns the undone actions, an
    empty list when there was nothing to undo. An action with `failed` true could
    not be undone, for example because what it changed was deleted since.
    """

    type = "undo"
    group = GROUP_WORKSPACE_UNDO
    title = "Undo the last change"
    destructive = True
    input_schema = NoInput

    def _sync_call(self, endpoint: MCPEndpoint, args: NoInput) -> list[dict]:
        return _replay(endpoint, ActionHandler.undo)


class RedoMcpTool(MCPTool):
    """
    Redoes the latest change undone with `undo`. Nothing is redone once another
    change was made through this connection after the undo. Returns the redone
    actions, an empty list when there was nothing to redo.
    """

    type = "redo"
    group = GROUP_WORKSPACE_UNDO
    title = "Redo the last undone change"
    destructive = True
    input_schema = NoInput

    def _sync_call(self, endpoint: MCPEndpoint, args: NoInput) -> list[dict]:
        return _replay(endpoint, ActionHandler.redo)
