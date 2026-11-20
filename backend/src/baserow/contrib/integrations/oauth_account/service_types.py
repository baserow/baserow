import time
from typing import Any, Dict, List
from urllib.parse import quote

from rest_framework import serializers

from baserow.contrib.integrations.utils import send_http_request
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.services.exceptions import (
    RemoteBusyDispatchException,
    RemoteRefusedDispatchException,
    RuntimeDispatchException,
    ServiceImproperlyConfiguredDispatchException,
)

from .exceptions import (
    ClientRejected,
    OAuthAccountNotConfigured,
    OAuthFailed,
    ProviderAPIError,
    ProviderAPIUnreachable,
    ReconnectRequired,
    ScopesMissing,
)
from .handler import OAuthAccountHandler
from .models import OAuthAccountIntegrationMixin
from .providers import REQUEST_EXCEPTIONS

# API answers that mean "ask again later".
BUSY_STATUS_CODES = (429, 503, 504)
# Longest a single connect or read to the provider's API may wait, in seconds.
API_OPERATION_TIMEOUT_SECONDS = 10


def quote_path_segments(*segments: Any) -> str:
    """
    A URL path, each segment quoted on its own. Segments are often ids resolved
    from formulas: unquoted, a `/` or `..` in one would reach another endpoint
    of the provider's API with the account's token.

    :param segments: The path segments, e.g. `"chats", chat_id, "messages"`.
    :raises ValueError: When a segment is empty, `.` or `..`.
    :return: The segments joined with `/`.
    """

    quoted = []
    for segment in segments:
        segment = str(segment)
        if segment in ("", ".", ".."):
            raise ValueError("A path segment can't be empty, '.' or '..'.")
        quoted.append(quote(segment, safe=""))
    return "/".join(quoted)


def _retry_after(response) -> int | None:
    try:
        return int(response.headers.get("Retry-After"))
    except (TypeError, ValueError):
        return None


class MissingScopesField(serializers.Field):
    """
    The scopes a service's type needs that its integration's account hasn't
    granted, so the frontend can offer to grant them without repeating the
    scope lists.
    """

    def __init__(self, service_type: "OAuthAccountServiceTypeMixin", **kwargs):
        self.service_type = service_type
        kwargs.setdefault("read_only", True)
        kwargs.setdefault("source", "*")
        kwargs.setdefault(
            "help_text",
            "The permissions this service needs that its integration's account "
            "hasn't granted. Empty when it isn't connected.",
        )
        super().__init__(**kwargs)

    def to_representation(self, service) -> List[str]:
        return self.service_type.get_missing_scopes(service)


class OAuthAccountServiceTypeMixin:
    """
    For service types that act as the account of an OAuth account integration.
    The account grants `required_scopes` when someone signs in for a service of
    this type, so a service that only sends email never asks for access to
    chats, and the other way around.

    Put it before `ServiceType` in the bases, and set `integration_type`.
    """

    integration_type: str
    """The OAuth account integration type the service acts through."""

    required_scopes: list[str] = []
    """The provider's scopes the service needs, written as the provider does."""

    permission_description: str = ""
    """
    What the scopes let Baserow do, completing "hasn't allowed Baserow to … yet",
    e.g. "send Teams messages".
    """

    @property
    def oauth_integration_type(self):
        return integration_type_registry.get(self.integration_type)

    @property
    def oauth_provider_name(self) -> str:
        return self.oauth_integration_type.provider.name

    def get_field_names(
        self, request_serializer: bool, extra_params=None, **kwargs
    ) -> List[str]:
        names = super().get_field_names(request_serializer, extra_params, **kwargs)
        if request_serializer or (extra_params or {}).get("public"):
            return names
        return [*names, "missing_scopes"]

    def get_field_overrides(
        self, request_serializer: bool, extra_params=None, **kwargs
    ) -> Dict:
        overrides = super().get_field_overrides(
            request_serializer, extra_params, **kwargs
        )
        if request_serializer or (extra_params or {}).get("public"):
            return overrides
        return {**overrides, "missing_scopes": MissingScopesField(self)}

    def get_missing_scopes(self, service) -> list[str]:
        """
        :param service: The service.
        :return: The required scopes its integration's account didn't grant,
            empty when it has no connected account.
        """

        integration = service.integration.specific if service.integration_id else None
        if not isinstance(integration, OAuthAccountIntegrationMixin):
            return []
        if not integration.connected:
            return []
        return self.oauth_integration_type.provider.missing_scopes(
            integration.scopes, self.required_scopes
        )

    def get_oauth_integration(self, service) -> OAuthAccountIntegrationMixin:
        """
        :param service: The service.
        :raises ServiceImproperlyConfiguredDispatchException: When it has no
            integration of its type.
        :return: Its integration.
        """

        integration = service.integration.specific if service.integration_id else None
        model = self.oauth_integration_type.model_class
        if type(integration) is not model:
            raise ServiceImproperlyConfiguredDispatchException(
                f"The integration of this action is not a {self.oauth_provider_name} "
                "account."
            )
        return integration

    def get_oauth_handler(self) -> OAuthAccountHandler:
        return OAuthAccountHandler(self.oauth_integration_type)

    def get_access_token(self, service, deadline: float | None = None) -> str:
        """
        A token with `required_scopes`, as the service's account.

        :param service: The service.
        :param deadline: The `time.monotonic()` a refresh must be over by.
        :raises ServiceImproperlyConfiguredDispatchException: When the account
            must be connected again or grant access.
        :raises RuntimeDispatchException: When the failure is transient.
        :return: The access token.
        """

        integration = self.get_oauth_integration(service)
        try:
            return self.get_oauth_handler().get_access_token(
                integration, self.required_scopes, deadline=deadline
            )
        except (
            ReconnectRequired,
            ScopesMissing,
            ClientRejected,
            OAuthFailed,
            OAuthAccountNotConfigured,
        ) as exc:
            raise self.dispatch_exception_for(exc) from exc

    def refuse_token(self, service, token: str, deadline: float | None = None) -> str:
        """
        Call when the provider's API refused `token` (a 401): it's refreshed
        once, unless a newer one is stored.

        :param service: The service.
        :param token: The refused access token.
        :param deadline: The `time.monotonic()` a refresh must be over by.
        :raises ServiceImproperlyConfiguredDispatchException: When the account
            must be connected again.
        :raises RuntimeDispatchException: When the failure is transient.
        :return: An access token to try again with.
        """

        integration = self.get_oauth_integration(service)
        try:
            return self.get_oauth_handler().refuse_token(
                integration, token, deadline=deadline
            )
        except (
            ReconnectRequired,
            ClientRejected,
            OAuthFailed,
            OAuthAccountNotConfigured,
        ) as exc:
            raise self.dispatch_exception_for(exc) from exc

    def request_as_account(
        self,
        service,
        method: str,
        url: str,
        deadline: float | None = None,
        **kwargs,
    ):
        """
        A request to the provider's API as the service's account. A token the
        API refuses is refreshed once. Failures become dispatch exceptions whose
        messages are safe to show.

        :param service: The service.
        :param method: The HTTP method.
        :param url: The URL. Build paths from formulas with
            `quote_path_segments`.
        :param deadline: The `time.monotonic()` the whole exchange must be over
            by, the token refresh included.
        :param kwargs: Passed on to `send_http_request`, e.g. `params`, `json`.
        :return: The response, with a status below 400.
        """

        if deadline is None:
            deadline = time.monotonic() + API_OPERATION_TIMEOUT_SECONDS * 2
        token = self.get_access_token(service, deadline=deadline)
        try:
            response = self._send_as_account(method, url, token, deadline, kwargs)
            if response.status_code == 401:
                # Revoked or expired early: a new token may still be accepted.
                token = self.refuse_token(service, token, deadline=deadline)
                response = self._send_as_account(method, url, token, deadline, kwargs)
                if response.status_code == 401:
                    raise ReconnectRequired()
            if response.status_code >= 400:
                raise ProviderAPIError(
                    response.status_code,
                    self.get_api_error_code(response),
                    _retry_after(response),
                )
        except (ReconnectRequired, ProviderAPIUnreachable) as exc:
            raise self.dispatch_exception_for(exc) from exc
        except ProviderAPIError as exc:
            raise self.api_error_exception(exc) from exc
        return response

    def _send_as_account(self, method, url, token, deadline, kwargs):
        kwargs = dict(kwargs)
        headers = {**(kwargs.pop("headers", None) or {})}
        headers["Authorization"] = f"Bearer {token}"
        try:
            return send_http_request(
                method=method,
                url=url,
                headers=headers,
                deadline=deadline,
                operation_timeout=API_OPERATION_TIMEOUT_SECONDS,
                # The token only goes to the address that was configured.
                allow_redirects=False,
                send_netrc_credentials=False,
                **kwargs,
            )
        except REQUEST_EXCEPTIONS as exc:
            # Not `str(exc)`: it can repeat what was sent.
            raise ProviderAPIUnreachable(type(exc).__name__) from exc

    def get_api_error_code(self, response) -> str:
        """
        The provider's error code in an error answer, never its message: that
        can repeat what was sent. Providers whose errors read differently
        override it.

        :param response: The error answer.
        :return: The code, empty when there's none.
        """

        try:
            payload = response.json()
        except ValueError:
            return ""
        error = payload.get("error") if isinstance(payload, dict) else None
        code = error.get("code") if isinstance(error, dict) else error
        if isinstance(code, int):
            code = str(code)
        return code[:100] if isinstance(code, str) else ""

    def dispatch_exception_for(self, exc: Exception) -> Exception:
        """
        :param exc: A failure to get a token or to reach the provider's API.
        :return: The dispatch exception to raise instead.
        """

        name = self.oauth_provider_name
        if isinstance(exc, ReconnectRequired):
            return ServiceImproperlyConfiguredDispatchException(
                f"The {name} account of this integration must be connected again. "
                "Reconnect it in the integration settings, then publish again if "
                "this runs in a published application or workflow."
            )
        if isinstance(exc, ScopesMissing):
            what = self.permission_description or ", ".join(exc.scopes)
            return ServiceImproperlyConfiguredDispatchException(
                f"The {name} account of this integration hasn't allowed Baserow to "
                f"{what} yet. Grant access in this action's settings."
            )
        if isinstance(exc, ClientRejected):
            return ServiceImproperlyConfiguredDispatchException(
                f"{name} refused the OAuth app this integration signs in through, "
                "maybe because its secret expired. Contact your Baserow admin."
            )
        if isinstance(exc, OAuthAccountNotConfigured):
            return ServiceImproperlyConfiguredDispatchException(
                f"This Baserow installation isn't set up to connect {name} accounts."
            )
        if isinstance(exc, OAuthFailed):
            if exc.retryable:
                return RuntimeDispatchException(
                    f"{name} could not be reached to refresh the sign-in. Try "
                    "again later."
                )
            # The provider answered and refused: trying again won't change that.
            return RemoteRefusedDispatchException(
                f"{name} refused to refresh the sign-in of this integration. "
                "Reconnect it in the integration settings."
            )
        return RuntimeDispatchException(
            f"The request to {name} failed: {exc}."
            if isinstance(exc, ProviderAPIUnreachable)
            else f"The request to {name} failed."
        )

    def api_error_exception(self, exc: ProviderAPIError) -> Exception:
        """
        Service types override it for messages that name what they act on, or
        for the provider's own codes, e.g. a quota.

        :param exc: What the provider's API answered.
        :return: The dispatch exception to raise instead.
        """

        name = self.oauth_provider_name
        if exc.status_code in BUSY_STATUS_CODES:
            return RemoteBusyDispatchException(
                f"{name} asked for this to be sent again later."
            )
        if exc.status_code == 403:
            return RemoteRefusedDispatchException(
                f"The connected {name} account isn't allowed to do this."
            )
        if exc.status_code == 404:
            return RemoteRefusedDispatchException(
                f"{name} couldn't find what this action points to."
            )
        detail = exc.code or str(exc.status_code)
        return RemoteRefusedDispatchException(f"{name} refused the request: {detail}.")
