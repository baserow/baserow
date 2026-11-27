from typing import Any

from django.conf import settings

from baserow.contrib.integrations.oauth_account.service_types import (
    OAuthAccountServiceTypeMixin,
    quote_path_segments,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)

from .models import MicrosoftIntegration

GRAPH_API_VERSION = "v1.0"


def graph_url(*segments: Any) -> str:
    """
    The Microsoft Graph URL of a path, each segment quoted on its own.

    :param segments: The path segments, e.g. `"chats", chat_id, "messages"`.
    :raises ValueError: When a segment is empty, `.` or `..`.
    :return: The URL.
    """

    return (
        f"{settings.INTEGRATIONS_MICROSOFT_GRAPH_URL}/{GRAPH_API_VERSION}/"
        f"{quote_path_segments(*segments)}"
    )


class MicrosoftServiceTypeMixin(OAuthAccountServiceTypeMixin):
    """
    For service types that act as the account of a Microsoft integration through
    Microsoft Graph. Set `required_scopes` and `permission_description`.
    """

    integration_type = "microsoft"

    def get_microsoft_integration(self, service) -> MicrosoftIntegration:
        return self.get_oauth_integration(service)

    def graph_request(self, service, method: str, *segments: Any, **kwargs) -> Any:
        """
        A Graph request as the service's account, with failures turned into
        dispatch exceptions whose messages are safe to show.

        :param service: The service.
        :param method: The HTTP method.
        :param segments: The path after the API version, see `graph_url`.
        :param kwargs: Passed on to `request_as_account`, e.g. `json`, `params`,
            `deadline`.
        :return: The answer's JSON, None when it has no body.
        """

        try:
            url = graph_url(*segments)
        except ValueError as exc:
            raise ServiceImproperlyConfiguredDispatchException(
                "An id of this action is empty or invalid."
            ) from exc
        response = self.request_as_account(service, method, url, **kwargs)
        if not response.content:
            return None
        try:
            return response.json()
        except ValueError:
            return None
