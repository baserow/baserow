from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext_lazy as _

from baserow.core.action.registries import ActionType, ActionTypeDescription
from baserow.core.action.scopes import ApplicationActionScopeType

from .integration_types import OAuthAccountIntegrationTypeMixin
from .models import OAuthAccountIntegrationMixin
from .service import CompletedSignIn, OAuthAccountService

OAUTH_ACCOUNT_ACTION_CONTEXT = _(
    'in application "%(application_name)s" (%(application_id)s).'
)


def _register(
    action_type: type[ActionType],
    user: AbstractUser,
    integration: OAuthAccountIntegrationMixin,
    integration_type: OAuthAccountIntegrationTypeMixin,
) -> None:
    application = integration.application
    action_type.register_action(
        user=user,
        params=action_type.Params(
            integration_id=integration.id,
            integration_name=integration.name,
            integration_type=integration_type.type,
            application_id=application.id,
            application_name=application.name,
        ),
        scope=ApplicationActionScopeType.value(application.id),
        workspace=application.workspace,
    )


class ConnectOAuthAccountActionType(ActionType):
    """
    Signs in to a provider for an integration. Creating one this way is logged
    as an ordinary, undoable integration creation; connecting an existing one
    again is logged here, and isn't undoable: the old tokens are gone.
    """

    type = "connect_oauth_account"
    description = ActionTypeDescription(
        _("Connect account"),
        _(
            'Account connected to integration "%(integration_name)s" '
            "(%(integration_id)s)"
        ),
        OAUTH_ACCOUNT_ACTION_CONTEXT,
    )
    analytics_params = ["integration_id", "integration_type", "application_id"]

    @dataclass
    class Params:
        integration_id: int
        integration_name: str
        integration_type: str
        application_id: int
        application_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        integration_type: OAuthAccountIntegrationTypeMixin,
        state: str,
        code: str,
        error: str = "",
        error_description: str = "",
    ) -> CompletedSignIn:
        """
        :param user: Who finishes the sign-in.
        :param integration_type: The integration type it signs in for.
        :param state: The state the provider redirected back with.
        :param code: The authorization code, empty when there's an error.
        :param error: The OAuth error the provider redirected back with.
        :param error_description: Its description.
        :return: The integration, and whether it was created.
        """

        # The token exchange happens outside a transaction.
        completed = OAuthAccountService(integration_type).complete_sign_in(
            user, state, code, error, error_description
        )
        if not completed.created:
            with transaction.atomic():
                _register(cls, user, completed.integration, integration_type)
        return completed

    @classmethod
    def scope(cls, application_id: int) -> str:
        return ApplicationActionScopeType.value(application_id)


class DisconnectOAuthAccountActionType(ActionType):
    """Forgets the tokens of an integration. Audited, not undoable."""

    type = "disconnect_oauth_account"
    description = ActionTypeDescription(
        _("Disconnect account"),
        _(
            'Account disconnected from integration "%(integration_name)s" '
            "(%(integration_id)s)"
        ),
        OAUTH_ACCOUNT_ACTION_CONTEXT,
    )
    analytics_params = ["integration_id", "integration_type", "application_id"]

    @dataclass
    class Params:
        integration_id: int
        integration_name: str
        integration_type: str
        application_id: int
        application_name: str

    @classmethod
    def do(
        cls,
        user: AbstractUser,
        integration_type: OAuthAccountIntegrationTypeMixin,
        integration_id: int,
    ) -> OAuthAccountIntegrationMixin:
        """
        :param user: Who disconnects the account.
        :param integration_type: The integration's type.
        :param integration_id: The integration.
        :return: The integration.
        """

        with transaction.atomic():
            integration = OAuthAccountService(integration_type).disconnect(
                user, integration_id
            )
            _register(cls, user, integration, integration_type)
        return integration

    @classmethod
    def scope(cls, application_id: int) -> str:
        return ApplicationActionScopeType.value(application_id)
