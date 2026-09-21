from typing import List, Optional

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

    def _enhance_and_filter_application_queryset_for_workspaces(
        self, user: AbstractUser, workspaces: List[Workspace]
    ):
        return lambda model, queryset: application_type_registry.get_by_model(
            model
        ).enhance_and_filter_queryset_for_workspaces(queryset, user, workspaces)

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

        return self.list_applications_in_workspaces(
            user, [workspace], specific=specific, base_queryset=base_queryset
        )

    def list_applications_in_workspaces(
        self,
        user: AbstractUser,
        workspaces: List[Workspace],
        specific: bool = True,
        base_queryset: Optional[QuerySet] = None,
    ) -> QuerySet[Application]:
        """
        Get a list of all the applications in multiple workspaces in a single pass.
        Contrary to calling `list_applications_in_workspace` per workspace, the
        permission filtering and the queryset enhancements are batched across all the
        workspaces, keeping the number of queries independent of the number of
        workspaces.

        :param user: The user trying to access the applications.
        :param workspaces: The workspaces where the applications must be listed,
            ordered by id. To keep the number of queries independent of the number of
            workspaces, the workspace instances should come from
            `CoreHandler.get_enhanced_workspace_queryset` so their memberships and
            templates are prefetched.
        :param specific: If True the specific applications will be returned instead of
            the base applications.
        :param base_queryset: The base queryset from where to select the applications.
        :return: A queryset of applications ordered by workspace id, then order and id.
        """

        application_qs = self.handler.list_applications_in_workspaces(
            workspaces, base_queryset
        )

        application_qs = self.handler.filter_queryset_for_workspaces(
            user,
            ListApplicationsWorkspaceOperationType.type,
            application_qs,
            workspaces,
        )

        if specific:
            application_qs = self.handler.filter_specific_applications(
                application_qs,
                per_content_type_queryset_hook=(
                    self._enhance_and_filter_application_queryset_for_workspaces(
                        user, workspaces
                    )
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
                per_content_type_queryset_hook=(
                    self._enhance_and_filter_application_queryset_for_workspaces(
                        user, [application.workspace]
                    )
                ),
                base_model=Application,
            )[0]

        return application
