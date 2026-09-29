import time

import pytest
from freezegun import freeze_time

from baserow.api.exceptions import ThrottledAPIException
from baserow.throttling.handler import RateLimitThrottle
from baserow.throttling.types import RateLimit


class DummyRequest:
    path = "/api/dummy/"


class DummyThrottle(RateLimitThrottle):
    scope = "dummy"

    def __init__(self, rate_limits=(), ident="1"):
        super().__init__()
        self.rate_limits = rate_limits
        self.ident = ident

    def get_rate_limits(self, request):
        return self.rate_limits

    def get_ident(self, request):
        return self.ident


ONE_PER_MINUTE = (RateLimit(period_in_seconds=60, number_of_calls=1),)
TWO_PER_MINUTE = (RateLimit(period_in_seconds=60, number_of_calls=2),)


def test_allows_requests_within_the_limit():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        assert DummyThrottle(TWO_PER_MINUTE).allow_request(request, None) is True
        assert DummyThrottle(TWO_PER_MINUTE).allow_request(request, None) is True


def test_denies_the_request_that_exceeds_the_limit():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        DummyThrottle(TWO_PER_MINUTE).allow_request(request, None)
        DummyThrottle(TWO_PER_MINUTE).allow_request(request, None)

        throttle = DummyThrottle(TWO_PER_MINUTE)
        with pytest.raises(ThrottledAPIException):
            throttle.allow_request(request, None)

        assert throttle.wait() == 60


def test_the_window_slides():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        DummyThrottle(ONE_PER_MINUTE).allow_request(request, None)

    with freeze_time("2024-01-01 12:00:30"):
        throttle = DummyThrottle(ONE_PER_MINUTE)
        with pytest.raises(ThrottledAPIException):
            throttle.allow_request(request, None)
        assert throttle.wait() == 30

    with freeze_time("2024-01-01 12:01:01"):
        assert DummyThrottle(ONE_PER_MINUTE).allow_request(request, None) is True


def test_the_tightest_exceeded_rate_limit_denies():
    request = DummyRequest()
    rate_limits = (
        RateLimit(period_in_seconds=3600, number_of_calls=10),
        RateLimit(period_in_seconds=60, number_of_calls=2),
    )

    with freeze_time("2024-01-01 12:00:00"):
        for _ in range(2):
            DummyThrottle(rate_limits).allow_request(request, None)

        throttle = DummyThrottle(rate_limits)
        with pytest.raises(ThrottledAPIException):
            throttle.allow_request(request, None)

        # The hourly limit still has room, so the minute limit is the one that
        # decides how long the caller has to wait.
        assert throttle.wait() == 60


def test_wait_time_is_scoped_to_the_window_of_the_violated_rate():
    request = DummyRequest()
    rate_limits = (
        RateLimit(period_in_seconds=3600, number_of_calls=100),
        RateLimit(period_in_seconds=60, number_of_calls=2),
    )

    with freeze_time("2024-01-01 12:00:00"):
        DummyThrottle(rate_limits).allow_request(request, None)
        DummyThrottle(rate_limits).allow_request(request, None)

    # The minute window has cleared, but the calls of 12:00:00 are still in the
    # sorted set because they're within the hour window.
    with freeze_time("2024-01-01 12:02:00"):
        DummyThrottle(rate_limits).allow_request(request, None)
        DummyThrottle(rate_limits).allow_request(request, None)

    with freeze_time("2024-01-01 12:02:30"):
        throttle = DummyThrottle(rate_limits)
        with pytest.raises(ThrottledAPIException):
            throttle.allow_request(request, None)

        # The oldest call in the minute window is the one of 12:02:00, not the
        # one of 12:00:00 that's only still relevant for the hour window.
        assert throttle.wait() == 30


def test_the_longest_wait_of_the_violated_rates_is_reported():
    request = DummyRequest()
    rate_limits = (
        RateLimit(period_in_seconds=60, number_of_calls=2),
        RateLimit(period_in_seconds=3600, number_of_calls=3),
    )

    with freeze_time("2024-01-01 12:00:00"):
        DummyThrottle(rate_limits).allow_request(request, None)

    with freeze_time("2024-01-01 12:30:00"):
        DummyThrottle(rate_limits).allow_request(request, None)
        DummyThrottle(rate_limits).allow_request(request, None)

        throttle = DummyThrottle(rate_limits)
        with pytest.raises(ThrottledAPIException):
            throttle.allow_request(request, None)

        # Both rates are exceeded. Waiting out the minute one isn't enough, so
        # the hour one decides: its oldest call of 12:00:00 leaves that window
        # at 13:00:00.
        assert throttle.wait() == 1800


def test_wait_time_accounts_for_more_calls_in_the_window_than_the_limit():
    request = DummyRequest()
    throttle = DummyThrottle(TWO_PER_MINUTE)

    # A window can hold more calls than the limit allows, for example when the
    # configured limit was lowered while the window was already filling up.
    cache_key = throttle.get_cache_key(request)
    with freeze_time("2024-01-01 12:00:00") as frozen:
        for seconds in [0, 10, 20]:
            throttle.redis_cli.zadd(
                cache_key, {f"call-{seconds}": time.time() + seconds}
            )
        frozen.move_to("2024-01-01 12:00:30")

        with pytest.raises(ThrottledAPIException):
            throttle.allow_request(request, None)

        # Waiting for the oldest call to expire isn't enough, because that still
        # leaves 2 calls in the window. The second oldest, of 12:00:10, is the
        # one that brings the count back under the limit.
        assert throttle.wait() == 40


def test_without_rate_limits_nothing_is_throttled():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        for _ in range(10):
            assert DummyThrottle(()).allow_request(request, None) is True


def test_a_request_without_ident_is_exempt():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        for _ in range(10):
            throttle = DummyThrottle(ONE_PER_MINUTE, ident=None)
            assert throttle.allow_request(request, None) is True


def test_idents_do_not_share_a_window():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        DummyThrottle(ONE_PER_MINUTE, ident="1").allow_request(request, None)

        with pytest.raises(ThrottledAPIException):
            DummyThrottle(ONE_PER_MINUTE, ident="1").allow_request(request, None)

        assert (
            DummyThrottle(ONE_PER_MINUTE, ident="2").allow_request(request, None)
            is True
        )


def test_the_slot_is_reserved_while_the_request_is_being_handled():
    request = DummyRequest()

    # The check and the reservation are one atomic operation, so a second
    # request can't be allowed while the first one is still being handled.
    with freeze_time("2024-01-01 12:00:00"):
        assert DummyThrottle(ONE_PER_MINUTE).allow_request(request, None) is True

        with pytest.raises(ThrottledAPIException):
            DummyThrottle(ONE_PER_MINUTE).allow_request(request, None)


def test_a_released_slot_does_not_count():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        throttle = DummyThrottle(ONE_PER_MINUTE)
        throttle.allow_request(request, None)
        throttle.release()

        assert DummyThrottle(ONE_PER_MINUTE).allow_request(request, None) is True


def test_releasing_twice_only_gives_one_slot_back():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        first = DummyThrottle(TWO_PER_MINUTE)
        first.allow_request(request, None)
        second = DummyThrottle(TWO_PER_MINUTE)
        second.allow_request(request, None)

        first.release()
        first.release()

        assert DummyThrottle(TWO_PER_MINUTE).allow_request(request, None) is True
        with pytest.raises(ThrottledAPIException):
            DummyThrottle(TWO_PER_MINUTE).allow_request(request, None)


def test_release_without_a_reservation_does_nothing():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        DummyThrottle(ONE_PER_MINUTE, ident=None).release()
        DummyThrottle((), ident="1").release()

        denied = DummyThrottle(ONE_PER_MINUTE)
        denied.allow_request(request, None)
        blocked = DummyThrottle(ONE_PER_MINUTE)
        with pytest.raises(ThrottledAPIException):
            blocked.allow_request(request, None)

        # The denied request never reserved anything, so releasing it must not
        # free the slot of the request that did.
        blocked.release()
        with pytest.raises(ThrottledAPIException):
            DummyThrottle(ONE_PER_MINUTE).allow_request(request, None)


def test_the_subclass_hooks_are_required():
    request = DummyRequest()

    with pytest.raises(NotImplementedError):
        RateLimitThrottle().get_rate_limits(request)

    with pytest.raises(NotImplementedError):
        RateLimitThrottle().get_ident(request)
