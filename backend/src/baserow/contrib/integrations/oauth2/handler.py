from datetime import timedelta
from typing import Optional
from urllib.parse import urljoin

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core import signing
from django.urls import reverse
from django.utils import timezone

from baserow.core.handler import CoreHandler
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.models import Integration
from baserow.core.integrations.operations import UpdateIntegrationOperationType
from baserow.core.services.exceptions import (
    RemoteRefusedDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)

from .exceptions import (
    OAuth2IntegrationNotConfigured,
    OAuth2InvalidReturnUrl,
    OAuth2InvalidState,
    OAuth2TokenRequestFailed,
)
from .models import TOKEN_FIELDS

STATE_SALT = "baserow.integrations.oauth2"
# How long a consent screen may stay open before the callback is refused.
STATE_MAX_AGE_SECONDS = 15 * 60
# Refresh ahead of expiry so a token is never handed out about to lapse.
ACCESS_TOKEN_MARGIN = timedelta(seconds=60)


class OAuth2IntegrationHandler:
    """
    Connects an OAuth2 integration to an account: builds the consent URL with
    a signed state, finishes the exchange when the provider calls back, and
    hands services a valid access token, refreshing it when needed.
    """

    def get_redirect_uri(self) -> str:
        # One callback for every provider; the state says which integration.
        return urljoin(
            settings.OAUTH_BACKEND_URL, reverse("api:integrations:oauth2_callback")
        )

    def get_authorization_url(
        self, user: AbstractUser, integration: Integration, return_url: str
    ) -> str:
        """
        :raises OAuth2IntegrationNotConfigured: Without a client id and secret.
        :raises OAuth2InvalidReturnUrl: When the page to return to is not ours.
        """

        CoreHandler().check_permissions(
            user,
            UpdateIntegrationOperationType.type,
            workspace=integration.application.workspace,
            context=integration,
        )
        if not integration.client_id or not integration.client_secret:
            raise OAuth2IntegrationNotConfigured()
        # The callback redirects the browser here, so only this frontend.
        if not return_url.startswith(settings.PUBLIC_WEB_FRONTEND_URL.rstrip("/")):
            raise OAuth2InvalidReturnUrl()
        state = signing.dumps(
            {
                "integration_id": integration.id,
                "user_id": user.id,
                "return_url": return_url,
            },
            salt=STATE_SALT,
        )
        return integration.get_type().build_authorization_url(
            integration, self.get_redirect_uri(), state
        )

    def parse_state(self, state: Optional[str]) -> dict:
        try:
            return signing.loads(
                state or "", salt=STATE_SALT, max_age=STATE_MAX_AGE_SECONDS
            )
        except signing.BadSignature as e:
            raise OAuth2InvalidState() from e

    def complete_authorization(self, code: str, state: str) -> str:
        """
        Trades the code for tokens and stores them on the integration the
        state names. Returns the frontend page to send the browser back to.

        :raises OAuth2InvalidState: When the state does not verify.
        :raises OAuth2TokenRequestFailed: When the provider refuses the code.
        """

        data = self.parse_state(state)
        try:
            integration = IntegrationHandler().get_integration(data["integration_id"])
        except IntegrationDoesNotExist as e:
            raise OAuth2InvalidState() from e
        user = get_user_model().objects.filter(id=data["user_id"]).first()
        if user is None:
            raise OAuth2InvalidState()
        # The person who started the flow must still be allowed to change the
        # integration; the state alone must not grant that.
        CoreHandler().check_permissions(
            user,
            UpdateIntegrationOperationType.type,
            workspace=integration.application.workspace,
            context=integration,
        )
        integration_type = integration.get_type()
        body = integration_type.exchange_code(
            integration, code, self.get_redirect_uri()
        )
        if not body.get("refresh_token") and not integration.refresh_token:
            raise OAuth2TokenRequestFailed(
                "The provider did not issue a refresh token. Remove the app's "
                "access from your account and connect again, so consent is "
                "asked once more."
            )
        integration_type.apply_token_response(integration, body)
        integration.account_email = (
            integration_type.fetch_account_email(integration.access_token) or ""
        )
        integration.save(update_fields=list(TOKEN_FIELDS))
        return data["return_url"]

    def get_access_token(self, integration: Integration) -> str:
        """
        A valid access token for the integration's account, refreshed when
        the stored one is about to expire.

        :raises ServiceImproperlyConfiguredDispatchException: Not connected.
        :raises RemoteRefusedDispatchException: When the refresh is refused,
            which happens once the person revoked the app's access.
        """

        if not integration.refresh_token:
            raise ServiceImproperlyConfiguredDispatchException(
                "This integration is not connected to an account yet. Open the "
                "integration settings and connect it."
            )
        expires_at = integration.access_token_expires_at
        if (
            integration.access_token
            and expires_at is not None
            and expires_at - ACCESS_TOKEN_MARGIN > timezone.now()
        ):
            return integration.access_token
        integration_type = integration.get_type()
        try:
            body = integration_type.refresh_access_token(integration)
        except OAuth2TokenRequestFailed as e:
            raise RemoteRefusedDispatchException(
                f"{e} Reconnect the integration if the account's access was revoked."
            ) from e
        integration_type.apply_token_response(integration, body)
        integration.save(
            update_fields=["access_token", "access_token_expires_at", "refresh_token"]
        )
        return integration.access_token
