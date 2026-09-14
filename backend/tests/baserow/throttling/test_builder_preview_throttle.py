import pytest
from rest_framework.request import Request
from rest_framework.test import APIRequestFactory

from baserow.api.exceptions import ThrottledAPIException
from baserow.contrib.builder.preview import BuilderPreviewActor
from baserow.throttling.handler import ConcurrentUserRequestsThrottle


def test_builder_preview_requests_are_throttled_and_release_their_slot(
    settings, monkeypatch
):
    """Preview actors obey the concurrency limit and free their slot after a response."""

    settings.BASEROW_THROTTLE_BLACKLIST_TTL_SECONDS = 0
    monkeypatch.setattr(ConcurrentUserRequestsThrottle, "rate", 1, raising=False)
    actor = BuilderPreviewActor(
        builder_id=1, workspace_id=1, grant_id=12345, issued_by_user_id=1
    )
    request = Request(APIRequestFactory().get("/api/builder/preview/1/current/"))
    request.user = actor

    throttle = ConcurrentUserRequestsThrottle()
    assert throttle.allow_request(request, None)
    try:
        with pytest.raises(ThrottledAPIException):
            ConcurrentUserRequestsThrottle().allow_request(request, None)
    finally:
        ConcurrentUserRequestsThrottle.on_request_processed(request._request)

    assert ConcurrentUserRequestsThrottle().allow_request(request, None)
    ConcurrentUserRequestsThrottle.on_request_processed(request._request)
