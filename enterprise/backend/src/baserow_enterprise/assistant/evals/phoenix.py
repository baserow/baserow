from __future__ import annotations

import os
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

if TYPE_CHECKING:
    from phoenix.client import Client


def get_phoenix_client() -> "Client":
    """Build a Phoenix client from env vars, falling back to Django settings."""

    base_url = os.getenv("PHOENIX_ENDPOINT") or getattr(
        settings, "BASEROW_ASSISTANT_PHOENIX_URL", ""
    )
    if not base_url:
        raise ImproperlyConfigured(
            "No Phoenix endpoint configured. Set BASEROW_ASSISTANT_PHOENIX_URL "
            "(or the PHOENIX_ENDPOINT env var) — see "
            "docs/development/ai-assistant-tracing.md."
        )

    api_key = os.getenv("PHOENIX_API_KEY") or getattr(
        settings, "BASEROW_ASSISTANT_PHOENIX_API_KEY", ""
    )

    from phoenix.client import Client

    return Client(base_url=base_url, api_key=api_key or None)
