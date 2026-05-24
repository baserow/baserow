from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from django.conf import settings
from django.core.cache import cache

if TYPE_CHECKING:
    from baserow_premium.license.models import License

_CACHE_KEY = "license:instance_wide_active"


def get_cached_instance_wide_licenses() -> list[License] | None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return None
    return cache.get(_CACHE_KEY)


def set_cached_instance_wide_licenses(licenses: list[License]) -> None:
    """
    Cache the active instance-wide licenses for at most
    ``BASEROW_CACHE_TTL_SECONDS`` and no longer than until the earliest license
    expires, so the cache naturally self-heals when a license rolls over.
    """

    max_ttl = settings.BASEROW_CACHE_TTL_SECONDS
    if max_ttl <= 0:
        return

    if licenses:
        now = datetime.now(tz=timezone.utc)
        earliest = min(
            int((lic.valid_through - now).total_seconds()) for lic in licenses
        )
        ttl = max(1, min(max_ttl, earliest))
    else:
        ttl = max_ttl
    cache.set(_CACHE_KEY, licenses, timeout=ttl)


def invalidate_cached_instance_wide_licenses() -> None:
    if settings.BASEROW_CACHE_TTL_SECONDS <= 0:
        return
    cache.delete(_CACHE_KEY)
