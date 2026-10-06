import json

from django.http import JsonResponse

from oauth2_provider.views import (
    DynamicClientRegistrationManagementView,
    DynamicClientRegistrationView,
)

from .validators import ALLOWED_GRANT_TYPES, ALLOWED_RESPONSE_TYPES


def _metadata_error(body: bytes) -> str | None:
    """
    Returns why the client metadata asks for something other than the authorization
    code flow, or None. Bodies that aren't a JSON object are left to the library.
    """

    try:
        data = json.loads(body)
    except ValueError:
        return None
    if not isinstance(data, dict):
        return None

    grant_types = data.get("grant_types", ["authorization_code"])
    if (
        not isinstance(grant_types, list)
        or "authorization_code" not in grant_types
        or not set(grant_types) <= ALLOWED_GRANT_TYPES
    ):
        return "Only the authorization_code and refresh_token grant types are allowed."

    response_types = data.get("response_types", ["code"])
    if not isinstance(response_types, list) or not set(response_types) <= (
        ALLOWED_RESPONSE_TYPES
    ):
        return "Only the code response type is allowed."
    return None


def _reject_other_flows(handler):
    def wrapped(self, request, *args, **kwargs):
        error = _metadata_error(request.body)
        if error:
            return JsonResponse(
                {"error": "invalid_client_metadata", "error_description": error},
                status=400,
            )
        return handler(self, request, *args, **kwargs)

    return wrapped


class MCPDynamicClientRegistrationView(DynamicClientRegistrationView):
    """Registers clients for the authorization code flow only (RFC 7591)."""

    post = _reject_other_flows(DynamicClientRegistrationView.post)


class MCPDynamicClientRegistrationManagementView(
    DynamicClientRegistrationManagementView
):
    """Keeps updated clients on the authorization code flow only (RFC 7592)."""

    put = _reject_other_flows(DynamicClientRegistrationManagementView.put)
