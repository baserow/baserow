from typing import List, Optional

from django.contrib.auth.models import AbstractUser

from baserow.core.exceptions import CannotCalculateIntermediateOrder
from baserow.core.handler import CoreHandler
from baserow.core.integrations.exceptions import IntegrationNotInSameApplication
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import (
    CreateIntegrationOperationType,
    DeleteIntegrationOperationType,
    ListIntegrationsApplicationOperationType,
    ReadIntegrationOperationType,
    UpdateIntegrationOperationType,
)
from baserow.core.integrations.registries import IntegrationType
from baserow.core.integrations.signals import (
    integration_created,
    integration_moved,
    integration_orders_recalculated,
    integration_updated,
)
from baserow.core.integrations.types import IntegrationForUpdate, UpdatedIntegration
from baserow.core.models import Application
from baserow.core.trash.handler import TrashHandler
from baserow.core.utils import extract_undo_redo_values


class IntegrationService:
    def __init__(self):
        self.handler = IntegrationHandler()

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

        CoreHandler().check_permissions(
            user,
            ListIntegrationsApplicationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        user_integrations = CoreHandler().filter_queryset(
            user,
            ListIntegrationsApplicationOperationType.type,
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

        CoreHandler().check_permissions(
            user,
            CreateIntegrationOperationType.type,
            workspace=application.workspace,
            context=application,
        )

        prepared_values = integration_type.prepare_values(kwargs, user)

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

    def update_integration(
        self, user: AbstractUser, integration: IntegrationForUpdate, **kwargs
    ) -> UpdatedIntegration:
        """
        Updates and integration with values. Will also check if the values are allowed
        to be set on the integration first.

        :param user: The user trying to update the integration.
        :param integration: The integration that should be updated.
        :param values: The values that should be set on the integration.
        :param kwargs: Additional attributes of the integration.
        :return: The updated integration together with the values that changed.
        """

        CoreHandler().check_permissions(
            user,
            UpdateIntegrationOperationType.type,
            workspace=integration.application.workspace,
            context=integration,
        )

        integration_type = integration.get_type()

        # Capture the original and new values (in the service-level vocabulary, so
        # FK fields are stored as their ids) before `prepare_values` mutates them, so
        # the update can be undone/redone.
        original_values, new_values = extract_undo_redo_values(
            integration, kwargs, integration_type.sensitive_fields
        )

        prepared_values = integration_type.prepare_values(kwargs, user)

        integration = self.handler.update_integration(
            integration_type, integration, **prepared_values
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

        CoreHandler().check_permissions(
            user,
            DeleteIntegrationOperationType.type,
            workspace=application.workspace,
            context=integration,
        )

        # Soft-delete (trash) the integration so it can be restored via undo. The
        # `integration_deleted` realtime signal is emitted by the trashable item type.
        TrashHandler.trash(user, application.workspace, application, integration)

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

        CoreHandler().check_permissions(
            user,
            UpdateIntegrationOperationType.type,
            workspace=integration.application.workspace,
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
