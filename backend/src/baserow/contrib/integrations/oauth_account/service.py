from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.api.sessions import set_untrusted_client_session_id
from baserow.core.exceptions import ApplicationOperationNotSupported
from baserow.core.handler import CoreHandler
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.operations import (
    CreateIntegrationOperationType,
    UpdateIntegrationOperationType,
)
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.signals import integration_updated
from baserow.core.models import Application, Workspace
from baserow.core.registries import application_type_registry
from baserow.core.services.registries import service_type_registry

from .exceptions import (
    OAuthAccountNotConfigured,
    OAuthAccountTypeDoesNotExist,
    OAuthFailed,
    ServiceTypeNotAllowed,
    SignInCancelled,
)
from .handler import OAuthAccountHandler, PendingSignIn
from .integration_types import OAuthAccountIntegrationTypeMixin
from .models import OAuthAccountIntegrationMixin, lock_oauth_integration


@dataclass
class CompletedSignIn:
    integration: OAuthAccountIntegrationMixin
    # True when the sign-in created the integration, False when it connected
    # an existing one again.
    created: bool


def get_oauth_account_integration_type(name: str) -> OAuthAccountIntegrationTypeMixin:
    """
    :param name: An integration type name, from the URL.
    :raises OAuthAccountTypeDoesNotExist: When it isn't an OAuth account type.
    :return: The integration type.
    """

    try:
        integration_type = integration_type_registry.get(name)
    except integration_type_registry.does_not_exist_exception_class as exc:
        raise OAuthAccountTypeDoesNotExist() from exc
    if not isinstance(integration_type, OAuthAccountIntegrationTypeMixin):
        raise OAuthAccountTypeDoesNotExist()
    return integration_type


class OAuthAccountService:
    """
    Signing in to a provider for the integrations of one OAuth account
    integration type, with the permissions checked.
    """

    def __init__(self, integration_type: OAuthAccountIntegrationTypeMixin):
        self.integration_type = integration_type
        self.model = integration_type.model_class
        self.handler = OAuthAccountHandler(integration_type)

    def get_integration_for_update(
        self, user: AbstractUser, integration_id: int
    ) -> OAuthAccountIntegrationMixin:
        """
        :param user: Who asks.
        :param integration_id: The integration.
        :raises IntegrationDoesNotExist: When it doesn't exist or isn't of this
            type.
        :raises PermissionDenied: When the user can't change it.
        :return: The integration.
        """

        integration = IntegrationHandler().get_integration(integration_id).specific
        if type(integration) is not self.model:
            raise IntegrationDoesNotExist()
        CoreHandler().check_permissions(
            user,
            UpdateIntegrationOperationType.type,
            workspace=integration.application.workspace,
            context=integration,
        )
        return integration

    def get_application_for_create(
        self, user: AbstractUser, application_id: int
    ) -> Application:
        """
        :param user: Who asks.
        :param application_id: Where the integration would be created.
        :raises ApplicationDoesNotExist: When there's no such application.
        :raises PermissionDenied: When the user can't create integrations there.
        :raises ApplicationOperationNotSupported: When it doesn't hold
            integrations of this type.
        :return: The application.
        """

        application = CoreHandler().get_application(application_id)
        CoreHandler().check_permissions(
            user,
            CreateIntegrationOperationType.type,
            workspace=application.workspace,
            context=application,
        )
        application_type = application_type_registry.get_by_model(
            application.specific_class
        )
        if not application_type.supports_integration_type(self.integration_type):
            raise ApplicationOperationNotSupported()
        return application

    def get_scopes_for_service_types(
        self, service_types: list[str], workspace: Workspace
    ) -> list[str]:
        """
        The scopes a sign-in asks for come from the service types it's for,
        never from the request.

        :param service_types: Names of service types using this integration
            type.
        :param workspace: The workspace the integration is in.
        :raises ServiceTypeNotAllowed: When one doesn't use this integration
            type, or the workspace can't use it.
        :return: The scopes they need.
        """

        from .service_types import OAuthAccountServiceTypeMixin

        scopes = []
        for name in service_types:
            try:
                service_type = service_type_registry.get(name)
            except service_type_registry.does_not_exist_exception_class as exc:
                raise ServiceTypeNotAllowed() from exc
            if (
                not isinstance(service_type, OAuthAccountServiceTypeMixin)
                or service_type.integration_type != self.integration_type.type
                or service_type.is_deactivated(workspace)
            ):
                raise ServiceTypeNotAllowed()
            scopes += service_type.required_scopes
        return scopes

    def start_sign_in(
        self,
        user: AbstractUser,
        service_types: list[str],
        application_id: int | None = None,
        integration_id: int | None = None,
        name: str = "",
    ) -> str:
        """
        Start signing in, to create an integration in an application, or to
        connect an existing one again. Permissions are checked now, so nobody
        signs in only to be refused at the end, and again when the sign-in
        completes.

        :param user: Who signs in.
        :param service_types: The service types the account is connected for.
        :param application_id: Creates an integration in this application.
        :param integration_id: Or connects this integration again.
        :param name: The name of the integration to create.
        :raises OAuthAccountNotConfigured: When there's no client.
        :return: Where to send the person.
        """

        integration = None
        if integration_id is not None:
            integration = self.get_integration_for_update(user, integration_id)
            workspace = integration.application.workspace
        else:
            application = self.get_application_for_create(user, application_id)
            workspace = application.workspace
        if not self.integration_type.provider.is_configured(integration):
            raise OAuthAccountNotConfigured()
        scopes = self.get_scopes_for_service_types(service_types, workspace)
        return self.handler.start_sign_in(
            user,
            scopes,
            application_id=application_id,
            integration=integration,
            name=name,
        )

    def complete_sign_in(
        self,
        user: AbstractUser,
        state: str,
        code: str,
        error: str = "",
        error_description: str = "",
    ) -> CompletedSignIn:
        """
        Finish a sign-in when the provider redirects back. Only the person who
        started it can finish it, so a sign-in link opened by someone else can't
        connect their account. The provider is called outside any transaction;
        only storing the result is.

        :param user: Who finishes the sign-in.
        :param state: The state the provider redirected back with.
        :param code: The authorization code, empty when there's an error.
        :param error: The OAuth error the provider redirected back with.
        :param error_description: Its description.
        :raises OAuthStateInvalid: When the state is unknown, expired, someone
            else's, or the integration or its client changed since.
        :raises SignInCancelled: When the person declined.
        :raises OAuthFailed: When the exchange fails.
        :return: The integration, and whether it was created.
        """

        pending = self.handler.pop_sign_in(state, user)
        if pending.web_socket_id:
            # The tab that started the sign-in stores what the response says;
            # the real-time update is for everyone else.
            user.web_socket_id = pending.web_socket_id
        if pending.client_session_id:
            # So the creation is undone from that tab, not the popup.
            set_untrusted_client_session_id(user, pending.client_session_id)

        # Checked again before the code is used: access may have changed.
        integration = self._check_pending_permissions(user, pending)
        client = self.handler.check_client(pending, integration)
        self.handler.raise_for_sign_in_error(pending, client, error, error_description)
        if not code:
            raise SignInCancelled()
        signed_in = self.handler.exchange_code(pending, client, code)

        with transaction.atomic():
            if pending.integration_id is not None:
                self.get_integration_for_update(user, pending.integration_id)
                locked = lock_oauth_integration(self.model, pending.integration_id)
                # The client may have been changed while the provider answered.
                self.handler.check_client(pending, locked)
                self.handler.store_sign_in(locked, signed_in, user, pending)
                integration = self.notify_updated(user, locked.id)
                return CompletedSignIn(integration=integration, created=False)

            from baserow.core.integrations.actions import CreateIntegrationActionType

            application = self.get_application_for_create(user, pending.application_id)
            name = (
                pending.name
                or self.integration_type.provider.default_integration_name(
                    signed_in.identity
                )
            )
            integration = CreateIntegrationActionType.do(
                user, self.integration_type, application, name=name
            )
            # The same instance the creation is broadcast with, on commit, so
            # other editors see it connected.
            self.handler.store_sign_in(integration, signed_in, user, pending)
            return CompletedSignIn(integration=integration, created=True)

    def _check_pending_permissions(
        self, user: AbstractUser, pending: PendingSignIn
    ) -> OAuthAccountIntegrationMixin | None:
        """
        :return: The integration a reconnect is for, None for a creation.
        """

        if pending.integration_id is not None:
            return self.get_integration_for_update(user, pending.integration_id)
        if pending.application_id is not None:
            self.get_application_for_create(user, pending.application_id)
            return None
        raise OAuthFailed("This sign-in has nothing to connect.")

    def disconnect(
        self, user: AbstractUser, integration_id: int
    ) -> OAuthAccountIntegrationMixin:
        """
        Forget the account's tokens. Published copies keep theirs until they're
        published again.

        :param user: Who asks.
        :param integration_id: The integration.
        :return: The integration.
        """

        with transaction.atomic():
            integration = self.get_integration_for_update(user, integration_id)
            self.handler.disconnect(integration)
            return self.notify_updated(user, integration_id)

    def notify_updated(
        self, user: AbstractUser, integration_id: int
    ) -> OAuthAccountIntegrationMixin:
        """
        Read the integration again and tell other editors it changed.

        :param user: Who changed it.
        :param integration_id: The integration.
        :return: The integration.
        """

        integration = IntegrationHandler().get_integration(integration_id).specific
        integration_updated.send(self, integration=integration, user=user)
        return integration
