"""Permission-aware Google account connection operations for application editors."""

import base64
import hashlib
import secrets
from urllib.parse import urlencode

from django.core.cache import cache
from django.db import transaction

from rest_framework.exceptions import ValidationError

from baserow.core.handler import CoreHandler
from baserow.core.integrations.exceptions import IntegrationDoesNotExist
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.integrations.operations import UpdateIntegrationOperationType
from baserow.core.integrations.signals import integration_updated
from baserow.core.services.exceptions import ServiceTypeDoesNotExist

from . import oauth
from .models import GoogleIntegration


def editable_integration(user, integration_id):
    """Resolve the integration and enforce the existing integration edit operation."""
    integration = IntegrationHandler().get_integration(integration_id).specific
    if not isinstance(integration, GoogleIntegration):
        raise IntegrationDoesNotExist()
    CoreHandler().check_permissions(
        user,
        UpdateIntegrationOperationType.type,
        workspace=integration.application.workspace,
        context=integration,
    )
    return integration


def notify(user, integration):
    integration_updated.send(sender=notify, integration=integration, user=user)
    return integration


def start(user, integration_id, service_type=None):
    """Create an expiring user-bound PKCE flow, invalidating any older flow."""
    scopes = set(oauth.IDENTITY_SCOPES)
    if service_type:
        from baserow.core.services.registries import service_type_registry

        try:
            service = service_type_registry.get(service_type)
        except ServiceTypeDoesNotExist:
            raise ValidationError("Unknown Google service.") from None
        if service.integration_type != "google":
            raise ValidationError("Unknown Google service.")
        scopes.update(service.required_scopes)
    with transaction.atomic():
        integration = editable_integration(user, integration_id)
        integration = oauth.lock_integration(integration.pk)
        client_id, secret = oauth.client(integration)
        if not client_id or not secret:
            raise ValidationError("Configure an OAuth client before connecting Google.")
        integration.generation += 1
        integration.save(update_fields=["generation"])
        state, verifier = secrets.token_urlsafe(32), secrets.token_urlsafe(64)
        cache.set(
            f"google_oauth:{state}",
            {
                "user_id": user.id,
                "integration_id": integration.id,
                "generation": integration.generation,
                "client": oauth.client_fingerprint(integration),
                "verifier": verifier,
            },
            timeout=600,
        )
        scopes.update(integration.granted_scopes)
        params = {
            "client_id": client_id,
            "redirect_uri": oauth.redirect_uri(),
            "response_type": "code",
            "scope": " ".join(sorted(scopes)),
            "access_type": "offline",
            "include_granted_scopes": "true",
            "prompt": "consent",
            "state": state,
            "code_challenge": base64.urlsafe_b64encode(
                hashlib.sha256(verifier.encode()).digest()
            )
            .decode()
            .rstrip("="),
            "code_challenge_method": "S256",
        }
        if integration.account_email:
            params["login_hint"] = integration.account_email
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def complete(user, state, code):
    """Consume state once and reject stale flows or a different Google account."""
    key = f"google_oauth:{state}"
    pending = cache.get(key)
    if not pending or pending["user_id"] != user.id:
        raise ValidationError("Google sign-in expired or belongs to another user.")
    if not cache.delete(key):
        raise ValidationError("Google sign-in was already completed.")
    if not code:
        raise ValidationError("Google authorization was cancelled.")
    with transaction.atomic():
        integration = editable_integration(user, pending["integration_id"])
        integration = oauth.lock_integration(integration.pk)
        if (
            integration.generation != pending["generation"]
            or oauth.client_fingerprint(integration) != pending["client"]
        ):
            raise ValidationError(
                "Google configuration changed. Start connecting again."
            )
        client_id, secret = oauth.client(integration)
        status, token = oauth.request_json(
            "POST",
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "authorization_code",
                "code": code,
                "client_id": client_id,
                "client_secret": secret,
                "redirect_uri": oauth.redirect_uri(),
                "code_verifier": pending["verifier"],
            },
        )
        if status != 200:
            raise ValidationError("Google refused the authorization code.")
        if integration.connected_client != oauth.client_fingerprint(integration):
            integration.clear_tokens()
        oauth.store_token(integration, token)
        status, identity = oauth.request_json(
            "GET",
            "https://openidconnect.googleapis.com/v1/userinfo",
            headers={"Authorization": f"Bearer {integration.access_token}"},
        )
        if (
            status != 200
            or not identity.get("sub")
            or not identity.get("email")
            or not identity.get("email_verified")
        ):
            raise ValidationError(
                "Google did not grant access to a verified account identity."
            )
        if integration.account_id and integration.account_id != identity["sub"]:
            raise ValidationError(
                "Use a new integration to connect a different Google account."
            )
        integration.account_id = identity["sub"]
        integration.account_email = identity["email"]
        integration.save()
    return notify(user, integration)


def disconnect(user, integration_id):
    """Disable all consumers and invalidate pending flows; retain account identity."""
    with transaction.atomic():
        integration = editable_integration(user, integration_id)
        integration = oauth.lock_integration(integration.pk)
        integration.clear_tokens()
        integration.generation += 1
        integration.save()
    return notify(user, integration)
