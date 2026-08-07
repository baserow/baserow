from django.test import RequestFactory, override_settings

from baserow.core.user.utils import sign_user_session
from baserow_enterprise.api.authentication import extract_user_session_from_request


@override_settings(FRONTEND_COOKIE_PREFIX="")
def test_extract_user_session_from_unprefixed_cookie():
    cookie = sign_user_session(1, "refresh-token")
    request = RequestFactory().get("/", HTTP_COOKIE=f"user_session={cookie}")

    user_session = extract_user_session_from_request(request)

    assert user_session.user_id == "1"


@override_settings(FRONTEND_COOKIE_PREFIX="baserow_3010_")
def test_extract_user_session_from_prefixed_cookie():
    cookie = sign_user_session(2, "refresh-token")
    request = RequestFactory().get(
        "/",
        HTTP_COOKIE=f"baserow_3010_user_session={cookie}",
    )

    user_session = extract_user_session_from_request(request)

    assert user_session.user_id == "2"
