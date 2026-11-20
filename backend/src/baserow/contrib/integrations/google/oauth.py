"""Google authorization, shared by services using one application integration."""

import hashlib
import time
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from requests import RequestException

from baserow.contrib.integrations.utils import send_http_request
from baserow.core.fields import is_unreadable_secret
from baserow.core.integrations.models import Integration
from baserow.core.services.exceptions import (
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)

from .models import GoogleIntegration

GMAIL_SEND_SCOPE = "https://www.googleapis.com/auth/gmail.send"
IDENTITY_SCOPES = {"openid", "https://www.googleapis.com/auth/userinfo.email"}
REQUEST_TIMEOUT = 20


def lock_integration(integration_id):
    """Lock the parent first, then read fresh child fields after any lock wait.

    A joined SELECT locking only the parent can return child tokens from the
    snapshot before a concurrent refresh committed. Separate reads prevent
    two workers from refreshing the same rotating token.
    """
    Integration.objects.select_for_update(of=("self",)).get(pk=integration_id)
    return GoogleIntegration.objects.get(pk=integration_id)


def redirect_uri():
    return settings.PUBLIC_WEB_FRONTEND_URL.rstrip("/") + "/google-oauth-callback"


def client(integration):
    if integration.client_mode == "default":
        return settings.GOOGLE_OAUTH_CLIENT_ID, settings.GOOGLE_OAUTH_CLIENT_SECRET
    if is_unreadable_secret(integration.client_secret):
        raise ServiceImproperlyConfiguredDispatchException(
            "The Google client secret cannot be decrypted. Restore the encryption key or enter it again."
        )
    return integration.client_id, integration.client_secret


def client_fingerprint(integration):
    client_id, secret = client(integration)
    return hashlib.sha256(f"{client_id}\0{secret}".encode()).hexdigest()


def request_json(method, url, **kwargs):
    """Bound Google responses, refuse redirects and keep credentials out of errors."""
    try:
        response = send_http_request(
            method=method,
            url=url,
            deadline=time.monotonic() + REQUEST_TIMEOUT,
            operation_timeout=REQUEST_TIMEOUT,
            allow_redirects=False,
            send_netrc_credentials=False,
            **kwargs,
        )
    except RequestException:
        raise RuntimeDispatchException("Google could not be reached.") from None
    if response.status_code == 429 or response.status_code >= 500:
        raise RemoteBusyDispatchException(
            "Google is temporarily unavailable or its quota was exceeded."
        )
    try:
        data = response.json()
    except ValueError:
        raise RemoteRefusedDispatchException(
            "Google returned an invalid response."
        ) from None
    if not isinstance(data, dict):
        raise RemoteRefusedDispatchException("Google returned an invalid response.")
    return response.status_code, data


def store_token(integration, data):
    """Preserve refresh tokens Google omits and store the actual granted scopes."""
    if not isinstance(data.get("access_token"), str) or not data["access_token"]:
        raise RemoteRefusedDispatchException("Google returned no access token.")
    try:
        lifetime = int(data["expires_in"])
        scopes = data["scope"].split()
    except (KeyError, ValueError, TypeError, AttributeError):
        raise RemoteRefusedDispatchException(
            "Google returned invalid token metadata."
        ) from None
    integration.access_token = data["access_token"]
    if data.get("refresh_token"):
        integration.refresh_token = data["refresh_token"]
    integration.expires_at = timezone.now() + timedelta(seconds=lifetime)
    integration.granted_scopes = scopes
    integration.connected_client = client_fingerprint(integration)
    integration.connected = True


def access_token(integration_id, required_scopes):
    """Serialize refreshes and persist revocation without discarding transient failures."""
    failed = False
    with transaction.atomic():
        integration = lock_integration(integration_id)
        if is_unreadable_secret(integration.access_token) or is_unreadable_secret(
            integration.refresh_token
        ):
            raise ServiceImproperlyConfiguredDispatchException(
                "The Google tokens cannot be decrypted. Restore the encryption key or reconnect."
            )
        if (
            not integration.connected
            or integration.connected_client != client_fingerprint(integration)
        ):
            raise ServiceImproperlyConfiguredDispatchException(
                "Reconnect the Google integration."
            )
        if not set(required_scopes).issubset(integration.granted_scopes):
            raise ServiceImproperlyConfiguredDispatchException(
                "Grant the Google permissions required by this action."
            )
        if (
            not integration.expires_at
            or integration.expires_at <= timezone.now() + timedelta(seconds=60)
        ):
            if not integration.refresh_token:
                failed = True
            else:
                client_id, secret = client(integration)
                status, token = request_json(
                    "POST",
                    "https://oauth2.googleapis.com/token",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": integration.refresh_token,
                        "client_id": client_id,
                        "client_secret": secret,
                    },
                )
                if status == 200:
                    # A refresh response may omit scope when it is unchanged.
                    token.setdefault("scope", " ".join(integration.granted_scopes))
                    store_token(integration, token)
                elif token.get("error") == "invalid_grant":
                    failed = True
                else:
                    raise RemoteRefusedDispatchException(
                        "Google refused the token refresh."
                    )
            if failed:
                integration.clear_tokens()
            integration.save()
    if failed:
        raise ServiceImproperlyConfiguredDispatchException(
            "Google authorization was revoked. Reconnect the integration."
        )
    if not set(required_scopes).issubset(integration.granted_scopes):
        raise ServiceImproperlyConfiguredDispatchException(
            "Grant the Google permissions required by this action."
        )
    return integration.access_token, integration.account_email


def invalidate_access_token(integration_id, token):
    """A rejected token disables the connection unless a newer sign-in replaced it."""
    with transaction.atomic():
        integration = lock_integration(integration_id)
        if integration.access_token == token:
            integration.clear_tokens()
            integration.save()
