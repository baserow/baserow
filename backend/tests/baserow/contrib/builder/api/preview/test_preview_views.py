from concurrent.futures import ThreadPoolExecutor
from datetime import timedelta
from threading import Barrier
from unittest.mock import patch
from urllib.parse import parse_qs, urlparse

from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_302_FOUND,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.builder.preview import (
    BUILDER_PREVIEW_HANDOFF_QUERY_PARAM,
    BUILDER_PREVIEW_TOKEN_QUERY_PARAM,
    BuilderPreviewGrantHandler,
    BuilderPreviewGrantInvalid,
    get_builder_preview_cookie_name,
    get_builder_preview_cookie_path,
)
from baserow.core.cache import global_cache


def preview_grant_url(builder_id):
    return f"/api/builder/preview/{builder_id}/grant/"


def preview_exchange_url(token):
    return f"/api/builder/preview/exchange/{token}/"


def preview_handoff_url():
    return "/api/builder/preview/handoff/"


def current_preview_url(builder_id):
    return reverse("api:builder:preview:current", kwargs={"builder_id": builder_id})


@pytest.mark.django_db
def test_editor_with_read_access_can_create_and_exchange_preview_token(
    api_client, data_fixture, settings
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://preview.example.com"

    response = api_client.post(
        preview_grant_url(builder.id),
        {"path": "/dashboard?foo=bar"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    preview_url = response.json()["url"]
    parsed_preview_url = urlparse(preview_url)
    preview_query = parse_qs(parsed_preview_url.query)
    preview_token = preview_query[BUILDER_PREVIEW_TOKEN_QUERY_PARAM][0]

    assert preview_url.startswith(
        f"https://preview.example.com/builder/preview/{builder.id}/dashboard"
    )

    clean_url = (
        f"https://preview.example.com/builder/preview/{builder.id}/dashboard?foo=bar"
    )
    response = api_client.get(
        preview_exchange_url(preview_token),
        {"redirect": clean_url},
    )

    assert response.status_code == HTTP_302_FOUND
    parsed_redirect = urlparse(response["Location"])
    redirect_query = parse_qs(parsed_redirect.query)
    handoff_code = redirect_query.pop(BUILDER_PREVIEW_HANDOFF_QUERY_PARAM)[0]
    assert parsed_redirect._replace(query="").geturl() == (
        f"https://preview.example.com/builder/preview/{builder.id}/dashboard"
    )
    assert redirect_query == {"foo": ["bar"]}
    assert preview_token not in response["Location"]
    preview_cookie = response.cookies[get_builder_preview_cookie_name()]
    assert preview_cookie["httponly"]
    assert preview_cookie["secure"]
    assert preview_cookie["path"] == get_builder_preview_cookie_path(builder.id)
    assert preview_cookie.value != preview_token
    assert preview_cookie.value not in response["Location"]

    handoff_response = api_client.post(
        preview_handoff_url(),
        {
            BUILDER_PREVIEW_HANDOFF_QUERY_PARAM: handoff_code,
            "builder_id": builder.id,
        },
        format="json",
    )

    assert handoff_response.status_code == HTTP_200_OK
    assert handoff_response.json()["preview_session"] == preview_cookie.value
    assert handoff_response.json()["builder_id"] == builder.id
    assert 0 < handoff_response.json()["expires_in"] <= 30 * 60
    assert handoff_response["Cache-Control"] == "no-store"

    second_response = api_client.get(
        preview_exchange_url(preview_token),
        {"redirect": clean_url},
    )
    assert second_response.status_code == HTTP_404_NOT_FOUND

    reused_handoff_response = api_client.post(
        preview_handoff_url(),
        {
            BUILDER_PREVIEW_HANDOFF_QUERY_PARAM: handoff_code,
            "builder_id": builder.id,
        },
        format="json",
    )
    assert reused_handoff_response.status_code == HTTP_200_OK
    assert reused_handoff_response.json() == handoff_response.json()
    assert reused_handoff_response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_exchange_redirect_preserves_query_and_fragment(
    api_client, data_fixture, settings
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://preview.example.com"
    token = BuilderPreviewGrantHandler().create_grant(builder, user)

    response = api_client.get(
        preview_exchange_url(token),
        {
            "redirect": (
                f"https://preview.example.com/builder/preview/{builder.id}/page"
                "?foo=one&foo=two&blank=#section"
            )
        },
    )

    redirect = urlparse(response["Location"])
    assert redirect.path == f"/builder/preview/{builder.id}/page"
    assert parse_qs(redirect.query, keep_blank_values=True) == {
        "foo": ["one", "two"],
        "blank": [""],
        BUILDER_PREVIEW_HANDOFF_QUERY_PARAM: [
            parse_qs(redirect.query)[BUILDER_PREVIEW_HANDOFF_QUERY_PARAM][0]
        ],
    }
    assert redirect.fragment == "section"


@pytest.mark.django_db
def test_exchange_rejects_redirect_for_another_builder(
    api_client, data_fixture, settings
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    other_builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://preview.example.com"
    token = BuilderPreviewGrantHandler().create_grant(builder, user)

    response = api_client.get(
        preview_exchange_url(token),
        {
            "redirect": (
                f"https://preview.example.com/builder/preview/{other_builder.id}/page"
            )
        },
    )

    assert urlparse(response["Location"]).path == (f"/builder/preview/{builder.id}/")


@pytest.mark.django_db
def test_invalid_and_expired_preview_handoffs_return_no_store_404(
    api_client, data_fixture, settings
):
    invalid_response = api_client.post(
        preview_handoff_url(),
        {BUILDER_PREVIEW_HANDOFF_QUERY_PARAM: "invalid", "builder_id": 1},
        format="json",
    )

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_GRANT_TTL = timedelta(minutes=30)
    with freeze_time("2024-01-01 12:00:00"):
        handler = BuilderPreviewGrantHandler()
        token = handler.create_grant(builder, user)
        _, session_token = handler.exchange_token(token)
        handoff_code = handler.create_handoff(session_token, builder.id)

    with freeze_time("2024-01-01 12:01:01"):
        expired_response = api_client.post(
            preview_handoff_url(),
            {
                BUILDER_PREVIEW_HANDOFF_QUERY_PARAM: handoff_code,
                "builder_id": builder.id,
            },
            format="json",
        )

    for response in (invalid_response, expired_response):
        assert response.status_code == HTTP_404_NOT_FOUND
        assert response["Cache-Control"] == "no-store"


@pytest.mark.django_db
def test_preview_handoff_uses_configured_lifetime(api_client, data_fixture, settings):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_HANDOFF_TTL_SECONDS = 5 * 60

    with freeze_time("2024-01-01 12:00:00"):
        handler = BuilderPreviewGrantHandler()
        token = handler.create_grant(builder, user)
        _, session_token = handler.exchange_token(token)
        handoff_code = handler.create_handoff(session_token, builder.id)

    with freeze_time("2024-01-01 12:01:01"):
        response = api_client.post(
            preview_handoff_url(),
            {
                BUILDER_PREVIEW_HANDOFF_QUERY_PARAM: handoff_code,
                "builder_id": builder.id,
            },
            format="json",
        )

    assert response.status_code == HTTP_200_OK
    assert response.json()["preview_session"] == session_token


@pytest.mark.django_db
def test_preview_handoff_rejects_route_builder_mismatch(api_client, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    other_builder = data_fixture.create_builder_application(user=user)
    handler = BuilderPreviewGrantHandler()
    token = handler.create_grant(builder, user)
    _, session_token = handler.exchange_token(token)
    handoff_code = handler.create_handoff(session_token, builder.id)

    response = api_client.post(
        preview_handoff_url(),
        {
            BUILDER_PREVIEW_HANDOFF_QUERY_PARAM: handoff_code,
            "builder_id": other_builder.id,
        },
        format="json",
    )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_concurrent_preview_handoff_exchanges_are_idempotent(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    handler = BuilderPreviewGrantHandler()
    token = handler.create_grant(builder, user)
    _, session_token = handler.exchange_token(token)
    handoff_code = handler.create_handoff(session_token, builder.id)
    barrier = Barrier(2)

    def exchange():
        barrier.wait()
        try:
            return handler.exchange_handoff(handoff_code)
        except BuilderPreviewGrantInvalid:
            return None

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: exchange(), range(2)))

    assert results == [
        (session_token, pytest.approx(30 * 60, abs=1), builder.id),
        (session_token, pytest.approx(30 * 60, abs=1), builder.id),
    ]


@pytest.mark.django_db
def test_preview_handoff_replay_uses_fixed_handoff_lifetime(data_fixture, settings):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_HANDOFF_TTL_SECONDS = 60

    with freeze_time("2024-01-01 12:00:00"):
        handler = BuilderPreviewGrantHandler()
        token = handler.create_grant(builder, user)
        _, session_token = handler.exchange_token(token)
        handoff_code = handler.create_handoff(session_token, builder.id)
        assert handler.exchange_handoff(handoff_code)[0] == session_token

    with freeze_time("2024-01-01 12:00:59"):
        assert handler.exchange_handoff(handoff_code)[0] == session_token

    with freeze_time("2024-01-01 12:01:01"):
        with pytest.raises(BuilderPreviewGrantInvalid):
            handler.exchange_handoff(handoff_code)


@pytest.mark.django_db
def test_exchange_uses_lax_insecure_cookie_for_same_site_http_preview(
    api_client, data_fixture, settings
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    settings.PUBLIC_BACKEND_URL = "http://api.getbaserow.io:8000"
    settings.BUILDER_PREVIEW_URL = "http://preview.getbaserow.io:3000"

    grant_response = api_client.post(
        preview_grant_url(builder.id),
        {"path": "/"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    preview_token = parse_qs(urlparse(grant_response.json()["url"]).query)[
        BUILDER_PREVIEW_TOKEN_QUERY_PARAM
    ][0]

    response = api_client.get(
        preview_exchange_url(preview_token),
        {
            "redirect": (
                f"http://preview.getbaserow.io:3000/builder/preview/{builder.id}/"
            )
        },
    )

    cookie = response.cookies[get_builder_preview_cookie_name()]
    assert response.status_code == HTTP_302_FOUND
    assert cookie["samesite"] == "Lax"
    assert not cookie["secure"]


@pytest.mark.django_db
def test_exchange_uses_none_secure_cookie_for_cross_site_preview(
    api_client, data_fixture, settings
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    settings.PUBLIC_BACKEND_URL = "http://localhost:8000"
    settings.BUILDER_PREVIEW_URL = "http://preview.getbaserow.io:3000"

    grant_response = api_client.post(
        preview_grant_url(builder.id),
        {"path": "/"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    preview_token = parse_qs(urlparse(grant_response.json()["url"]).query)[
        BUILDER_PREVIEW_TOKEN_QUERY_PARAM
    ][0]

    response = api_client.get(
        preview_exchange_url(preview_token),
        {
            "redirect": (
                f"http://preview.getbaserow.io:3000/builder/preview/{builder.id}/"
            )
        },
    )

    cookie = response.cookies[get_builder_preview_cookie_name()]
    assert response.status_code == HTTP_302_FOUND
    assert cookie["samesite"] == "None"
    assert cookie["secure"]


@pytest.mark.django_db
def test_exchange_uses_frontend_cookie_prefix(api_client, data_fixture, settings):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://preview.example.com"
    settings.FRONTEND_COOKIE_PREFIX = "test_"

    grant_response = api_client.post(
        preview_grant_url(builder.id),
        {"path": "/"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    preview_token = parse_qs(urlparse(grant_response.json()["url"]).query)[
        BUILDER_PREVIEW_TOKEN_QUERY_PARAM
    ][0]

    response = api_client.get(
        preview_exchange_url(preview_token),
        {"redirect": f"https://preview.example.com/builder/preview/{builder.id}/"},
    )

    assert response.status_code == HTTP_302_FOUND
    assert "test_baserow_builder_preview" in response.cookies


@pytest.mark.django_db
def test_preview_token_uses_configured_ttl(api_client, data_fixture, settings):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_GRANT_TTL = timedelta(minutes=30)

    with freeze_time("2024-01-01 12:00:00"):
        token = BuilderPreviewGrantHandler().create_grant(builder, user)

    with freeze_time("2024-01-01 12:29:59"):
        valid_response = api_client.get(
            preview_exchange_url(token),
            {"redirect": "https://preview.example.com/"},
        )

    with freeze_time("2024-01-01 12:30:01"):
        expired_response = api_client.get(
            preview_exchange_url(token),
            {"redirect": "https://preview.example.com/"},
        )

    assert valid_response.status_code == HTTP_302_FOUND
    assert expired_response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_preview_grant_cache_entry_is_created_only_when_exchanged(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    handler = BuilderPreviewGrantHandler()

    with patch.object(global_cache, "get", wraps=global_cache.get) as cache_get:
        token = handler.create_grant(builder, user)

        cache_get.assert_not_called()

        handler.exchange_token(token)

        cache_get.assert_called_once()


@pytest.mark.django_db
def test_concurrent_preview_token_exchanges_only_succeed_once(data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    handler = BuilderPreviewGrantHandler()
    token = handler.create_grant(builder, user)
    barrier = Barrier(2)

    def exchange():
        barrier.wait()
        try:
            handler.exchange_token(token)
        except BuilderPreviewGrantInvalid:
            return False
        return True

    with ThreadPoolExecutor(max_workers=2) as executor:
        results = list(executor.map(lambda _: exchange(), range(2)))

    assert sorted(results) == [False, True]


@pytest.mark.django_db
def test_unexchanged_grant_token_does_not_authenticate_preview(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    token = BuilderPreviewGrantHandler().create_grant(builder, user)
    api_client.cookies[get_builder_preview_cookie_name()] = token

    response = api_client.get(
        current_preview_url(builder.id),
        format="json",
    )

    assert response.status_code != HTTP_200_OK


@pytest.mark.django_db
def test_preview_grant_url_uses_fixed_builder_path(data_fixture, settings):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://example.com"

    url = BuilderPreviewGrantHandler().get_preview_url(
        builder.id, "/dashboard?foo=bar", "token"
    )
    expected_url = (
        f"https://example.com/builder/preview/{builder.id}/dashboard"
        "?foo=bar&preview_token=token"
    )

    assert url == expected_url


@pytest.mark.django_db
def test_user_without_read_access_cannot_create_preview_grant(api_client, data_fixture):
    user = data_fixture.create_user()
    _, other_token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    response = api_client.post(
        preview_grant_url(builder.id),
        {"path": "/"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {other_token}",
    )

    assert response.status_code != HTTP_200_OK


@pytest.mark.django_db
def test_exchanged_preview_cookie_authenticates_draft_preview_as_preview_actor(
    api_client, data_fixture, settings
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    other_builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://preview.example.com"

    grant_response = api_client.post(
        preview_grant_url(builder.id),
        {"path": "/"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    preview_token = parse_qs(urlparse(grant_response.json()["url"]).query)[
        BUILDER_PREVIEW_TOKEN_QUERY_PARAM
    ][0]
    api_client.get(
        preview_exchange_url(preview_token),
        {"redirect": f"https://preview.example.com/builder/preview/{builder.id}/"},
    )

    response = api_client.get(
        current_preview_url(builder.id),
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == builder.id

    other_response = api_client.get(
        current_preview_url(other_builder.id),
        format="json",
    )
    assert other_response.status_code != HTTP_200_OK


@pytest.mark.django_db
def test_exchanged_preview_cookie_returns_current_preview_builder(
    api_client, data_fixture, settings
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://preview.example.com"

    grant_response = api_client.post(
        preview_grant_url(builder.id),
        {"path": "/"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    preview_token = parse_qs(urlparse(grant_response.json()["url"]).query)[
        BUILDER_PREVIEW_TOKEN_QUERY_PARAM
    ][0]
    api_client.get(
        preview_exchange_url(preview_token),
        {"redirect": f"https://preview.example.com/builder/preview/{builder.id}/"},
    )

    response = api_client.get(
        current_preview_url(builder.id),
        format="json",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == builder.id


@pytest.mark.django_db
def test_editor_jwt_is_not_accepted_by_draft_preview_endpoint(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    response = api_client.get(
        current_preview_url(builder.id),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code != HTTP_200_OK


@pytest.mark.django_db
def test_expired_preview_cookie_is_rejected(api_client, data_fixture, settings):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_GRANT_TTL = timedelta(minutes=30)

    with freeze_time("2024-01-01 12:00:00"):
        token = BuilderPreviewGrantHandler().create_grant(builder, user)
        _, session_token = BuilderPreviewGrantHandler().exchange_token(token)

    api_client.cookies[get_builder_preview_cookie_name()] = session_token

    with freeze_time("2024-01-01 12:30:01"):
        response = api_client.get(
            current_preview_url(builder.id),
            format="json",
        )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_BUILDER_PREVIEW_SESSION_INVALID",
        "detail": "The builder preview session is missing, invalid, or expired.",
    }


@pytest.mark.django_db
def test_tampered_preview_cookie_returns_preview_session_invalid(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    token = BuilderPreviewGrantHandler().create_grant(builder, user)
    _, session_token = BuilderPreviewGrantHandler().exchange_token(token)
    api_client.cookies[get_builder_preview_cookie_name()] = f"{session_token}tampered"

    response = api_client.get(
        current_preview_url(builder.id),
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_BUILDER_PREVIEW_SESSION_INVALID",
        "detail": "The builder preview session is missing, invalid, or expired.",
    }


@pytest.mark.django_db
def test_preview_route_without_cookie_returns_preview_session_invalid(
    api_client, data_fixture
):
    builder = data_fixture.create_builder_application()
    response = api_client.get(
        current_preview_url(builder.id),
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json() == {
        "error": "ERROR_BUILDER_PREVIEW_SESSION_INVALID",
        "detail": "The builder preview session is missing, invalid, or expired.",
    }


@pytest.mark.django_db
def test_preview_cookie_and_url_cannot_be_swapped_between_builders(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    other_builder = data_fixture.create_builder_application(user=user)
    token = BuilderPreviewGrantHandler().create_grant(builder, user)
    _, session_token = BuilderPreviewGrantHandler().exchange_token(token)
    api_client.cookies[get_builder_preview_cookie_name()] = session_token

    response = api_client.get(
        current_preview_url(other_builder.id),
        format="json",
    )

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "ERROR_BUILDER_PREVIEW_SESSION_INVALID"


@pytest.mark.django_db
def test_unmarked_request_without_cookie_can_access_published_builder(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    data_fixture.create_builder_page(builder=builder, user=user)
    builder.workspace = None
    builder.save()
    data_fixture.create_builder_custom_domain(published_to=builder)

    response = api_client.get(
        reverse(
            "api:builder:domains:get_builder_by_id",
            kwargs={"builder_id": builder.id},
        ),
        format="json",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == builder.id
