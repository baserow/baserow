from typing import Callable, List

from django.db import transaction
from django.db.models import QuerySet

from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.action.signals import ActionCommandType
from baserow.core.exceptions import LockConflict
from baserow.core.mcp.constants import LOCKED_MESSAGE
from baserow.core.mcp.groups import GROUP_WORKSPACE_UNDO
from baserow.core.mcp.models import MCPEndpoint
from baserow.core.mcp.registries import MCPTool
from baserow.core.tools.errors import ToolFailedError
from baserow.core.tools.types import BaseModel

PARTLY_UNDONE_MESSAGE = (
    "Part of the latest tool call couldn't be undone, so the call is only partly "
    "undone and can't be undone further. Use `redo` to restore what was undone."
)


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


def _redo(user, scopes, session) -> List[Action]:
    """
    `ActionHandler.redo`, except for a part of a call whose undo failed. The
    handler would take that part together with the parts undone right before it,
    up to `MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP`, and only mark them all as not
    undone. Here only the actions whose undo failed together are, so the parts
    that were really undone are redone next.
    """

    latest = (
        Action.objects.filter(user=user, session=session, undone_at__isnull=False)
        .order_by("-undone_at", "-created_on", "-id")
        .select_for_update(of=("self",))
        .first()
    )
    if latest is None or latest.error is None or latest.action_group is None:
        return ActionHandler.redo(user, scopes, session)
    if Action.objects.filter(
        user=user,
        session=session,
        undone_at__isnull=True,
        created_on__gt=latest.undone_at,
    ).exists():
        return []
    failed_together = Action.objects.filter(
        user=user,
        session=session,
        action_group=latest.action_group,
        undone_at=latest.undone_at,
        error__isnull=False,
    )
    ids = list(failed_together.values_list("id", flat=True))
    Action.objects.filter(pk__in=ids).update(undone_at=None)
    actions = list(Action.objects.filter(pk__in=ids).order_by("created_on", "id"))
    user.web_socket_id = None
    ActionHandler.send_action_done_signal_for_actions(
        user, actions, ActionCommandType.REDO
    )
    return actions


def _replay(
    endpoint: MCPEndpoint,
    replay: Callable,
    next_in_line: Callable[[], QuerySet],
    redo: bool = False,
) -> list[dict]:
    """
    Undoes or redoes the latest tool call of the endpoint. `ActionHandler` takes at
    most `MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP` actions of a group at a time, so
    it's called again while the next action in line is still from the same call.
    It stops at a part that failed, so the rest of the call stays as it was. It
    also stops when another call of the endpoint added an action between the parts,
    and the next undo or redo goes on from there. An action added right before the
    next part is replayed is taken back with it, and the loop stops after it.
    """

    # Only the changes made through this endpoint share its session, and an
    # endpoint belongs to one workspace, so no scope is needed to narrow them.
    user, session = endpoint.user, endpoint.undo_session_id
    replayed = []
    try:
        with transaction.atomic():
            while True:
                # A redo of a part whose undo failed only marks it as not undone
                # again, so the redo goes on with the parts after it.
                failed_before = set(
                    next_in_line()
                    .filter(user=user, session=session, error__isnull=False)
                    .values_list("id", flat=True)
                    if redo
                    else []
                )
                actions = replay(user, [], session)
                replayed.extend(actions)
                group = actions[0].action_group if actions else None
                failed = [a for a in actions if a.error is not None]
                if group is None or (
                    failed and not any(a.id in failed_before for a in failed)
                ):
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
        user, session = endpoint.user, endpoint.undo_session_id

        def next_in_line():
            return Action.objects.filter(undone_at__isnull=True).order_by(
                "-created_on", "-id"
            )

        # A part whose undo failed is marked as undone, so `ActionHandler` would
        # go on with the older parts of the same call and leave it in pieces.
        # That's refused while `redo` can still restore the call.
        latest = next_in_line().filter(user=user, session=session).first()
        if latest is not None and latest.action_group is not None:
            to_redo = (
                Action.objects.filter(
                    user=user, session=session, undone_at__isnull=False
                )
                .order_by("-undone_at", "-created_on", "-id")
                .first()
            )
            if (
                to_redo is not None
                and to_redo.action_group == latest.action_group
                and to_redo.error is not None
                and not Action.objects.filter(
                    user=user,
                    session=session,
                    undone_at__isnull=True,
                    created_on__gt=to_redo.undone_at,
                ).exists()
            ):
                raise ToolFailedError(PARTLY_UNDONE_MESSAGE)
        return _replay(endpoint, ActionHandler.undo, next_in_line)


class RedoMcpTool(MCPTool):
    """
    Redoes the latest change undone with `undo`. Nothing is redone once another
    change was made through this endpoint key or connected app after the undo.
    Returns the redone actions, an empty list when there was nothing to redo. An
    action with `failed` true could not be redone, or had not been undone because
    its undo failed.
    """

    type = "redo"
    group = GROUP_WORKSPACE_UNDO
    title = "Redo the last undone change"
    destructive = True
    input_schema = NoInput

    def _sync_call(self, endpoint: MCPEndpoint, args: NoInput) -> list[dict]:
        return _replay(
            endpoint,
            _redo,
            lambda: Action.objects.filter(undone_at__isnull=False).order_by(
                "-undone_at", "-created_on", "-id"
            ),
            redo=True,
        )
