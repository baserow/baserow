from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

import httpx

if TYPE_CHECKING:
    from phoenix.client import Client


class _PhoenixHttpClient(httpx.Client):
    """Keep the HTTP pool alive as long as any Phoenix SDK resource uses it."""

    def __del__(self) -> None:
        """Release connections without surfacing garbage-collection errors."""

        try:
            if not self.is_closed:
                self.close()
        except BaseException:
            pass


def get_phoenix_client() -> "Client":
    """Build a Phoenix client using only Baserow's endpoint and credentials.

    :return: A client whose HTTP pool closes after its last resource is released.
    :raises ImproperlyConfigured: If no Baserow Phoenix endpoint is configured.
    """

    base_url = getattr(settings, "BASEROW_ASSISTANT_PHOENIX_URL", "")
    if not base_url:
        raise ImproperlyConfigured(
            "No Phoenix endpoint configured. Set BASEROW_ASSISTANT_PHOENIX_URL "
            "— see "
            "docs/development/ai-assistant-tracing.md."
        )

    api_key = getattr(settings, "BASEROW_ASSISTANT_PHOENIX_API_KEY", "")

    from phoenix.client import Client

    # Supplying an HTTP client bypasses Phoenix's environment/config-file headers.
    http_client = _PhoenixHttpClient(
        base_url=base_url,
        headers={"Authorization": f"Bearer {api_key}"} if api_key else {},
        timeout=httpx.Timeout(connect=10, read=30, write=10, pool=10),
    )
    try:
        client = Client(http_client=http_client)
    except BaseException:
        http_client.close()
        raise
    return client
