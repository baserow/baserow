from typing import Any, Dict, List

from django.contrib.auth.models import AbstractUser
from django.db.models import Q, QuerySet

from baserow.core.db import specific_iterator
from baserow.core.exceptions import (
    ApplicationDoesNotExist,
    ApplicationOperationNotSupported,
)
from baserow.core.handler import CoreHandler
from baserow.core.models import Application, Workspace
from baserow.core.operations import ListApplicationsWorkspaceOperationType
from baserow.core.registries import application_type_registry
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import AUTOMATIC_SNAPSHOTS
from baserow_premium.license.handler import LicenseHandler

from .exceptions import AutomaticSnapshotScheduleDoesNotExist
from .handler import (
    AutomaticSnapshotScheduleHandler,
    UpdatedAutomaticSnapshotSchedule,
    get_schedule_state,
)
from .models import AutomaticSnapshotLastRun, AutomaticSnapshotSchedule
from .operations import (
    ReadApplicationAutomaticSnapshotScheduleOperationType,
    ReadWorkspaceAutomaticSnapshotScheduleOperationType,
    UpdateApplicationAutomaticSnapshotScheduleOperationType,
    UpdateWorkspaceAutomaticSnapshotScheduleOperationType,
)


class AutomaticSnapshotScheduleService:
    def __init__(self):
        self.handler = AutomaticSnapshotScheduleHandler()

    def _check_application(
        self, user: AbstractUser, application: Application, operation_type: str
    ) -> None:
        LicenseHandler.raise_if_user_doesnt_have_feature(
            AUTOMATIC_SNAPSHOTS, user, application.workspace
        )
        CoreHandler().check_permissions(
            user,
            operation_type,
            workspace=application.workspace,
            context=application,
        )

    def _check_workspace(
        self, user: AbstractUser, workspace: Workspace, operation_type: str
    ) -> None:
        LicenseHandler.raise_if_user_doesnt_have_feature(
            AUTOMATIC_SNAPSHOTS, user, workspace
        )
        CoreHandler().check_permissions(
            user,
            operation_type,
            workspace=workspace,
            context=workspace,
        )

    def get_applications_for_update(
        self, user: AbstractUser, workspace: Workspace, application_ids: List[int]
    ) -> List[Application]:
        """
        Returns the specific applications with the provided ids, after checking
        that the user can change the schedule of every one of them.

        :param user: The user changing the schedules.
        :param workspace: The workspace the applications must belong to.
        :param application_ids: The ids of the applications.
        :raises ApplicationDoesNotExist: When one of the applications doesn't exist
            in the workspace, or the user can't see it.
        :return: The applications.
        """

        LicenseHandler.raise_if_user_doesnt_have_feature(
            AUTOMATIC_SNAPSHOTS, user, workspace
        )
        CoreHandler().check_permissions(
            user,
            ListApplicationsWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )
        visible_applications = CoreHandler().filter_queryset(
            user,
            ListApplicationsWorkspaceOperationType.type,
            Application.objects_without_shared.filter(
                workspace=workspace, id__in=application_ids
            ),
            workspace=workspace,
        )
        applications = specific_iterator(
            visible_applications.select_related("workspace"),
            select_related=["workspace"],
        )
        if len(applications) != len(set(application_ids)):
            raise ApplicationDoesNotExist()

        checks = [
            PermissionCheck(
                user,
                UpdateApplicationAutomaticSnapshotScheduleOperationType.type,
                application,
            )
            for application in applications
        ]
        CoreHandler().check_multiple_permissions(
            checks, workspace, raise_exception=True
        )
        return applications

    def get_application(self, application_id: int) -> Application:
        """
        Returns the specific application with the provided id, with its workspace.
        The specific instance is needed so that roles given on the application
        apply to the permission checks.

        :param application_id: The id of the application.
        :raises ApplicationDoesNotExist: When the application doesn't exist.
        :return: The application.
        """

        return (
            CoreHandler()
            .get_application(
                application_id,
                base_queryset=Application.objects.select_related("workspace"),
            )
            .specific
        )

    def get_application_overview(
        self, user: AbstractUser, application: Application
    ) -> Dict[str, Any]:
        """
        Returns which schedule the provided application follows: its own, if it has
        one, and the workspace default. Reading it needs the permission on the
        application only, so an application Admin can see the workspace default that
        covers their application.

        :param user: The user requesting the overview.
        :param application: The application.
        :return: A dict with the `state`, the application `schedule` and the
            `workspace_default`, and the application's latest completed attempt.
        """

        self._check_application(
            user,
            application,
            ReadApplicationAutomaticSnapshotScheduleOperationType.type,
        )
        try:
            schedule = self.handler.get_application_schedule(application)
        except AutomaticSnapshotScheduleDoesNotExist:
            schedule = None
        try:
            workspace_default = self.handler.get_workspace_default(
                application.workspace
            )
        except AutomaticSnapshotScheduleDoesNotExist:
            workspace_default = None

        return {
            "last_run": AutomaticSnapshotLastRun.objects.filter(
                application=application
            ).first(),
            "state": get_schedule_state(schedule),
            "schedule": schedule,
            "workspace_default": workspace_default,
        }

    def get_workspace_schedules(
        self, user: AbstractUser, workspace: Workspace
    ) -> QuerySet:
        """
        Returns the workspace default schedule and the schedules of the
        applications in the workspace that the user can see.

        :param user: The user requesting the schedules.
        :param workspace: The workspace.
        :return: A queryset of schedules.
        """

        self._check_workspace(
            user, workspace, ReadWorkspaceAutomaticSnapshotScheduleOperationType.type
        )
        visible_applications = CoreHandler().filter_queryset(
            user,
            ListApplicationsWorkspaceOperationType.type,
            Application.objects_without_shared.filter(workspace=workspace),
            workspace=workspace,
        )
        return self.handler.list_workspace_schedules(workspace).filter(
            Q(application__isnull=True) | Q(application__in=visible_applications)
        )

    def create_application_schedule(
        self, user: AbstractUser, application: Application, values: Dict[str, Any]
    ) -> AutomaticSnapshotSchedule:
        """
        Creates a schedule of the provided application.

        :param user: The user creating the schedule.
        :param application: The application.
        :param values: The schedule values.
        :raises ApplicationOperationNotSupported: When the application type doesn't
            support snapshots.
        :return: The created schedule.
        """

        self._check_application(
            user,
            application,
            UpdateApplicationAutomaticSnapshotScheduleOperationType.type,
        )
        app_type = application_type_registry.get_by_model(application.specific_class)
        if app_type.supports_snapshots is False:
            raise ApplicationOperationNotSupported()

        return self.handler.create_schedule(
            application.workspace, application=application, **values
        )

    def update_application_schedule(
        self, user: AbstractUser, application: Application, values: Dict[str, Any]
    ) -> UpdatedAutomaticSnapshotSchedule:
        """
        Updates the schedule of the provided application.

        :param user: The user updating the schedule.
        :param application: The application.
        :param values: The schedule values to change.
        :return: The updated schedule, with its original and new values.
        """

        self._check_application(
            user,
            application,
            UpdateApplicationAutomaticSnapshotScheduleOperationType.type,
        )
        schedule = self.handler.get_application_schedule(application, for_update=True)
        return self.handler.update_schedule(schedule, **values)

    def delete_application_schedule(
        self, user: AbstractUser, application: Application
    ) -> AutomaticSnapshotSchedule:
        """
        Deletes the schedule of the provided application, so it follows the
        workspace default again.

        :param user: The user deleting the schedule.
        :param application: The application.
        :return: The deleted schedule.
        """

        self._check_application(
            user,
            application,
            UpdateApplicationAutomaticSnapshotScheduleOperationType.type,
        )
        schedule = self.handler.get_application_schedule(application, for_update=True)
        self.handler.delete_schedule(schedule)
        return schedule

    def create_workspace_default(
        self, user: AbstractUser, workspace: Workspace, values: Dict[str, Any]
    ) -> AutomaticSnapshotSchedule:
        """
        Creates the workspace default schedule.

        :param user: The user creating the schedule.
        :param workspace: The workspace.
        :param values: The schedule values.
        :return: The created schedule.
        """

        self._check_workspace(
            user, workspace, UpdateWorkspaceAutomaticSnapshotScheduleOperationType.type
        )
        return self.handler.create_schedule(workspace, application=None, **values)

    def update_workspace_default(
        self, user: AbstractUser, workspace: Workspace, values: Dict[str, Any]
    ) -> UpdatedAutomaticSnapshotSchedule:
        """
        Updates the workspace default schedule.

        :param user: The user updating the schedule.
        :param workspace: The workspace.
        :param values: The schedule values to change.
        :return: The updated schedule, with its original and new values.
        """

        self._check_workspace(
            user, workspace, UpdateWorkspaceAutomaticSnapshotScheduleOperationType.type
        )
        schedule = self.handler.get_workspace_default(workspace, for_update=True)
        return self.handler.update_schedule(schedule, **values)

    def delete_workspace_default(
        self, user: AbstractUser, workspace: Workspace
    ) -> AutomaticSnapshotSchedule:
        """
        Deletes the workspace default schedule.

        :param user: The user deleting the schedule.
        :param workspace: The workspace.
        :return: The deleted schedule.
        """

        self._check_workspace(
            user, workspace, UpdateWorkspaceAutomaticSnapshotScheduleOperationType.type
        )
        schedule = self.handler.get_workspace_default(workspace, for_update=True)
        self.handler.delete_schedule(schedule)
        return schedule
