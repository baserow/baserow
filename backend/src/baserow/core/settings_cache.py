from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache

if TYPE_CHECKING:
    from baserow.core.models import Settings

_CACHE_KEY = "core:settings"


def get_cached_settings() -> Settings | None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return None
    return cache.get(_CACHE_KEY)


def set_cached_settings(instance: Settings) -> None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return
    cache.set(_CACHE_KEY, instance, timeout=settings.BASEROW_CACHE_TTL_SECONDS)


def invalidate_cached_settings() -> None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return
    cache.delete(_CACHE_KEY)
