import time
from datetime import timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urlencode

from django.utils import timezone

from requests import exceptions as request_exceptions

from advocate.exceptions import UnacceptableAddressException
from baserow.contrib.integrations.utils import send_http_request
from baserow.core.integrations.models import Integration
from baserow.core.integrations.types import IntegrationDict

from .exceptions import OAuth2TokenRequestFailed

TOKEN_REQUEST_TIMEOUT_SECONDS = 10


class OAuth2IntegrationDict(IntegrationDict):
    client_id: str
    client_secret: str
    refresh_token: str
    access_token: str
    access_token_expires_at: Any
    account_email: str


class OAuth2IntegrationTypeMixin:
    """
    The provider specifics of a connected account: where to send the user for
    consent, where to trade the code and refresh tokens, and which scopes the
    services need. Everything below runs on the backend; the browser only
    follows the authorization URL and comes back to the callback.
    """

    SerializedDict = OAuth2IntegrationDict

    authorization_url: str
    token_url: str
    scopes: List[str] = []
    # Added to the consent URL, e.g. Google's offline access flags.
    extra_authorization_params: Dict[str, str] = {}
    # Answers the connected account's email once a token is in hand.
    account_info_url: str

    allowed_fields = ["client_id", "client_secret"]
    request_serializer_field_names = ["client_id", "client_secret"]
    serializer_field_names = [
        "client_id",
        "client_secret",
        "refresh_token",
        "account_email",
    ]
    serializer_field_extra_kwargs = {
        "account_email": {"read_only": True},
    }
    # The refresh token is a secret so the API only tells whether one is set;
    # it is never written by the API, only by the callback.
    secret_fields = ["client_secret", "refresh_token"]
    sensitive_fields = [
        "client_secret",
        "refresh_token",
        "access_token",
        "account_email",
    ]
    secret_field_dependencies = {"client_secret": ["client_id"]}

    def import_serialized(self, parent, serialized_values, id_mapping, **kwargs):
        # Exported without its secrets, which arrive as None.
        for name in ("client_id", "client_secret", "refresh_token", "access_token"):
            if serialized_values.get(name) is None:
                serialized_values[name] = ""
        if serialized_values.get("account_email") is None:
            serialized_values["account_email"] = ""
        return super().import_serialized(
            parent, serialized_values, id_mapping, **kwargs
        )

    def get_authorization_url(self, integration: Integration) -> str:
        return self.authorization_url

    def get_token_url(self, integration: Integration) -> str:
        return self.token_url

    def build_authorization_url(
        self, integration: Integration, redirect_uri: str, state: str
    ) -> str:
        params = {
            "client_id": integration.client_id,
            "redirect_uri": redirect_uri,
            "response_type": "code",
            "scope": " ".join(self.scopes),
            "state": state,
            **self.extra_authorization_params,
        }
        return f"{self.get_authorization_url(integration)}?{urlencode(params)}"

    def exchange_code(
        self, integration: Integration, code: str, redirect_uri: str
    ) -> Dict[str, Any]:
        return self._token_request(
            integration,
            {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
            },
        )

    def refresh_access_token(self, integration: Integration) -> Dict[str, Any]:
        return self._token_request(
            integration,
            {
                "grant_type": "refresh_token",
                "refresh_token": integration.refresh_token,
            },
        )

    def _token_request(self, integration: Integration, data: Dict[str, str]) -> dict:
        deadline = time.monotonic() + TOKEN_REQUEST_TIMEOUT_SECONDS
        try:
            response = send_http_request(
                "POST",
                self.get_token_url(integration),
                deadline=deadline,
                operation_timeout=TOKEN_REQUEST_TIMEOUT_SECONDS,
                data={
                    **data,
                    "client_id": integration.client_id,
                    "client_secret": integration.client_secret,
                },
                headers={"Accept": "application/json"},
                allow_redirects=False,
            )
        except UnacceptableAddressException as e:
            raise OAuth2TokenRequestFailed(
                "The provider's address is not allowed by this installation."
            ) from e
        except request_exceptions.RequestException as e:
            raise OAuth2TokenRequestFailed(
                f"The provider could not be reached: {type(e).__name__}."
            ) from e
        try:
            body = response.json()
        except ValueError:
            body = {}
        if response.status_code >= 400 or "access_token" not in body:
            # `error_description` is what the provider wants the user to read.
            detail = ""
            if isinstance(body, dict):
                detail = body.get("error_description") or body.get("error") or ""
            raise OAuth2TokenRequestFailed(
                f"The provider refused the token request ({response.status_code})"
                + (f": {detail}" if detail else ".")
            )
        return body

    def apply_token_response(self, integration: Integration, body: dict) -> None:
        """
        Stores a token answer. A refresh answer usually carries no refresh
        token, in which case the stored one stays valid.
        """

        integration.access_token = body["access_token"]
        if body.get("refresh_token"):
            integration.refresh_token = body["refresh_token"]
        expires_in = body.get("expires_in")
        try:
            seconds = int(expires_in)
        except (TypeError, ValueError):
            seconds = 3600
        integration.access_token_expires_at = timezone.now() + timedelta(
            seconds=seconds
        )

    def fetch_account_email(self, access_token: str) -> Optional[str]:
        deadline = time.monotonic() + TOKEN_REQUEST_TIMEOUT_SECONDS
        try:
            response = send_http_request(
                "GET",
                self.account_info_url,
                deadline=deadline,
                operation_timeout=TOKEN_REQUEST_TIMEOUT_SECONDS,
                headers={"Authorization": f"Bearer {access_token}"},
                allow_redirects=False,
            )
            body = response.json()
        except (
            UnacceptableAddressException,
            request_exceptions.RequestException,
            ValueError,
        ):
            # Only a label; the connection itself is fine without it.
            return None
        if not isinstance(body, dict):
            return None
        return self.extract_account_email(body)

    def extract_account_email(self, body: dict) -> Optional[str]:
        return body.get("email")
