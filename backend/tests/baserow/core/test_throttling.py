from unittest import mock

from django.core.cache import cache

import pytest
from freezegun import freeze_time

from baserow.throttling.exceptions import RateLimitExceededException
from baserow.throttling.handler import rate_limit
from baserow.throttling.types import RateLimit

throttled_fn_name = "throttled_function"
throttled_fn_2_name = "throttled_function_2"
throttled_key = "my_key"
throttled_key_2 = "my_key_2"


@pytest.fixture
def clear_throttle_cache():
    yield
    cache.delete(f"{throttled_fn_name}:{throttled_key}")
    cache.delete(f"{throttled_fn_name}:{throttled_key_2}")
    cache.delete(f"{throttled_fn_2_name}:{throttled_key}")
    cache.delete(f"{throttled_fn_2_name}:{throttled_key_2}")


def get_named_mock(function_name):
    class NamedMagicMock(mock.MagicMock):
        __name__ = function_name

    return NamedMagicMock()


@rate_limit(rate=RateLimit.from_string("1/s"), key=throttled_key)
def fn_rate_limited_one_per_second():
    """
    Throttled function for testing purposes that uses
    the rate_limit decorator.
    """

    pass


def test_rate_limit_throws_exception_by_default(clear_throttle_cache):
    with pytest.raises(RateLimitExceededException):
        for _ in range(2):
            fn_rate_limited_one_per_second()


def test_rate_limit_with_ignored_exceptions(clear_throttle_cache):
    mock_fn = get_named_mock(throttled_fn_name)

    for _ in range(10):
        rate_limit(
            rate=RateLimit.from_string("1/s"), key=throttled_key, raise_exception=False
        )(mock_fn)()

    assert mock_fn.call_count == 1


def test_rate_limit_different_keys_independent_counters(clear_throttle_cache):
    mock_fn = get_named_mock(throttled_fn_name)

    rate_limit(rate=RateLimit.from_string("1/s"), key=throttled_key)(mock_fn)()
    rate_limit(rate=RateLimit.from_string("1/s"), key=throttled_key_2)(mock_fn)()

    assert mock_fn.call_count == 2


def test_rate_limit_different_functions_independent_counters(clear_throttle_cache):
    mock_fn = get_named_mock(throttled_fn_name)
    mock_fn2 = get_named_mock(throttled_fn_2_name)

    rate_limit(rate=RateLimit.from_string("1/s"), key=throttled_key)(mock_fn)()
    rate_limit(rate=RateLimit.from_string("1/s"), key=throttled_key)(mock_fn2)()

    assert mock_fn.call_count == 1
    assert mock_fn2.call_count == 1


def test_rate_limit_per_seconds(clear_throttle_cache):
    mock_fn = get_named_mock(throttled_fn_name)
    rate = RateLimit.from_string("2/s")

    with freeze_time("2023-03-30 00:00:00.00001"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()
    with freeze_time("2023-03-30 00:00:00.00002"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()

    with freeze_time("2023-03-30 00:00:00.50000"):
        with pytest.raises(RateLimitExceededException):
            rate_limit(rate=rate, key=throttled_key)(mock_fn)()

    with freeze_time("2023-03-30 00:00:01.00003"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()
    with freeze_time("2023-03-30 00:00:01.00004"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()


def test_rate_limit_per_minute(clear_throttle_cache):
    mock_fn = get_named_mock(throttled_fn_name)
    rate = RateLimit.from_string("2/m")

    with freeze_time("2023-03-30 00:00:00"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()
    with freeze_time("2023-03-30 00:00:01"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()

    with freeze_time("2023-03-30 00:00:02"):
        with pytest.raises(RateLimitExceededException):
            rate_limit(rate=rate, key=throttled_key)(mock_fn)()

    with freeze_time("2023-03-30 00:02:00"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()
    with freeze_time("2023-03-30 00:02:01"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()


def test_rate_limit_per_hour(clear_throttle_cache):
    mock_fn = get_named_mock(throttled_fn_name)
    rate = RateLimit.from_string("2/h")

    with freeze_time("2023-03-30 00:00:00"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()
    with freeze_time("2023-03-30 00:01:00"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()

    with freeze_time("2023-03-30 00:02:00"):
        with pytest.raises(RateLimitExceededException):
            rate_limit(rate=rate, key=throttled_key)(mock_fn)()

    with freeze_time("2023-03-30 01:00:00"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()
    with freeze_time("2023-03-30 01:01:00"):
        rate_limit(rate=rate, key=throttled_key)(mock_fn)()
