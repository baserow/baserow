from datetime import timedelta
from urllib.parse import parse_qs, urlparse

from django.urls import reverse

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK, HTTP_302_FOUND, HTTP_404_NOT_FOUND

from baserow.contrib.builder.preview import (
    BUILDER_PREVIEW_TOKEN_QUERY_PARAM,
    BuilderPreviewGrantHandler,
    get_builder_preview_cookie_name,
)


def preview_grant_url(builder_id):
    return f"/api/builder/preview/{builder_id}/grant/"


def preview_exchange_url(token):
    return f"/api/builder/preview/exchange/{token}/"


@pytest.mark.django_db
def test_editor_with_read_access_can_create_and_exchange_preview_token(
    api_client, data_fixture, settings
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://preview.example.com"
    settings.BUILDER_PREVIEW_PATH_PREFIX = ""

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

    assert preview_url.startswith("https://preview.example.com/dashboard")

    clean_url = "https://preview.example.com/dashboard"
    response = api_client.get(
        preview_exchange_url(preview_token),
        {"redirect": clean_url},
    )

    assert response.status_code == HTTP_302_FOUND
    assert response["Location"] == clean_url
    assert response.cookies[get_builder_preview_cookie_name()]["httponly"]
    assert response.cookies[get_builder_preview_cookie_name()]["secure"]

    second_response = api_client.get(
        preview_exchange_url(preview_token),
        {"redirect": clean_url},
    )
    assert second_response.status_code == HTTP_302_FOUND


@pytest.mark.django_db
def test_exchange_uses_lax_insecure_cookie_for_same_site_http_preview(
    api_client, data_fixture, settings
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    settings.PUBLIC_BACKEND_URL = "http://api.getbaserow.io:8000"
    settings.BUILDER_PREVIEW_URL = "http://preview.getbaserow.io:3000"
    settings.BUILDER_PREVIEW_PATH_PREFIX = ""

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
        {"redirect": ("http://preview.getbaserow.io:3000/")},
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
    settings.BUILDER_PREVIEW_PATH_PREFIX = ""

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
        {"redirect": ("http://preview.getbaserow.io:3000/")},
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
    settings.BUILDER_PREVIEW_PATH_PREFIX = ""
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
        {"redirect": "https://preview.example.com/"},
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
def test_preview_grant_url_uses_configured_path_prefix(data_fixture, settings):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    settings.BUILDER_PREVIEW_URL = "https://example.com"
    settings.BUILDER_PREVIEW_PATH_PREFIX = "/builder-preview"

    url = BuilderPreviewGrantHandler().get_preview_url(
        builder.id, "/dashboard?foo=bar", "token"
    )
    expected_url = (
        "https://example.com/builder-preview/dashboard?foo=bar&preview_token=token"
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
        {"redirect": "https://preview.example.com/"},
    )

    response = api_client.get(
        reverse(
            "api:builder:domains:get_builder_by_id", kwargs={"builder_id": builder.id}
        ),
        format="json",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == builder.id

    other_response = api_client.get(
        reverse(
            "api:builder:domains:get_builder_by_id",
            kwargs={"builder_id": other_builder.id},
        ),
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
        {"redirect": "https://preview.example.com/"},
    )

    response = api_client.get(
        reverse("api:builder:preview:current"),
        format="json",
    )

    assert response.status_code == HTTP_200_OK
    assert response.json()["id"] == builder.id


@pytest.mark.django_db
def test_editor_jwt_is_not_accepted_by_draft_preview_endpoint(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)

    response = api_client.get(
        reverse(
            "api:builder:domains:get_builder_by_id", kwargs={"builder_id": builder.id}
        ),
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

    api_client.cookies[get_builder_preview_cookie_name()] = token

    with freeze_time("2024-01-01 12:30:01"):
        response = api_client.get(
            reverse(
                "api:builder:domains:get_builder_by_id",
                kwargs={"builder_id": builder.id},
            ),
            format="json",
        )

    assert response.status_code != HTTP_200_OK
