"""
The provider adapter: the only provider-specific code an OAuth account
integration needs, besides its services. It signs in with the authorization
code flow and PKCE as a confidential client, then refreshes tokens.

The standard parts of OAuth 2.0 are implemented here; a provider supplies its
endpoints, how it tells who signed in, and how its errors read. The class
attributes marked "behaviour flag" are product decisions the base supports
either way, so they can be changed for every provider at once.
"""

import base64
import hashlib
import json
import secrets
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from django.conf import settings
from django.utils import timezone

from loguru import logger
from requests import exceptions as request_exceptions

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.integrations.utils import send_http_request
from baserow.core.services.exceptions import (
    RedirectNotAllowedDispatchException,
    ResponseTooLargeDispatchException,
)

from .exceptions import (
    ClientRejected,
    OAuthFailed,
    ProviderUnavailable,
    ReconnectRequired,
    SignInCancelled,
)

if TYPE_CHECKING:
    from .models import OAuthAccountIntegrationMixin

# Every provider's popup comes back to this frontend page, which hands the code
# to Baserow with the person's own session, so only they can finish their
# sign-in. `{type}` is the integration type.
REDIRECT_PATH = "/integrations/{type}/oauth-callback"

# What a failed request to a provider may raise on the way.
REQUEST_EXCEPTIONS = (
    request_exceptions.RequestException,
    UnacceptableAddressException,
    ResponseTooLargeDispatchException,
    RedirectNotAllowedDispatchException,
)


@dataclass(frozen=True)
class OAuthClient:
    """The OAuth client a sign-in goes through."""

    client_id: str
    client_secret: str

    @property
    def fingerprint(self) -> str:
        """
        Tells clients apart without storing the secret: a sign-in started with
        one client can't finish with another.
        """

        return hashlib.sha256(
            f"{self.client_id}\0{self.client_secret}".encode()
        ).hexdigest()


@dataclass
class TokenSet:
    """What a token endpoint answered."""

    access_token: str
    refresh_token: str
    expires_at: datetime
    # What was granted, normalized. Empty when the provider didn't say.
    scopes: list[str]
    # The id token's claims, when the provider sent one.
    claims: dict[str, Any] = field(default_factory=dict)


@dataclass
class AccountIdentity:
    """Who signed in."""

    account_id: str
    email: str = ""
    name: str = ""
    # The provider's own fields to store, e.g. a tenant id. Each must be one of
    # the model's `extra_connection_fields`.
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class Authorization:
    """Where to send the person, and the PKCE verifier to keep."""

    url: str
    code_verifier: str


class TokenEndpointError(Exception):
    """
    The token endpoint answered with an OAuth error.

    :param error: The OAuth `error`.
    :param payload: The whole answer, for the provider's own error codes. Never
        shown: it may repeat what was sent.
    """

    def __init__(self, error: str, payload: dict):
        self.error = error
        self.payload = payload
        super().__init__(error)


def decode_id_token_claims(id_token: str) -> dict[str, Any]:
    """
    The claims of an id token. It came straight from the provider's token
    endpoint over TLS, so its signature doesn't need checking (OpenID Connect
    Core 3.1.3.7).

    :param id_token: The id token.
    :return: Its claims, empty when it can't be read.
    """

    try:
        payload = id_token.split(".")[1]
        payload += "=" * (-len(payload) % 4)
        claims = json.loads(base64.urlsafe_b64decode(payload))
    except (IndexError, ValueError, TypeError):
        return {}
    return claims if isinstance(claims, dict) else {}


def pkce_challenge(verifier: str) -> str:
    return (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .rstrip(b"=")
        .decode()
    )


class OAuthProvider(ABC):
    """
    How to sign in to one provider. One instance per integration type, set as
    the type's `provider`.
    """

    name: str = ""
    """The provider's name, for messages and default integration names."""

    base_scopes: list[str] = []
    """Asked for on every sign-in: who the account is, and a refresh token."""

    scopes_case_sensitive: bool = True
    """Whether two scopes differing only in case are different scopes."""

    request_deadline_seconds: int = 30
    """Longest a request to the token endpoint may take."""

    refresh_margin_seconds: int = 300
    """Refresh a token this many seconds before it expires."""

    default_token_lifetime_seconds: int = 3600
    """Assumed for an access token the provider gives no lifetime for."""

    reconnect_errors: frozenset[str] = frozenset(
        {"invalid_grant", "interaction_required", "consent_required", "login_required"}
    )
    """Refresh errors that mean the account must sign in again."""

    # Behaviour flags. Until the product decides otherwise, every provider
    # behaves the same way; see the OAuth account docs.

    allow_account_switch: bool = True
    """
    Behaviour flag. Whether reconnecting may sign in as another account than
    the one connected. When it's False, it fails with `AccountMismatch`.
    """

    keep_connection_in_duplicates: bool = True
    """
    Behaviour flag. Whether a duplicate keeps the connection while whoever
    connected it is a member of the workspace it's in.
    """

    keep_connection_in_published_copies: bool = True
    """
    Behaviour flag. Whether a published copy gets a copy of the tokens, so it
    keeps working until it's published again (ADR 016 §4).
    """

    # The OAuth client.

    def get_client(
        self, integration: "OAuthAccountIntegrationMixin | None" = None
    ) -> OAuthClient | None:
        """
        The client to sign in through. The default is the installation's own,
        from `get_instance_client`. A provider that lets an integration bring
        its own client returns it here for that integration.

        :param integration: The integration, None for one a sign-in creates.
        :return: The client, None when there's none.
        """

        return self.get_instance_client()

    def get_instance_client(self) -> OAuthClient | None:
        """
        :return: The client the installation configured, None when it has
            none.
        """

        return None

    def is_configured(
        self, integration: "OAuthAccountIntegrationMixin | None" = None
    ) -> bool:
        client = self.get_client(integration)
        return bool(client and client.client_id and client.client_secret)

    def get_redirect_uri(self, integration_type: str) -> str:
        return settings.PUBLIC_WEB_FRONTEND_URL.rstrip("/") + REDIRECT_PATH.format(
            type=integration_type
        )

    # Endpoints.

    @abstractmethod
    def get_authorization_endpoint(self, client: OAuthClient) -> str:
        """The URL people sign in at."""

    @abstractmethod
    def get_token_endpoint(self, client: OAuthClient) -> str:
        """The URL codes and refresh tokens are exchanged at."""

    @abstractmethod
    def identify(
        self, client: OAuthClient, token_set: TokenSet, deadline: float
    ) -> AccountIdentity:
        """
        Who signed in, from the id token's claims or the provider's userinfo
        endpoint. Only identities the provider verified count.

        :param client: The client the sign-in went through.
        :param token_set: What the code was exchanged for.
        :param deadline: The `time.monotonic()` a request must be over by.
        :raises OAuthFailed: When the provider didn't say who signed in.
        :return: The account.
        """

    # Scopes.

    def normalize_scope(self, scope: str) -> str:
        """:return: The scope as stored and compared."""

        return scope

    def normalize_scopes(self, scopes) -> list[str]:
        """
        :param scopes: Scopes as a space separated string or a list.
        :return: Their normalized names, without duplicates, sorted.
        """

        if isinstance(scopes, str):
            scopes = scopes.split()
        if not isinstance(scopes, (list, tuple, set)):
            scopes = []
        result = {}
        for scope in scopes:
            if not isinstance(scope, str) or not scope.strip():
                continue
            name = self.normalize_scope(scope.strip())
            key = name if self.scopes_case_sensitive else name.lower()
            result.setdefault(key, name)
        return sorted(result.values(), key=str.lower)

    def missing_scopes(self, granted, required) -> list[str]:
        """
        :param granted: What the account granted.
        :param required: What a service needs.
        :return: The required scopes that weren't granted.
        """

        def key(scope):
            return scope if self.scopes_case_sensitive else scope.lower()

        have = {key(scope) for scope in self.normalize_scopes(granted)}
        return [
            scope for scope in self.normalize_scopes(required) if key(scope) not in have
        ]

    # Signing in.

    def build_authorization(
        self,
        client: OAuthClient,
        redirect_uri: str,
        state: str,
        scopes: list[str],
        login_hint: str = "",
    ) -> Authorization:
        """
        :param client: The client to sign in through.
        :param redirect_uri: Where the provider sends the person back.
        :param state: Binds the redirect back to this sign-in.
        :param scopes: The permissions to ask for, base ones included.
        :param login_hint: The account to suggest, on a reconnect.
        :return: Where to send the person, and the PKCE verifier to keep.
        """

        verifier = secrets.token_urlsafe(64)
        params = {
            "client_id": client.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": " ".join(scopes),
            "state": state,
            "code_challenge": pkce_challenge(verifier),
            "code_challenge_method": "S256",
            **self.get_extra_authorization_params(),
        }
        if login_hint:
            params["login_hint"] = login_hint
        return Authorization(
            url=f"{self.get_authorization_endpoint(client)}?{urlencode(params)}",
            code_verifier=verifier,
        )

    def get_extra_authorization_params(self) -> dict[str, str]:
        """
        The provider's own authorization parameters, e.g. to get a refresh
        token or let a second account be picked.
        """

        return {}

    def classify_callback_error(
        self,
        error: str,
        error_description: str,
        client: OAuthClient,
        scopes: list[str],
    ) -> Exception:
        """
        Turn the error the provider redirected back with into one the person
        can act on. Providers add their own codes, e.g. "an admin must approve
        this app" (`AdminConsentRequired`) or `TenantNotAllowed`.

        :param error: The OAuth error.
        :param error_description: The provider's description. Never shown.
        :param client: The client the sign-in went through.
        :param scopes: What it asked for.
        :return: The exception to raise.
        """

        if error == "access_denied":
            return SignInCancelled()
        return OAuthFailed(f"{self.name} refused the sign-in. Try again.")

    def admin_consent_url(self, client: OAuthClient, scopes: list[str]) -> str:
        """
        :return: Where an admin approves Baserow for their organisation, empty
            when the provider has no such page.
        """

        return ""

    def exchange_code(
        self,
        client: OAuthClient,
        redirect_uri: str,
        code: str,
        code_verifier: str,
        scopes: list[str],
        deadline: float | None = None,
    ) -> TokenSet:
        """
        Exchange an authorization code for tokens.

        :raises ClientRejected: When the client itself is refused.
        :raises OAuthFailed: When the provider refuses or can't be reached.
        :return: The tokens.
        """

        try:
            return self.request_token(
                client,
                {
                    "grant_type": "authorization_code",
                    "code": code,
                    "redirect_uri": redirect_uri,
                    "code_verifier": code_verifier,
                    **self.get_extra_code_params(scopes),
                },
                deadline=deadline,
            )
        except TokenEndpointError as exc:
            raise self.classify_token_error(
                exc,
                OAuthFailed("The sign-in expired or was refused. Try again."),
            ) from exc

    def get_extra_code_params(self, scopes: list[str]) -> dict[str, str]:
        """The provider's own parameters of a code exchange."""

        return {}

    def refresh(
        self,
        client: OAuthClient,
        refresh_token: str,
        scopes: list[str],
        deadline: float | None = None,
    ) -> TokenSet:
        """
        Get a new access token. A provider may send a new refresh token too,
        which must be stored.

        :param client: The client.
        :param refresh_token: The stored refresh token.
        :param scopes: The scopes the account granted.
        :param deadline: The `time.monotonic()` the refresh must be over by.
        :raises ReconnectRequired: When the refresh token is no good.
        :raises ClientRejected: When the client itself is refused.
        :raises OAuthFailed: When the provider can't be reached or refuses for
            another reason.
        :return: The tokens.
        """

        try:
            return self.request_token(
                client,
                {
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    **self.get_extra_refresh_params(scopes),
                },
                deadline=deadline,
            )
        except TokenEndpointError as exc:
            if exc.error == "temporarily_unavailable":
                raise ProviderUnavailable(
                    f"{self.name} could not be reached. Try again later."
                ) from exc
            if exc.error in self.reconnect_errors:
                raise ReconnectRequired() from exc
            raise self.classify_token_error(
                exc, OAuthFailed(f"{self.name} refused to refresh the token.")
            ) from exc

    def get_extra_refresh_params(self, scopes: list[str]) -> dict[str, str]:
        """The provider's own parameters of a refresh."""

        return {}

    def classify_token_error(
        self, exc: TokenEndpointError, fallback: Exception
    ) -> Exception:
        """
        :param exc: The token endpoint's error.
        :param fallback: What to raise when it means nothing in particular.
        :return: The exception to raise.
        """

        if self.is_client_rejected(exc):
            logger.warning(
                "{} refused the OAuth client of this installation.", self.name
            )
            return ClientRejected()
        return fallback

    def is_client_rejected(self, exc: TokenEndpointError) -> bool:
        """Whether the error means the client itself, e.g. its secret, is bad."""

        return exc.error == "invalid_client"

    def request_token(
        self, client: OAuthClient, data: dict[str, str], deadline: float | None
    ) -> TokenSet:
        """
        A request to the token endpoint.

        :param client: The client, sent in the body.
        :param data: The grant's own fields.
        :param deadline: The `time.monotonic()` the request must be over by,
            when sooner than `request_deadline_seconds` from now.
        :raises TokenEndpointError: When the provider refuses with an OAuth
            error.
        :raises ProviderUnavailable: When it can't be reached or is busy.
        :raises OAuthFailed: When it answers something else.
        :return: The tokens.
        """

        body = {
            **data,
            "client_id": client.client_id,
            "client_secret": client.client_secret,
        }
        end = time.monotonic() + self.request_deadline_seconds
        if deadline is not None:
            end = min(end, deadline)
        try:
            response = send_http_request(
                method="POST",
                url=self.get_token_endpoint(client),
                data=body,
                deadline=end,
                # The token endpoint answers directly, so the secret and the
                # codes only go to the address that was configured.
                allow_redirects=False,
                send_netrc_credentials=False,
            )
        except REQUEST_EXCEPTIONS as exc:
            # Not `str(exc)`: the request carries the client secret.
            raise ProviderUnavailable(
                f"{self.name} could not be reached. Try again later."
            ) from exc

        try:
            payload = response.json()
        except ValueError:
            payload = None
        if not isinstance(payload, dict):
            payload = {}

        if response.status_code == 429 or response.status_code >= 500:
            # Busy or down, whatever the body says: the tokens may still be
            # good, so they're kept and the request can be tried again.
            logger.info(
                "{} token request failed with status {}",
                self.name,
                response.status_code,
            )
            raise ProviderUnavailable(
                f"{self.name} could not be reached. Try again later."
            )

        if response.status_code != 200:
            error = payload.get("error")
            if isinstance(error, str) and error:
                raise TokenEndpointError(error, payload)
            logger.info(
                "{} token request failed with status {}",
                self.name,
                response.status_code,
            )
            raise OAuthFailed(f"{self.name} refused the request.")

        return self.parse_token_response(payload)

    def parse_token_response(self, payload: dict) -> TokenSet:
        """
        :param payload: A successful answer of the token endpoint.
        :raises OAuthFailed: When it has no access token.
        :return: The tokens.
        """

        access_token = payload.get("access_token")
        if not isinstance(access_token, str) or not access_token:
            raise OAuthFailed(f"{self.name}'s answer is invalid.")
        refresh_token = payload.get("refresh_token")
        try:
            expires_in = int(payload.get("expires_in"))
        except (TypeError, ValueError):
            expires_in = self.default_token_lifetime_seconds
        id_token = payload.get("id_token")
        return TokenSet(
            access_token=access_token,
            refresh_token=refresh_token if isinstance(refresh_token, str) else "",
            expires_at=timezone.now() + timedelta(seconds=expires_in),
            scopes=self.normalize_scopes(payload.get("scope") or ""),
            claims=(
                decode_id_token_claims(id_token) if isinstance(id_token, str) else {}
            ),
        )

    def expires_soon(self, expires_at: datetime | None) -> bool:
        """
        :param expires_at: When an access token expires.
        :return: Whether it should be refreshed now. A token with no expiry is
            refreshed.
        """

        return expires_at is None or (
            expires_at.timestamp() - time.time() < self.refresh_margin_seconds
        )

    def default_integration_name(self, identity: AccountIdentity) -> str:
        """:return: The name of an integration a sign-in creates, unnamed."""

        name = self.name or "Account"
        return (f"{name} ({identity.email})" if identity.email else name)[:255]
