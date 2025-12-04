import traceback
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Set, Tuple

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.db.models import Q

from loguru import logger
from opentelemetry import trace

from baserow.core.exceptions import LockConflict
from baserow.core.telemetry.utils import baserow_trace, baserow_trace_methods

from .models import Action
from .registries import (
    ActionScopeStr,
    UndoableActionCustomCleanupMixin,
    action_type_registry,
)
from .signals import ActionCommandType

tracer = trace.get_tracer(__name__)


def scopes_to_q_filter(scopes: List[ActionScopeStr]):
    """
    Provides a Q filter which matches the provided scopes. If no scopes are provided
    then a Q which matches all actions will be returned.
    """

    q = Q()
    for scope_str in scopes:
        q |= Q(scope=scope_str)
    return q


class OneActionHasErrorAndCannotBeRedone(Exception):
    """
    Raised if an action raised an error during undo so cannot be redone.
    """


class ActionHandler(metaclass=baserow_trace_methods(tracer)):
    """
    Contains methods to do high level operations on ActionType's like undoing or
    redoing them.
    """

    @classmethod
    def send_action_done_signal_for_actions(
        cls,
        user: AbstractUser,
        actions: List[Action],
        action_command_type: ActionCommandType,
        **kwargs,
    ) -> None:
        for action in actions:
            action_type = action_type_registry.get(action.type)
            action_type.send_action_done_signal(
                user,
                action.params,
                action.scope,
                action.workspace,
                action.updated_on,
                action_command_type,
            )

    @classmethod
    def _undo_action(
        cls, user: AbstractUser, action: Action, undone_at: datetime
    ) -> None:
        try:
            action.error = None
            # noinspection PyBroadException
            action_type = action_type_registry.get(action.type)
            # noinspection PyArgumentList
            latest_params = action_type.serialized_to_params(action.params)

            action_type.undo(user, latest_params, action)
            # action.params could be changed, so save the action
            action.undone_at = undone_at
            action.save()
        except Exception as exc:
            tb = traceback.format_exc()
            logger.warning(
                "Undoing {action} failed because of: \n" + str(tb), action=action.type
            )
            raise exc

    @classmethod
    @baserow_trace(tracer)
    def undo(
        cls, user: AbstractUser, scopes: List[ActionScopeStr], session: str
    ) -> List[Action]:
        # Un-set the web_socket_id so the user doing this undo will receive any
        # events triggered by the action.
        user.web_socket_id = None

        latest_not_undone_action = (
            Action.objects.filter(user=user, undone_at__isnull=True, session=session)
            .filter(scopes_to_q_filter(scopes))
            .order_by("-created_on", "-id")
            .select_for_update(of=("self",))
            .first()
        )
        if latest_not_undone_action is None:
            return []

        if latest_not_undone_action.action_group is None:
            actions_being_undone = [latest_not_undone_action]
        else:
            actions_being_undone = list(
                Action.objects.filter(
                    undone_at__isnull=True,
                    action_group=latest_not_undone_action.action_group,
                    session=session,
                    user=user,
                )
                .order_by("-created_on", "-id")[
                    : settings.MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP
                ]
                .select_for_update(of=("self",))
            )

        undone_at = datetime.now(tz=timezone.utc)
        action_being_undone_ids = [action.id for action in actions_being_undone]
        try:
            # Wrap all the action group to ensure any errors get rolled back.
            with transaction.atomic():
                for action in actions_being_undone:
                    cls._undo_action(user, action, undone_at)
        except LockConflict:
            raise
        except Exception:
            # if any single action fails, rollback and set the same error for all.
            tb = traceback.format_exc()
            if action.action_group is not None:
                logger.warning(
                    "Rolling back action group {action_group}:",
                    action_group=action.action_group,
                )
            Action.objects.filter(pk__in=action_being_undone_ids).update(
                error=tb, undone_at=undone_at
            )

        # refresh actions from db to ensure everything is updated
        actions = list(Action.objects.filter(pk__in=action_being_undone_ids))
        cls.send_action_done_signal_for_actions(user, actions, ActionCommandType.UNDO)
        return actions

    @classmethod
    def _redo_action(cls, user: AbstractUser, action: Action) -> None:
        # noinspection PyBroadException
        try:
            action_being_redone = action
            action_type = action_type_registry.get(action.type)
            # noinspection PyArgumentList
            latest_params = action_type.serialized_to_params(action.params)

            action_type.redo(user, latest_params, action_being_redone)

            # action.params could be changed, so save the action
            action.undone_at = None
            action.save()
        except Exception as exc:
            tb = traceback.format_exc()
            logger.warning(
                "Redoing {action} failed because of: \n" + str(tb), action=action
            )
            raise exc

    @classmethod
    @baserow_trace(tracer)
    def redo(
        cls, user: AbstractUser, scopes: List[ActionScopeStr], session: str
    ) -> List[Action]:
        # Un-set the web_socket_id so the user doing this redo will receive any
        # events triggered by the action.
        user.web_socket_id = None

        scopes_filter = scopes_to_q_filter(scopes)
        latest_undone_action = (
            Action.objects.filter(user=user, undone_at__isnull=False, session=session)
            .filter(scopes_filter)
            .order_by("-undone_at", "-created_on", "-id")
            .select_for_update(of=("self",))
            .first()
        )

        if latest_undone_action is None:
            return []

        if latest_undone_action.action_group is None:
            actions_being_redone = [latest_undone_action]
        else:
            actions_being_redone = list(
                Action.objects.filter(
                    undone_at__isnull=False,
                    action_group=latest_undone_action.action_group,
                    session=session,
                    user=user,
                )
                .order_by("created_on", "id")[
                    : settings.MAX_UNDOABLE_ACTIONS_PER_ACTION_GROUP
                ]
                .select_for_update(of=("self",))
            )

        actions_being_redone_ids = [action.id for action in actions_being_redone]
        if not actions_being_redone:
            return []

        normal_action_happened_since_undo = (
            Action.objects.filter(
                user=user,
                created_on__gt=actions_being_redone[0].undone_at,
                undone_at__isnull=True,
                session=session,
            )
            .filter(scopes_filter)
            .exists()
        )
        if normal_action_happened_since_undo:
            return []

        actions_has_errors = Action.objects.filter(
            pk__in=actions_being_redone_ids, error__isnull=False
        ).exists()
        if actions_has_errors:
            # We are redoing an action group that failed during the undo and so we
            # actually have nothing to redo. In this case, we mark it as redone so
            # the user can try undo them again to see if it works this time.
            Action.objects.filter(pk__in=actions_being_redone_ids).update(
                undone_at=None
            )
        else:
            try:
                # Wrap all the action group to ensure any errors get rolled back.
                with transaction.atomic():
                    for action in actions_being_redone:
                        cls._redo_action(user, action)
            except LockConflict:
                raise
            except Exception:
                # if just one action fails, rollback and set the same error for all.
                tb = traceback.format_exc()
                if latest_undone_action.action_group is not None:
                    logger.warning(
                        "Rolling back action group {action_group}:",
                        action_group=latest_undone_action.action_group,
                    )
                Action.objects.filter(pk__in=actions_being_redone_ids).update(
                    error=tb, undone_at=None
                )

        # refresh actions from db to ensure everything is updated
        actions = list(
            Action.objects.filter(pk__in=actions_being_redone_ids).order_by(
                "created_on", "id"
            )
        )
        cls.send_action_done_signal_for_actions(user, actions, ActionCommandType.REDO)
        return actions

    @classmethod
    def clean_up_old_undoable_actions(cls):
        """
        Any actions which haven't been updated in
        settings.MINUTES_UNTIL_ACTION_CLEANED_UP will be deleted any have an extra
        data associated with them cleaned up.
        """

        now = datetime.now(tz=timezone.utc)
        minutes = int(settings.MINUTES_UNTIL_ACTION_CLEANED_UP)
        cutoff = now - timedelta(minutes=minutes)

        types_with_custom_clean_up = set()
        for action_type in action_type_registry.get_all():
            if isinstance(action_type, UndoableActionCustomCleanupMixin):
                types_with_custom_clean_up.add(action_type.type)

        # Delete in a separate atomic block so if we crash later we don't roll back
        # these valid deletes.
        with transaction.atomic():
            # Here we delete all actions which have a type which doesn't have a custom
            # `clean_up_any_extra_action_data` implementation. This means that all
            # we need to do to clean them up is delete the actions, which we can do
            # in a single DELETE WHERE query.
            bulk_delete_count, _ = (
                Action.objects.filter(updated_on__lte=cutoff)
                .exclude(type__in=types_with_custom_clean_up)
                .delete()
            )

        (
            custom_deleted_count,
            cleanup_error,
        ) = cls._cleanup_actions_with_custom_cleanup_logic(
            cutoff, types_with_custom_clean_up
        )
        total_deleted = bulk_delete_count + custom_deleted_count

        logger.info(f"Cleaned up {total_deleted} actions.")

        if cleanup_error:
            logger.error("However an error was encountered during an action cleanup: ")
            raise cleanup_error

    @classmethod
    def _cleanup_actions_with_custom_cleanup_logic(
        cls, cutoff: datetime, types_with_custom_clean_up: Set[str]
    ) -> Tuple[int, Optional[Exception]]:
        """
        ActionTypes can implement a custom clean_up_any_extra_action_data method to
        clean up any extra data associated with them. This method will loop over all
        of those actions calling their custom clean_up_any_extra_action_data method
        and deleting the action.

        :param cutoff: Any actions updated on or before this time will be cleaned up.
        :param types_with_custom_clean_up: The set of ActionType.type names which
            have custom clean_up_any_extra_action_data methods which need to be
            called to do some extra per type cleanup.
        :return: A tuple of the number of deleted actions and an optional Exception
            which is present when a custom cleanup failed.
        """

        with transaction.atomic():
            actions_to_cleanup_with_custom_logic = (
                Action.objects.filter(
                    updated_on__lte=cutoff, type__in=types_with_custom_clean_up
                )
                .select_for_update(of=("self",))
                .order_by("updated_on", "id")
            )
            deleted_count = 0
            for action in actions_to_cleanup_with_custom_logic:
                try:
                    with transaction.atomic():
                        # Run each clean up in a single inside its own atomic block so
                        # later cleanup for different action fails we don't roll back
                        # previous successful clean ups.
                        action_type = action_type_registry.get(action.type)
                        action_type.clean_up_any_extra_action_data(action)
                        action.delete()
                        deleted_count += 1
                except Exception as e:
                    # We don't want to roll back the entire transaction if one of the
                    # cleanup's failed. The failed cleanup has already been rolled
                    # back due to its own inner atomic block so we can safely stop
                    # , commit the outer transaction which persists the successful
                    # cleanups and let the caller decide what to do with the error.
                    return deleted_count, e

        return deleted_count, None
