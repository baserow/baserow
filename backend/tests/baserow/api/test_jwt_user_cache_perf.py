"""
Perf comparison: cached vs uncached JWT user lookup.

Run with:
    just b test tests/baserow/api/test_jwt_user_cache_perf.py -s
"""

import time

from django.test.utils import override_settings

import pytest
from rest_framework_simplejwt.tokens import AccessToken

from baserow.api.authentication import JSONWebTokenAuthentication
from baserow.core.user.cache import invalidate_cached_user

ITERATIONS = 500


def _bench(auth, token) -> float:
    """Return average time in microseconds over ITERATIONS calls."""

    auth.get_user(token)

    start = time.perf_counter_ns()
    for _ in range(ITERATIONS):
        auth.get_user(token)
    elapsed_ns = time.perf_counter_ns() - start

    return elapsed_ns / ITERATIONS / 1_000


@pytest.mark.disabled_in_ci
@pytest.mark.django_db
def test_perf_cached_vs_uncached(data_fixture):
    user = data_fixture.create_user()
    token = AccessToken.for_user(user)
    auth = JSONWebTokenAuthentication()

    with override_settings(BASEROW_CACHE_TTL_SECONDS=30):
        invalidate_cached_user(user.id)
        avg_cached = _bench(auth, token)

    with override_settings(BASEROW_CACHE_TTL_SECONDS=0):
        invalidate_cached_user(user.id)
        avg_uncached = _bench(auth, token)

    speedup = avg_uncached / avg_cached if avg_cached > 0 else float("inf")

    print()
    print(f"  Benchmark: {ITERATIONS} iterations of get_user()")
    print(f"  ┌──────────────────────────────────────────┐")
    print(f"  │ Uncached (DB every call):  {avg_uncached:>8.1f} µs/call │")
    print(f"  │ Cached   (Redis hit):      {avg_cached:>8.1f} µs/call │")
    print(f"  │ Speedup:                   {speedup:>8.1f}x       │")
    print(f"  └──────────────────────────────────────────┘")

    assert avg_cached < avg_uncached, (
        f"Expected cache to be faster, got cached={avg_cached:.1f}µs "
        f"vs uncached={avg_uncached:.1f}µs"
    )
