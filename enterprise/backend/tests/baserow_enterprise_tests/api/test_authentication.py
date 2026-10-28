from django.core.signing import BadSignature, TimestampSigner
from django.test import RequestFactory, override_settings

import pytest
from freezegun import freeze_time
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.tokens import RefreshToken

from baserow.core.user.handler import UserHandler
from baserow.core.user.utils import sign_user_session
from baserow.core.utils import generate_hash
from baserow_enterprise.api.authentication import (
    AuthenticateFromUserSessionAuthentication,
    extract_user_session_from_request,
)


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


def _authenticate_user_session(user_session):
    request = RequestFactory().get("/", HTTP_COOKIE=f"user_session={user_session}")
    return AuthenticateFromUserSessionAuthentication().authenticate(request)


@pytest.mark.django_db
@override_settings(FRONTEND_COOKIE_PREFIX="")
def test_user_session_stops_working_when_the_session_is_revoked(data_fixture):
    user = data_fixture.create_user()
    refresh_token = str(RefreshToken.for_user(user))
    rotated = UserHandler().rotate_refresh_token(refresh_token)
    user_session = sign_user_session(user.id, str(rotated))

    assert _authenticate_user_session(user_session)[0] == user

    UserHandler().revoke_refresh_token_session(RefreshToken(refresh_token))

    with pytest.raises(AuthenticationFailed):
        _authenticate_user_session(user_session)


@pytest.mark.django_db
@override_settings(FRONTEND_COOKIE_PREFIX="")
def test_user_session_expires_with_the_refresh_token(data_fixture):
    user = data_fixture.create_user()
    with freeze_time("2026-10-20 09:00"):
        refresh_token = RefreshToken.for_user(user)

    # Signed by the last refresh just before the session ends.
    with freeze_time("2026-10-27 08:59"):
        user_session = sign_user_session(user.id, str(refresh_token))
        assert _authenticate_user_session(user_session)[0] == user

    with freeze_time("2026-10-27 09:01"):
        with pytest.raises(AuthenticationFailed):
            _authenticate_user_session(user_session)


@pytest.mark.django_db
def test_user_session_with_a_session_is_rejected_by_the_previous_release(
    data_fixture,
):
    user = data_fixture.create_user()
    user_session = sign_user_session(user.id, str(RefreshToken.for_user(user)))

    # The previous release reads the cookie with the default salt and can't handle
    # the session keys, so it must get an invalid signature instead.
    with pytest.raises(BadSignature):
        TimestampSigner().unsign_object(user_session)


@pytest.mark.django_db
@override_settings(FRONTEND_COOKIE_PREFIX="")
def test_user_session_signed_by_the_previous_release_still_works(data_fixture):
    user = data_fixture.create_user()
    refresh_token = str(RefreshToken.for_user(user))
    user_session = TimestampSigner().sign_object(
        {"user_id": str(user.id), "token_hash": generate_hash(refresh_token)}
    )

    assert _authenticate_user_session(user_session)[0] == user

    UserHandler().rotate_refresh_token(refresh_token)

    with pytest.raises(AuthenticationFailed):
        _authenticate_user_session(user_session)


@pytest.mark.django_db
@override_settings(FRONTEND_COOKIE_PREFIX="")
def test_user_session_keeps_working_when_the_refresh_token_rotates(data_fixture):
    user = data_fixture.create_user()
    refresh_token = str(RefreshToken.for_user(user))
    user_session = sign_user_session(user.id, refresh_token)

    # A tab still on the previous frontend doesn't write the new user session.
    UserHandler().rotate_refresh_token(refresh_token)

    assert _authenticate_user_session(user_session)[0] == user
