import secrets
import time
from dataclasses import asdict, dataclass, fields
from typing import TYPE_CHECKING

from django.contrib.auth.models import AbstractUser
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone

from loguru import logger

from baserow.api.sessions import get_untrusted_client_session_id
from baserow.core.fields import is_unreadable_secret

from .exceptions import (
    AccountMismatch,
    OAuthAccountNotConfigured,
    OAuthFailed,
    OAuthStateInvalid,
    ProviderUnavailable,
    ReconnectRequired,
    ScopesMissing,
)
from .models import TOKEN_FIELDS, OAuthAccountIntegrationMixin, lock_oauth_integration
from .providers import AccountIdentity, OAuthClient, OAuthProvider, TokenSet

if TYPE_CHECKING:
    from .integration_types import OAuthAccountIntegrationTypeMixin

# How long a person has to finish signing in.
OAUTH_STATE_TIMEOUT_SECONDS = 600
OAUTH_STATE_CACHE_KEY = "oauth_account_state:{}"
# One refresh per integration at a time. Outlasts the longest token request,
# so it can't expire while its owner still waits for the provider.
REFRESH_LOCK_KEY = "oauth_account_token_refresh:{}"
REFRESH_LOCK_SECONDS = 35
REFRESH_POLL_SECONDS = 0.2


@dataclass(frozen=True)
class PendingSignIn:
    """A sign-in someone started, kept until the provider redirects back."""

    # The integration type it signs in for. Its complete endpoint only
    # finishes its own sign-ins.
    integration_type: str
    user_id: int
    # Set when the sign-in creates an integration in this application.
    application_id: int | None
    # Set when the sign-in connects this integration again.
    integration_id: int | None
    name: str
    scopes: list[str]
    code_verifier: str
    # The integration's generation when the reconnect started.
    generation: int
    # The client it went through: one changed since can't finish it.
    client_fingerprint: str
    # The browser tab that started it. The sign-in finishes in a popup, so
    # that tab is left out of the real-time update and stores the result
    # itself, once, and its undo stack gets what the sign-in did.
    web_socket_id: str | None
    client_session_id: str | None

    @classmethod
    def from_dict(cls, data: dict) -> "PendingSignIn | None":
        """
        :param data: What was cached.
        :return: The sign-in, or None when it was cached by another version.
        """

        names = {field.name for field in fields(cls)}
        if not isinstance(data, dict) or not names <= data.keys():
            return None
        return cls(**{name: data[name] for name in names})


@dataclass
class SignedIn:
    """What a sign-in got, before it's stored."""

    token_set: TokenSet
    identity: AccountIdentity


def readable(secret: str) -> str:
    """
    :param secret: A stored token.
    :raises ReconnectRequired: When it can't be decrypted. It must not be sent,
        nor taken for a missing one and cleared: the key that reads it may be
        configured again.
    :return: The token.
    """

    if is_unreadable_secret(secret):
        raise ReconnectRequired()
    return secret


class OAuthAccountHandler:
    """
    Signing in, refreshing and signing out the account of an integration of
    one OAuth account integration type. Permissions are checked by the caller.
    """

    def __init__(self, integration_type: "OAuthAccountIntegrationTypeMixin"):
        self.integration_type = integration_type
        self.provider: OAuthProvider = integration_type.provider
        self.model: type[OAuthAccountIntegrationMixin] = integration_type.model_class

    @property
    def redirect_uri(self) -> str:
        return self.provider.get_redirect_uri(self.integration_type.type)

    def get_client(
        self, integration: OAuthAccountIntegrationMixin | None = None
    ) -> OAuthClient:
        """
        :param integration: The integration, None for one a sign-in creates.
        :raises OAuthAccountNotConfigured: When there's no usable client.
        :return: The client to sign in through.
        """

        client = self.provider.get_client(integration)
        if not client or not client.client_id or not client.client_secret:
            raise OAuthAccountNotConfigured()
        return client

    def start_sign_in(
        self,
        user: AbstractUser,
        scopes: list[str],
        application_id: int | None = None,
        integration: OAuthAccountIntegrationMixin | None = None,
        name: str = "",
    ) -> str:
        """
        Remember a sign-in and return where to send the person.

        :param user: Who signs in. Only they can finish it.
        :param scopes: The scopes services need, without the base ones.
        :param application_id: Creates an integration in this application.
        :param integration: Or connects this integration again, keeping the
            scopes it already has.
        :param name: The name of the integration to create.
        :raises OAuthAccountNotConfigured: When there's no client.
        :return: The authorization URL.
        """

        client = self.get_client(integration)
        requested = list(scopes)
        login_hint = ""
        generation = 0
        if integration is not None:
            requested += integration.scopes or []
            login_hint = integration.account_email
            generation = integration.generation
        requested = self.provider.normalize_scopes(
            [*self.provider.base_scopes, *requested]
        )

        state = secrets.token_urlsafe(32)
        authorization = self.provider.build_authorization(
            client, self.redirect_uri, state, requested, login_hint
        )
        pending = PendingSignIn(
            integration_type=self.integration_type.type,
            user_id=user.id,
            application_id=None if integration is not None else application_id,
            integration_id=integration.id if integration is not None else None,
            name=name,
            scopes=requested,
            code_verifier=authorization.code_verifier,
            generation=generation,
            client_fingerprint=client.fingerprint,
            web_socket_id=getattr(user, "web_socket_id", None),
            client_session_id=get_untrusted_client_session_id(user),
        )
        cache.set(
            OAUTH_STATE_CACHE_KEY.format(state),
            asdict(pending),
            OAUTH_STATE_TIMEOUT_SECONDS,
        )
        return authorization.url

    def pop_sign_in(self, state: str, user: AbstractUser) -> PendingSignIn:
        """
        The sign-in a callback belongs to. Each one can be used once, and only
        by the person who started it, for the integration type it started for;
        anyone else's attempt leaves it be.

        :param state: The state the provider redirected back with.
        :param user: Who finishes the sign-in.
        :raises OAuthStateInvalid: When it's unknown, used, expired, someone
            else's or another type's.
        :return: The pending sign-in.
        """

        key = OAUTH_STATE_CACHE_KEY.format(state)
        stored = cache.get(key) if state else None
        pending = PendingSignIn.from_dict(stored) if stored else None
        if (
            pending is None
            or pending.user_id != user.id
            or pending.integration_type != self.integration_type.type
        ):
            raise OAuthStateInvalid()
        # Only the request that deletes it may go on, if two arrive at once.
        if not cache.delete(key):
            raise OAuthStateInvalid()
        return pending

    def raise_for_sign_in_error(
        self,
        pending: PendingSignIn,
        client: OAuthClient,
        error: str,
        error_description: str,
    ) -> None:
        """
        :param pending: The sign-in.
        :param client: Its client.
        :param error: The OAuth error the provider redirected back with, empty
            when there's none.
        :param error_description: Its description. Never shown.
        :raises Exception: What the provider's adapter makes of it.
        """

        if error:
            raise self.provider.classify_callback_error(
                error, error_description or "", client, pending.scopes
            )

    def check_client(
        self,
        pending: PendingSignIn,
        integration: OAuthAccountIntegrationMixin | None,
    ) -> OAuthClient:
        """
        :param pending: The sign-in.
        :param integration: The integration it reconnects, None when it creates
            one.
        :raises OAuthStateInvalid: When the client changed since it started.
        :return: The client.
        """

        client = self.get_client(integration)
        if client.fingerprint != pending.client_fingerprint:
            raise OAuthStateInvalid()
        return client

    def exchange_code(
        self, pending: PendingSignIn, client: OAuthClient, code: str
    ) -> SignedIn:
        """
        Exchange the code and find out who signed in. Never call this inside a
        transaction: it talks to the provider.

        :param pending: The sign-in.
        :param client: Its client.
        :param code: The authorization code.
        :raises OAuthFailed: When the exchange fails, or the provider didn't say
            which account signed in or sent no refresh token.
        :return: The tokens and the account.
        """

        deadline = time.monotonic() + self.provider.request_deadline_seconds
        token_set = self.provider.exchange_code(
            client,
            self.redirect_uri,
            code,
            pending.code_verifier,
            pending.scopes,
            deadline=deadline,
        )
        if not token_set.refresh_token:
            raise OAuthFailed(
                f"{self.provider.name} didn't allow Baserow to stay signed in. "
                "Try again."
            )
        identity = self.provider.identify(client, token_set, deadline)
        if not identity.account_id:
            raise OAuthFailed(
                f"{self.provider.name} didn't say which account signed in. Try again."
            )
        return SignedIn(token_set=token_set, identity=identity)

    def store_sign_in(
        self,
        integration: OAuthAccountIntegrationMixin,
        signed_in: SignedIn,
        user: AbstractUser,
        pending: PendingSignIn,
    ) -> OAuthAccountIntegrationMixin:
        """
        Store a sign-in on the integration, which the caller locked or just
        created, inside a transaction.

        :param integration: The integration.
        :param signed_in: The tokens and the account.
        :param user: Who signed in.
        :param pending: The sign-in. For a reconnect, its generation must still
            be the integration's.
        :raises OAuthStateInvalid: When the account was signed out or signed in
            again since the reconnect started.
        :raises AccountMismatch: When it signed in as another account and the
            provider doesn't allow that.
        :return: The integration.
        """

        if (
            pending.integration_id is not None
            and integration.generation != pending.generation
        ):
            raise OAuthStateInvalid()
        identity = signed_in.identity
        if (
            not self.provider.allow_account_switch
            and integration.account_id
            and integration.account_id != identity.account_id
        ):
            raise AccountMismatch()
        token_set = signed_in.token_set
        integration.account_id = str(identity.account_id)[:255]
        integration.account_email = str(identity.email or "")[:255]
        integration.account_name = str(identity.name or "")[:255]
        for name, value in identity.extra.items():
            if name not in self.model.extra_connection_fields:
                raise ValueError(f"{name} isn't one of the model's connection fields.")
            setattr(integration, name, value)
        # What was granted, which can be less than what was asked for. Only an
        # answer without a list is taken to grant what was asked.
        integration.scopes = token_set.scopes or pending.scopes
        integration.access_token = token_set.access_token
        integration.refresh_token = token_set.refresh_token
        integration.expires_at = token_set.expires_at
        integration.connected_at = timezone.now()
        integration.connected_by = user
        integration.generation += 1
        integration.save(
            update_fields=[*self.model.get_connection_fields(), "generation"]
        )
        return integration

    def disconnect(
        self, integration: OAuthAccountIntegrationMixin
    ) -> OAuthAccountIntegrationMixin:
        """
        Forget the tokens. A reconnect started before can't finish. Only
        forgets them: a delegated token generally can't be revoked alone.

        :param integration: The integration.
        :return: The integration.
        """

        with transaction.atomic():
            locked = lock_oauth_integration(self.model, integration.id)
            cleared = locked.clear_tokens()
            locked.generation += 1
            locked.save(update_fields=[*cleared, "generation"])
        return locked

    def get_access_token(
        self,
        integration: OAuthAccountIntegrationMixin,
        required_scopes: list[str],
        deadline: float | None = None,
    ) -> str:
        """
        A valid access token for the integration's account, refreshed first
        when it expires soon.

        :param integration: The integration, as the caller read it.
        :param required_scopes: What the caller needs the account to have
            granted.
        :param deadline: The `time.monotonic()` a refresh must be over by.
        :raises ReconnectRequired: When the account isn't connected or the
            provider stopped accepting its tokens.
        :raises ScopesMissing: When it didn't grant a required scope.
        :raises ClientRejected: When the client itself is refused.
        :raises OAuthFailed: When the provider can't be reached.
        :return: The access token.
        """

        if not integration.connected:
            raise ReconnectRequired()
        missing = self.provider.missing_scopes(integration.scopes, required_scopes)
        if missing:
            raise ScopesMissing(missing)
        if self.provider.expires_soon(integration.expires_at):
            integration = self.refresh(integration, deadline=deadline)
            # Granted scopes can shrink on a refresh.
            missing = self.provider.missing_scopes(integration.scopes, required_scopes)
            if missing:
                raise ScopesMissing(missing)
        return readable(integration.access_token)

    def refuse_token(
        self,
        integration: OAuthAccountIntegrationMixin,
        token: str,
        deadline: float | None = None,
    ) -> str:
        """
        The provider's API refused an access token (a 401). Refresh it once,
        unless another request stored a newer one meanwhile. A refresh token
        the provider refuses too is cleared.

        :param integration: The integration.
        :param token: The refused access token.
        :param deadline: The `time.monotonic()` the refresh must be over by.
        :raises ReconnectRequired: When it can't be refreshed.
        :raises ClientRejected: When the client itself is refused.
        :raises OAuthFailed: When the provider can't be reached.
        :return: An access token to try again with.
        """

        refreshed = self.refresh(integration, refused_token=token, deadline=deadline)
        return readable(refreshed.access_token)

    def refresh(
        self,
        integration: OAuthAccountIntegrationMixin,
        refused_token: str | None = None,
        deadline: float | None = None,
    ) -> OAuthAccountIntegrationMixin:
        """
        Refresh the access token, once even when requests start at the same
        time, and store the new refresh token the provider may send with it. A
        refresh token the provider refuses is cleared, so the integration shows
        that it must be connected again.

        The provider is called without holding a database lock: a short-lived
        cache lock lets one request refresh while the others wait for its
        result, and the row is only locked to store it.

        :param integration: The integration, as the caller read it.
        :param refused_token: The access token the provider's API refused:
            refresh even when it isn't about to expire, unless a newer one is
            stored.
        :param deadline: The `time.monotonic()` the refresh must be over by.
        :raises ReconnectRequired: When it can't be refreshed.
        :raises ClientRejected: When the client itself is refused.
        :raises OAuthFailed: When the provider can't be reached, or another
            request is still refreshing when the deadline passes.
        :return: The stored integration, with a current token.
        """

        end = time.monotonic() + self.provider.request_deadline_seconds
        if deadline is not None:
            end = min(end, deadline)
        key = REFRESH_LOCK_KEY.format(integration.id)
        owner = secrets.token_hex(8)
        while True:
            stored = self.model.objects_and_trash.get(id=integration.id)
            usable = self._usable_without_refresh(stored, integration, refused_token)
            if usable is not None:
                return usable
            if cache.add(key, owner, timeout=REFRESH_LOCK_SECONDS):
                break
            # Another request is refreshing this token: use what it stores.
            if time.monotonic() >= end:
                raise ProviderUnavailable(
                    f"{self.provider.name} is still refreshing the sign-in. Try "
                    "again later."
                )
            time.sleep(REFRESH_POLL_SECONDS)

        try:
            # Read again: the request that held the lock may just have stored.
            stored = self.model.objects_and_trash.get(id=integration.id)
            usable = self._usable_without_refresh(stored, integration, refused_token)
            if usable is not None:
                return usable
            client = self.get_client(stored)
            try:
                token_set = self.provider.refresh(
                    client,
                    readable(stored.refresh_token),
                    stored.scopes or [],
                    deadline=end,
                )
            except ReconnectRequired:
                logger.info(
                    "{} integration {} must reconnect",
                    self.integration_type.type,
                    stored.id,
                )
                self._store_refresh(stored, None)
                raise
            return self._store_refresh(stored, token_set)
        finally:
            if cache.get(key) == owner:
                cache.delete(key)

    def _usable_without_refresh(
        self,
        stored: OAuthAccountIntegrationMixin,
        read: OAuthAccountIntegrationMixin,
        refused_token: str | None,
    ) -> OAuthAccountIntegrationMixin | None:
        """
        :param stored: The integration as stored now.
        :param read: The integration as the caller read it.
        :param refused_token: The access token the API refused, if any.
        :raises ReconnectRequired: When it isn't connected any more.
        :return: The stored integration when its token can be used as it is,
            None when it must be refreshed.
        """

        if not stored.connected:
            raise ReconnectRequired()
        if stored.generation != read.generation:
            # Signed in again since the caller read it.
            return stored
        if refused_token is not None:
            # Refused: only a token stored since then is worth trying.
            return stored if stored.access_token != refused_token else None
        return None if self.provider.expires_soon(stored.expires_at) else stored

    def _store_refresh(
        self, read: OAuthAccountIntegrationMixin, token_set: TokenSet | None
    ) -> OAuthAccountIntegrationMixin:
        """
        Store a refreshed token, or clear the tokens when the provider refused
        the refresh, unless the account was signed out or in again since
        `read`.

        :param read: The integration the refresh started from.
        :param token_set: The new tokens, None to clear them.
        :return: The stored integration.
        """

        with transaction.atomic():
            locked = lock_oauth_integration(self.model, read.id)
            if (
                locked.generation != read.generation
                or locked.refresh_token != read.refresh_token
            ):
                # What's stored now is newer than what this refreshed.
                return locked
            if token_set is None:
                update_fields = locked.clear_tokens()
            else:
                update_fields = list(TOKEN_FIELDS)
                locked.access_token = token_set.access_token
                if token_set.refresh_token:
                    locked.refresh_token = token_set.refresh_token
                locked.expires_at = token_set.expires_at
                if token_set.scopes:
                    locked.scopes = token_set.scopes
                    update_fields.append("scopes")
            locked.save(update_fields=update_fields)
        return locked
