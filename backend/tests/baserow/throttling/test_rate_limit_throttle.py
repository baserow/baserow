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


class DummyConsumeOnSuccessThrottle(DummyThrottle):
    scope = "dummy_on_success"
    consume_on_success = True


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


def test_consume_on_success_does_not_consume_when_checking():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        for _ in range(10):
            throttle = DummyConsumeOnSuccessThrottle(ONE_PER_MINUTE)
            assert throttle.allow_request(request, None) is True

        DummyConsumeOnSuccessThrottle(ONE_PER_MINUTE).record(request)

        with pytest.raises(ThrottledAPIException):
            DummyConsumeOnSuccessThrottle(ONE_PER_MINUTE).allow_request(request, None)


def test_record_is_a_noop_when_exempt():
    request = DummyRequest()

    with freeze_time("2024-01-01 12:00:00"):
        DummyConsumeOnSuccessThrottle(ONE_PER_MINUTE, ident=None).record(request)
        DummyConsumeOnSuccessThrottle((), ident="1").record(request)

        throttle = DummyConsumeOnSuccessThrottle(ONE_PER_MINUTE)
        assert throttle.allow_request(request, None) is True


def test_the_subclass_hooks_are_required():
    request = DummyRequest()

    with pytest.raises(NotImplementedError):
        RateLimitThrottle().get_rate_limits(request)

    with pytest.raises(NotImplementedError):
        RateLimitThrottle().get_ident(request)
