from typing import Any, Dict, List, Optional, Tuple

from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import CannotCalculateIntermediateOrder
from baserow.core.handler import CoreHandler
from baserow.core.integrations.exceptions import (
    IntegrationNotInSameApplication,
)
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import (
    CreateIntegrationOperationType,
    CreateIntegrationWorkspaceOperationType,
    DeleteIntegrationOperationType,
    DeleteWorkspaceIntegrationOperationType,
    ListIntegrationsApplicationOperationType,
    ListIntegrationsWorkspaceOperationType,
    OrderIntegrationsWorkspaceOperationType,
    ReadIntegrationOperationType,
    UpdateIntegrationOperationType,
    UpdateWorkspaceIntegrationOperationType,
)
from baserow.core.integrations.registries import (
    IntegrationType,
    check_secret_targets_unchanged,
)
from baserow.core.integrations.signals import (
    integration_created,
    integration_moved,
    integration_orders_recalculated,
    integration_updated,
)
from baserow.core.integrations.types import IntegrationForUpdate, UpdatedIntegration
from baserow.core.models import Application, Workspace
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import extract_undo_redo_values


class IntegrationService:
    def __init__(self):
        self.handler = IntegrationHandler()

    def _get_operation_and_context(
        self,
        application: Application,
        operation_name: str,
        workspace_operation_name: str,
    ) -> Tuple[str, Application | Workspace]:
        """
        Picks the operation to check on the integrations of the given application.
        Those of the shared application are the workspace integrations, so the
        workspace operation is checked on the workspace instead.

        :param application: The application that holds the integrations.
        :param operation_name: The operation on the integrations of an application.
        :param workspace_operation_name: The operation on the workspace integrations.
        :return: The operation name and the context to check it on.
        """

        if self.handler.is_shared_application(application):
            return workspace_operation_name, application.workspace
        return operation_name, application

    def check_integration_permission(
        self,
        user: AbstractUser,
        integration: Integration,
        operation_name: str,
        workspace_operation_name: str,
    ):
        """
        Checks an operation on the given integration. A workspace integration is
        checked with the workspace operation instead, because the operation on an
        integration of an application resolves through the shared application to
        the workspace, so it would let anyone allowed to manage the integrations of
        every application in the workspace manage it.

        :param user: The user to check.
        :param integration: The integration the operation is about.
        :param operation_name: The operation on an integration of an application.
        :param workspace_operation_name: The operation on a workspace integration.
        :raises PermissionException: When the user isn't allowed.
        """

        if self.handler.is_shared_application(integration.application):
            operation_name = workspace_operation_name

        CoreHandler().check_permissions(
            user,
            operation_name,
            workspace=integration.application.workspace,
            context=integration,
        )

    def get_integration(self, user: AbstractUser, integration_id: int) -> Integration:
        """
        Returns an integration instance from the database. Also checks the user
        permissions.

        :param user: The user trying to get the integration.
        :param integration_id: The ID of the integration.
        :return: The integration instance.
        """

        integration = self.handler.get_integration(integration_id)

        CoreHandler().check_permissions(
            user,
            ReadIntegrationOperationType.type,
            workspace=integration.application.workspace,
            context=integration,
        )

        return integration

    def get_integrations(
        self, user: AbstractUser, application: Application
    ) -> List[Integration]:
        """
        Gets all the integrations of a given application visible to the given user.

        :param user: The user trying to get the integrations.
        :param application: The application that holds the integrations.
        :return: The integrations of that application.
        """

        operation_name, context = self._get_operation_and_context(
            application,
            ListIntegrationsApplicationOperationType.type,
            ListIntegrationsWorkspaceOperationType.type,
        )

        CoreHandler().check_permissions(
            user,
            operation_name,
            workspace=application.workspace,
            context=context,
        )

        user_integrations = CoreHandler().filter_queryset(
            user,
            operation_name,
            Integration.objects.all(),
            workspace=application.workspace,
        )

        return self.handler.get_integrations(
            application=application, base_queryset=user_integrations
        )

    def create_integration(
        self,
        user: AbstractUser,
        integration_type: IntegrationType,
        application: Application,
        before: Optional[Integration] = None,
        **kwargs,
    ) -> Integration:
        """
        Creates a new integration for a application given the user permissions.

        :param user: The user trying to create the integration.
        :param integration_type: The type of the integration.
        :param application: The application the integration exists in.
        :param before: If set, the new integration is inserted before this integration.
        :param kwargs: Additional attributes of the integration.
        :return: The created integration.
        """

        operation_name, context = self._get_operation_and_context(
            application,
            CreateIntegrationOperationType.type,
            CreateIntegrationWorkspaceOperationType.type,
        )

        CoreHandler().check_permissions(
            user,
            operation_name,
            workspace=application.workspace,
            context=context,
        )

        prepared_values = integration_type.prepare_values(
            kwargs, user, application=application
        )

        try:
            new_integration = self.handler.create_integration(
                integration_type, application, before=before, **prepared_values
            )
        except CannotCalculateIntermediateOrder:
            self.recalculate_full_orders(user, application)
            # If the `find_intermediate_order` fails with a
            # `CannotCalculateIntermediateOrder`, it means that it's not possible
            # calculate an intermediate fraction. Therefore, must reset all the
            # orders of the integrations (while respecting their original order),
            # so that we can then can find the fraction any many more after.
            before.refresh_from_db()
            new_integration = self.handler.create_integration(
                integration_type, application, before=before, **prepared_values
            )

        integration_created.send(
            self,
            integration=new_integration,
            user=user,
            before_id=before.id if before else None,
        )

        return new_integration

    def _check_secret_dependencies(
        self,
        integration: IntegrationForUpdate,
        integration_type: IntegrationType,
        values: Dict[str, Any],
    ):
        """
        Raises if a request-target field is being changed without the credential
        it protects being supplied in the same request. A secret that is not
        stored is skipped, so an integration that authenticates anonymously can
        still change its host.
        """

        dropped = integration_type.get_dropped_secrets(values, integration)
        for secret, targets in integration_type.secret_field_dependencies.items():
            if (
                not getattr(integration, secret, None)
                or secret in values
                or secret in dropped
            ):
                continue

            check_secret_targets_unchanged(
                secret,
                targets,
                values,
                lambda target: getattr(integration, target),
            )

    def update_integration(
        self,
        user: AbstractUser,
        integration: IntegrationForUpdate,
        **kwargs,
    ) -> UpdatedIntegration:
        """
        Updates and integration with values. Will also check if the values are allowed
        to be set on the integration first.

        An `application_id` other than the integration's moves it to that
        application. That's how it's promoted to the shared application of its
        workspace, and how undoing the promotion moves it back. Moving it also
        needs the permission to create an integration in that application.

        :param user: The user trying to update the integration.
        :param integration: The integration that should be updated.
        :param kwargs: Additional attributes of the integration.
        :return: The updated integration together with the values that changed.
        :raises IntegrationCredentialRequired: When a request-target field changes
            without its credential.
        :raises ApplicationDoesNotExist: When the application to move it to
            doesn't exist.
        :raises IntegrationCannotMoveToApplication: When it can't move to that
            application.
        """

        self.check_integration_permission(
            user,
            integration,
            UpdateIntegrationOperationType.type,
            UpdateWorkspaceIntegrationOperationType.type,
        )

        application_id = kwargs.pop("application_id", None)
        target_application = None
        if application_id is not None and application_id != integration.application_id:
            target_application = CoreHandler().get_application(application_id)
            operation_name, context = self._get_operation_and_context(
                target_application,
                CreateIntegrationOperationType.type,
                CreateIntegrationWorkspaceOperationType.type,
            )
            CoreHandler().check_permissions(
                user,
                operation_name,
                workspace=target_application.workspace,
                context=context,
            )

        integration_type = integration.get_type()

        self._check_secret_dependencies(integration, integration_type, kwargs)

        # Capture the original and new values (in the service-level vocabulary, so
        # FK fields are stored as their ids) before `prepare_values` mutates them, so
        # the update can be undone/redone.
        original_values, new_values = extract_undo_redo_values(
            integration, kwargs, integration_type.get_action_log_excluded_fields()
        )

        if target_application is not None:
            original_values["application_id"] = integration.application_id
            new_values["application_id"] = target_application.id
            integration_type.before_application_change(
                integration, target_application, user
            )

        prepared_values = integration_type.prepare_values(
            kwargs, user, application=integration.application, instance=integration
        )

        integration = self.handler.update_integration(
            integration_type,
            integration,
            application=target_application,
            **prepared_values,
        )

        integration_updated.send(self, integration=integration, user=user)

        return UpdatedIntegration(integration, original_values, new_values)

    def delete_integration(self, user: AbstractUser, integration: IntegrationForUpdate):
        """
        Deletes an integration.

        :param user: The user trying to delete the integration.
        :param integration: The to-be-deleted integration.
        """

        application = integration.application

        self.check_integration_permission(
            user,
            integration,
            DeleteIntegrationOperationType.type,
            DeleteWorkspaceIntegrationOperationType.type,
        )

        # Soft-delete (trash) the integration so it can be restored via undo. The
        # `integration_deleted` realtime signal is emitted by the trashable item type.
        # A workspace integration is trashed in the workspace, so it's listed and
        # emptied with the workspace's trash, never with the shared application's.
        trash_application = (
            None if self.handler.is_shared_application(application) else application
        )
        TrashHandler.trash(user, application.workspace, trash_application, integration)

    def move_integration(
        self,
        user: AbstractUser,
        integration: IntegrationForUpdate,
        before: Optional[Integration] = None,
    ) -> Integration:
        """
        Moves an integration in the application before another integration. If the
        `before` integration is omitted the integration is moved at the end of the
        application.

        :param user: The user who move the integration.
        :param integration: The integration we want to move.
        :param before: The integration before which we want to move the given
            integration.
        :return: The integration with an updated order.
        """

        workspace = integration.application.workspace
        if self.handler.is_shared_application(integration.application):
            CoreHandler().check_permissions(
                user,
                OrderIntegrationsWorkspaceOperationType.type,
                workspace=workspace,
                context=workspace,
            )
        else:
            CoreHandler().check_permissions(
                user,
                UpdateIntegrationOperationType.type,
                workspace=workspace,
                context=integration,
            )

        # Check we are on the same application.
        if before and integration.application_id != before.application_id:
            raise IntegrationNotInSameApplication()

        try:
            integration = self.handler.move_integration(integration, before=before)
        except CannotCalculateIntermediateOrder:
            # If it's failing, we need to recalculate all orders then move again.
            self.recalculate_full_orders(user, integration.application)
            # Refresh the before integration as the order might have changed.
            before.refresh_from_db()
            integration = self.handler.move_integration(integration, before=before)

        integration_moved.send(self, integration=integration, before=before, user=user)

        return integration

    def recalculate_full_orders(self, user: AbstractUser, application: Application):
        """
        Recalculates the order to whole numbers of all integrations of the given
        application and send a signal.
        """

        self.handler.recalculate_full_orders(application)

        integration_orders_recalculated.send(self, application=application)
