import dataclasses
from typing import Any, Dict

from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import (
    ActionScopeStr,
    ActionType,
    ActionTypeDescription,
)
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.models import Application, Workspace

from .handler import SCHEDULE_FIELDS, UpdatedAutomaticSnapshotSchedule
from .models import AutomaticSnapshotSchedule
from .service import AutomaticSnapshotScheduleService


def _schedule_values(schedule: AutomaticSnapshotSchedule) -> Dict[str, Any]:
    return {field: getattr(schedule, field) for field in SCHEDULE_FIELDS}


class AutomaticSnapshotScheduleActionType(ActionType):
    """
    The changes to automatic snapshot schedules aren't undoable. They're registered
    as actions so that they're recorded in the audit log.
    """

    analytics_params = ["workspace_id", "application_id", "schedule_id"]

    @classmethod
    def scope(cls, workspace_id: int) -> ActionScopeStr:
        return WorkspaceActionScopeType.value(workspace_id)


class CreateWorkspaceAutomaticSnapshotScheduleActionType(
    AutomaticSnapshotScheduleActionType
):
    type = "create_workspace_automatic_snapshot_schedule"
    description = ActionTypeDescription(
        _("Create workspace automatic snapshot schedule"),
        _(
            "Automatic snapshot schedule (%(schedule_id)s) created for workspace "
            '"%(group_name)s" (%(group_id)s).'
        ),
    )
    analytics_params = ["workspace_id", "schedule_id"]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        schedule_id: int
        values: Dict[str, Any]

    @classmethod
    def do(
        cls, user: AbstractUser, workspace: Workspace, values: Dict[str, Any]
    ) -> AutomaticSnapshotSchedule:
        """
        Creates the workspace default schedule.

        :param user: The user creating the schedule.
        :param workspace: The workspace.
        :param values: The schedule values.
        :return: The created schedule.
        """

        schedule = AutomaticSnapshotScheduleService().create_workspace_default(
            user, workspace, values
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id, workspace.name, schedule.id, _schedule_values(schedule)
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return schedule


class UpdateWorkspaceAutomaticSnapshotScheduleActionType(
    AutomaticSnapshotScheduleActionType
):
    type = "update_workspace_automatic_snapshot_schedule"
    description = ActionTypeDescription(
        _("Update workspace automatic snapshot schedule"),
        _(
            "Automatic snapshot schedule (%(schedule_id)s) updated for workspace "
            '"%(group_name)s" (%(group_id)s).'
        ),
    )
    analytics_params = ["workspace_id", "schedule_id"]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        schedule_id: int
        original_values: Dict[str, Any]
        values: Dict[str, Any]

    @classmethod
    def do(
        cls, user: AbstractUser, workspace: Workspace, values: Dict[str, Any]
    ) -> UpdatedAutomaticSnapshotSchedule:
        """
        Updates the workspace default schedule.

        :param user: The user updating the schedule.
        :param workspace: The workspace.
        :param values: The schedule values to change.
        :return: The updated schedule, with its original and new values.
        """

        updated = AutomaticSnapshotScheduleService().update_workspace_default(
            user, workspace, values
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id,
                workspace.name,
                updated.schedule.id,
                updated.original_values,
                updated.new_values,
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return updated


class DeleteWorkspaceAutomaticSnapshotScheduleActionType(
    AutomaticSnapshotScheduleActionType
):
    type = "delete_workspace_automatic_snapshot_schedule"
    description = ActionTypeDescription(
        _("Delete workspace automatic snapshot schedule"),
        _(
            "Automatic snapshot schedule (%(schedule_id)s) deleted for workspace "
            '"%(group_name)s" (%(group_id)s).'
        ),
    )
    analytics_params = ["workspace_id", "schedule_id"]

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        schedule_id: int
        original_values: Dict[str, Any]

    @classmethod
    def do(cls, user: AbstractUser, workspace: Workspace) -> None:
        """
        Deletes the workspace default schedule.

        :param user: The user deleting the schedule.
        :param workspace: The workspace.
        """

        schedule = AutomaticSnapshotScheduleService().delete_workspace_default(
            user, workspace
        )
        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id, workspace.name, schedule.id, _schedule_values(schedule)
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )


class CreateApplicationAutomaticSnapshotScheduleActionType(
    AutomaticSnapshotScheduleActionType
):
    type = "create_application_automatic_snapshot_schedule"
    description = ActionTypeDescription(
        _("Create application automatic snapshot schedule"),
        _(
            "Automatic snapshot schedule (%(schedule_id)s) created for application "
            '"%(application_name)s" (%(application_id)s).'
        ),
    )

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_id: int
        application_name: str
        schedule_id: int
        values: Dict[str, Any]

    @classmethod
    def do(
        cls, user: AbstractUser, application: Application, values: Dict[str, Any]
    ) -> AutomaticSnapshotSchedule:
        """
        Creates a schedule of the provided application.

        :param user: The user creating the schedule.
        :param application: The application.
        :param values: The schedule values.
        :return: The created schedule.
        """

        schedule = AutomaticSnapshotScheduleService().create_application_schedule(
            user, application, values
        )
        workspace = application.workspace
        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id,
                workspace.name,
                application.id,
                application.name,
                schedule.id,
                _schedule_values(schedule),
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return schedule


class UpdateApplicationAutomaticSnapshotScheduleActionType(
    AutomaticSnapshotScheduleActionType
):
    type = "update_application_automatic_snapshot_schedule"
    description = ActionTypeDescription(
        _("Update application automatic snapshot schedule"),
        _(
            "Automatic snapshot schedule (%(schedule_id)s) updated for application "
            '"%(application_name)s" (%(application_id)s).'
        ),
    )

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_id: int
        application_name: str
        schedule_id: int
        original_values: Dict[str, Any]
        values: Dict[str, Any]

    @classmethod
    def do(
        cls, user: AbstractUser, application: Application, values: Dict[str, Any]
    ) -> UpdatedAutomaticSnapshotSchedule:
        """
        Updates the schedule of the provided application.

        :param user: The user updating the schedule.
        :param application: The application.
        :param values: The schedule values to change.
        :return: The updated schedule, with its original and new values.
        """

        updated = AutomaticSnapshotScheduleService().update_application_schedule(
            user, application, values
        )
        workspace = application.workspace
        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id,
                workspace.name,
                application.id,
                application.name,
                updated.schedule.id,
                updated.original_values,
                updated.new_values,
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
        return updated


class DeleteApplicationAutomaticSnapshotScheduleActionType(
    AutomaticSnapshotScheduleActionType
):
    type = "delete_application_automatic_snapshot_schedule"
    description = ActionTypeDescription(
        _("Delete application automatic snapshot schedule"),
        _(
            "Automatic snapshot schedule (%(schedule_id)s) deleted for application "
            '"%(application_name)s" (%(application_id)s).'
        ),
    )

    @dataclasses.dataclass
    class Params:
        workspace_id: int
        workspace_name: str
        application_id: int
        application_name: str
        schedule_id: int
        original_values: Dict[str, Any]

    @classmethod
    def do(cls, user: AbstractUser, application: Application) -> None:
        """
        Deletes the schedule of the provided application, so it follows the
        workspace default again.

        :param user: The user deleting the schedule.
        :param application: The application.
        """

        schedule = AutomaticSnapshotScheduleService().delete_application_schedule(
            user, application
        )
        workspace = application.workspace
        cls.register_action(
            user=user,
            params=cls.Params(
                workspace.id,
                workspace.name,
                application.id,
                application.name,
                schedule.id,
                _schedule_values(schedule),
            ),
            scope=cls.scope(workspace.id),
            workspace=workspace,
        )
