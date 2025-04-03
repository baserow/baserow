from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.core.db import specific_iterator
from baserow.core.handler import CoreHandler
from baserow.core.models import Application, Workspace
from baserow.core.operations import (
    ListApplicationsWorkspaceOperationType,
    ListWorkspacesOperationType,
    ReadApplicationOperationType,
    ReadWorkspaceOperationType,
)
from baserow.core.registries import application_type_registry


class CoreService:
    def __init__(self):
        self.handler = CoreHandler()

    def _enhance_and_filter_application_queryset(
        self, user: AbstractUser, workspace: Workspace
    ):
        return lambda model, queryset: application_type_registry.get_by_model(
            model
        ).enhance_and_filter_queryset(queryset, user, workspace)

    def list_workspaces(self, user: AbstractUser) -> QuerySet[Workspace]:
        """
        Get a list of all the workspaces the user has access to.

        :param user: The user trying to access the workspaces
        :return: A list of workspaces.
        """

        workspace_qs = self.handler.list_user_workspaces(user)
        return self.handler.filter_queryset(
            user, ListWorkspacesOperationType.type, workspace_qs
        )

    def get_workspace(self, user: AbstractUser, workspace_id: int) -> Workspace:
        """
        Get the workspace associated to the given id if the user has the permission
        to read it.

        :param user: The user trying to access the workspace
        :param workspace_id: The workspace id we want to return.
        :return: The workspace associated with the given id.
        """

        workspace = self.handler.get_workspace(workspace_id)

        self.handler.check_permissions(
            user,
            ReadWorkspaceOperationType.type,
            workspace=workspace,
            context=workspace,
        )

        return workspace

    def list_applications_in_workspace(
        self,
        user: AbstractUser,
        workspace: Workspace,
        specific: bool = True,
        base_queryset: Optional[QuerySet] = None,
    ) -> QuerySet[Application]:
        """
        Get a list of all the applications in a workspace.

        :param user: The user trying to access the applications
        :param workspace: The workspace instance where the applications must be listed.
        :param specific: If True the specific applications will be returned instead of
            the base applications. Set this to False if you only need the base
            applications to prevent unnecessary queries.
        :param base_queryset: The base queryset from where to select the applications
        :return: A list of applications
        """

        application_qs = self.handler.list_applications_in_workspace(
            workspace, base_queryset
        )

        application_qs = self.handler.filter_queryset(
            user,
            ListApplicationsWorkspaceOperationType.type,
            application_qs,
            workspace=workspace,
        )

        if specific:
            application_qs = self.handler.filter_specific_applications(
                application_qs,
                per_content_type_queryset_hook=self._enhance_and_filter_application_queryset(
                    user, workspace
                ),
            )

        return application_qs

    def get_application(
        self,
        user: AbstractUser,
        application_id: int,
        specific: bool = True,
        base_queryset: Optional[QuerySet] = None,
    ) -> Application:
        """
        Returns the application with the given id if the user has the right permissions.

        :param user: The user on whose behalf the application is requested.
        :param application_id: The identifier of the application that must be returned.
        :param specific: If True the specific application will be returned instead of
            the base application. Set this to False if you only need the base
            application to prevent unnecessary queries.
        :param base_queryset: The base queryset from where to select the application
            object.
        :raises UserNotInWorkspace: If the user does not belong to the workspace of
            the application.
        :return: The requested application instance of the provided id.
        """

        application = self.handler.get_application(
            application_id, base_queryset=base_queryset
        )

        CoreHandler().check_permissions(
            user,
            ReadApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        if specific:
            application = specific_iterator(
                [application],
                per_content_type_queryset_hook=self._enhance_and_filter_application_queryset(
                    user, application.workspace
                ),
                base_model=Application,
            )[0]

        return application
