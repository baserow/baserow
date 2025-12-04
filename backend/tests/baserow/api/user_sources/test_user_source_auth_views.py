from unittest.mock import patch

from django.urls import reverse

import pytest
from rest_framework import exceptions
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)
from rest_framework_simplejwt.exceptions import TokenError

from baserow.core.models import BlacklistedToken
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.exceptions import UserSourceImproperlyConfigured
from baserow.core.user_sources.jwt_token import UserSourceToken
from baserow.core.utils import generate_hash


@pytest.mark.django_db
def test_obtain_json_web_token(api_client, data_fixture, stub_user_source_registry):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:user_sources:token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"email": "e@ma.il", "password": "password"},
            format="json",
        )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert "refresh_token" in response_json
    assert "access_token" in response_json


@pytest.mark.django_db
def test_obtain_json_web_token_not_configured(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:user_sources:token_auth", kwargs={"user_source_id": user_source.id}
    )

    def raise_improperly_configured(*args, **kargs):
        raise UserSourceImproperlyConfigured()

    with stub_user_source_registry(authenticate_return=raise_improperly_configured):
        response = api_client.post(
            url,
            {"email": "e@ma.il", "password": "password"},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response_json["error"] == "ERROR_USER_SOURCE_IMPROPERLY_CONFIGURED"


@pytest.mark.django_db
def test_obtain_json_web_token_invalid_user_source(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_auth", kwargs={"user_source_id": 0})

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"email": "e@ma.il", "password": "password"},
            format="json",
        )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_obtain_json_web_token_no_creds(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:user_sources:token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "email" in response_json
    assert "password" in response_json


@pytest.mark.django_db
def test_obtain_json_web_token_unpublished_but_auth(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse(
        "api:user_sources:token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"email": "e@ma.il", "password": "password"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_obtain_json_web_token_auth_failed(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:user_sources:token_auth", kwargs={"user_source_id": user_source.id}
    )

    def raise_auth_exception(*args, **kwargs):
        raise exceptions.AuthenticationFailed(
            detail={
                "detail": "Auth failed",
                "error": "auth_failed",
            },
            code="auth_failed",
        )

    with stub_user_source_registry(authenticate_return=raise_auth_exception):
        response = api_client.post(
            url,
            {"email": "e@ma.il", "password": "password"},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_CREDENTIALS"


@pytest.mark.django_db
def test_obtain_json_web_token_missing_user(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:user_sources:token_auth", kwargs={"user_source_id": user_source.id}
    )

    def raise_not_found_exception(*args, **kwargs):
        raise UserNotFound()

    with stub_user_source_registry(authenticate_return=raise_not_found_exception):
        response = api_client.post(
            url,
            {"email": "e@ma.il", "password": "password"},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_CREDENTIALS"


@pytest.mark.django_db
def test_obtain_json_web_token_unpublished(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse(
        "api:user_sources:token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"email": "e@ma.il", "password": "password"},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_obtain_json_web_token_already_auth_other_user(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    other_user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=other_user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:user_sources:token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"email": "e@ma.il", "password": "password"},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_force_obtain_json_web_token(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse(
        "api:user_sources:force_token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"user_id": 42},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "refresh_token" in response_json
    assert "access_token" in response_json


@pytest.mark.django_db
def test_force_obtain_json_web_token_invalid_source(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse("api:user_sources:force_token_auth", kwargs={"user_source_id": 0})

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"user_id": 42},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_404_NOT_FOUND


@pytest.mark.django_db
def test_force_obtain_json_web_token_no_creds(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse(
        "api:user_sources:force_token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "user_id" in response_json


@pytest.mark.django_db
def test_force_obtain_json_web_token_other_user(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    other_user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=other_user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse(
        "api:user_sources:force_token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"user_id": 42},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_force_obtain_json_web_token_published(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:user_sources:force_token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"user_id": 42},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_force_obtain_json_web_token_published_no_auth(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:user_sources:force_token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"user_id": 42},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_force_obtain_json_web_token_no_auth(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse(
        "api:user_sources:force_token_auth", kwargs={"user_source_id": user_source.id}
    )

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"user_id": 42},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["detail"] == "Authentication credentials were not provided."


@pytest.mark.django_db
def test_force_obtain_json_web_token_user_not_found(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse(
        "api:user_sources:force_token_auth", kwargs={"user_source_id": user_source.id}
    )

    def raise_user_not_found(*args, **kwargs):
        raise UserNotFound()

    with stub_user_source_registry(get_user_return=raise_user_not_found):
        response = api_client.post(
            url,
            {"user_id": 42},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert (
        response_json["detail"] == "No active account found with the given credentials."
    )


@pytest.mark.django_db
def test_refresh_json_web_token(api_client, data_fixture, stub_user_source_registry):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_refresh")

    us_user = data_fixture.create_user_source_user(user_source=user_source)

    with stub_user_source_registry(get_user_return=us_user):
        response = api_client.post(
            url,
            {"refresh_token": str(us_user.get_refresh_token())},
            format="json",
        )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert "access_token" in response_json
    assert "refresh_token" not in response_json

    with (
        patch("baserow.api.user_sources.serializers.jwt_settings") as mocked_settings,
        stub_user_source_registry(get_user_return=us_user),
    ):
        mocked_settings.ROTATE_REFRESH_TOKENS = True
        mocked_settings.BLACKLIST_AFTER_ROTATION = False
        mocked_settings.USER_ID_CLAIM = "user_id"

        response = api_client.post(
            url,
            {"refresh_token": str(us_user.get_refresh_token())},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "access_token" in response_json
    assert "refresh_token" in response_json

    assert BlacklistedToken.objects.count() == 0

    token = us_user.get_refresh_token()
    with (
        patch("baserow.api.user_sources.serializers.jwt_settings") as mocked_settings,
        stub_user_source_registry(get_user_return=us_user),
    ):
        mocked_settings.ROTATE_REFRESH_TOKENS = True
        mocked_settings.BLACKLIST_AFTER_ROTATION = True
        mocked_settings.USER_ID_CLAIM = "user_id"
        response = api_client.post(
            url,
            {"refresh_token": str(token)},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert "access_token" in response_json
    assert "refresh_token" in response_json

    assert BlacklistedToken.objects.count() == 1

    with pytest.raises(TokenError):
        token.check_blacklist()


@pytest.mark.django_db
def test_refresh_json_web_token_update_user(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_refresh")

    us_user = data_fixture.create_user_source_user(
        user_source=user_source, username="before", email="before@before.com"
    )
    refresh_token = us_user.get_refresh_token()

    modified_user = data_fixture.create_user_source_user(
        user_source=user_source, username="after", email="after@after.com"
    )

    with stub_user_source_registry(get_user_return=modified_user):
        response = api_client.post(
            url,
            {"refresh_token": str(refresh_token)},
            format="json",
        )

    response_json = response.json()

    assert response.status_code == HTTP_200_OK
    assert "access_token" in response_json
    assert "refresh_token" in response_json

    updated_token = UserSourceToken(response_json["refresh_token"])
    assert updated_token["exp"] == refresh_token["exp"]
    assert updated_token["username"] == "after"


@pytest.mark.django_db
def test_refresh_json_web_token_fails_with_deleted_user(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_refresh")

    us_user = data_fixture.create_user_source_user(user_source=user_source)

    def raise_user_not_found(*args, **kwargs):
        raise UserNotFound()

    with stub_user_source_registry(get_user_return=raise_user_not_found):
        response = api_client.post(
            url,
            {"refresh_token": str(us_user.get_refresh_token())},
            format="json",
        )

    response_json = response.json()

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_json_web_token_fails_with_trashed_table(api_client, data_fixture):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    table = data_fixture.create_database_table(user=user, trashed=True)
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder, table=table
    )

    url = reverse("api:user_sources:token_refresh")
    us_user = data_fixture.create_user_source_user(user_source=user_source)

    response = api_client.post(
        url,
        {"refresh_token": str(us_user.get_refresh_token())},
        format="json",
    )
    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_json_web_token_blacklisted(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_refresh")

    us_user = data_fixture.create_user_source_user(user_source=user_source)

    refresh = us_user.get_refresh_token()
    refresh.blacklist()

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"refresh_token": str(refresh)},
            format="json",
        )

    response_json = response.json()

    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_json_web_token_no_refresh(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_refresh")

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {},
            format="json",
        )

    response_json = response.json()

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert "refresh_token" in response_json


@pytest.mark.django_db
def test_refresh_json_web_token_no_user_source(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_refresh")

    us_user = data_fixture.create_user_source_user(user_source=user_source)

    refresh = str(us_user.get_refresh_token())

    user_source.delete()

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"refresh_token": refresh},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_json_web_token_invalid_token(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_refresh")

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"refresh_token": "JWT invalid_token"},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_json_web_token_another_token(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse("api:user_sources:token_refresh")

    with stub_user_source_registry():
        response = api_client.post(
            url,
            {"refresh_token": f"JWT {token}"},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "ERROR_INVALID_REFRESH_TOKEN"


@pytest.mark.django_db
def test_refresh_json_web_token_unpublished(
    api_client, data_fixture, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse("api:user_sources:token_refresh")

    us_user = data_fixture.create_user_source_user(user_source=user_source)

    with stub_user_source_registry(get_user_return=us_user):
        response = api_client.post(
            url,
            {"refresh_token": str(us_user.get_refresh_token())},
            format="json",
        )

    response_json = response.json()
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response_json["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_refresh_json_web_token_unpublished_auth(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    url = reverse("api:user_sources:token_refresh")

    us_user = data_fixture.create_user_source_user(user_source=user_source)

    with stub_user_source_registry(get_user_return=us_user):
        response = api_client.post(
            url,
            {"refresh_token": str(us_user.get_refresh_token())},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_get_user_sources_with_user_source_auth_token(
    api_client, data_fixture, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)

    domain = data_fixture.create_builder_custom_domain(
        domain_name="test.getbaserow.io", published_to=published_builder
    )

    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    url = reverse(
        "api:builder:domains:get_builder_by_domain_name",
        kwargs={"domain_name": "test.getbaserow.io"},
    )
    us_user = data_fixture.create_user_source_user(user_source=user_source)

    with stub_user_source_registry(get_user_return=us_user):
        response = api_client.get(
            url,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {us_user.get_refresh_token().access_token}",
        )

    # Try to access a public to check that everything works as intended when e2e
    # testing
    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
def test_user_source_token_blacklist(api_client, data_fixture):
    published_builder = data_fixture.create_builder_application(workspace=None)

    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    us_user = data_fixture.create_user_source_user(user_source=user_source)

    refresh_token = us_user.get_refresh_token()
    refresh_token_str = str(us_user.get_refresh_token())

    response = api_client.post(
        reverse("api:user_sources:token_blacklist"),
        {"refresh_token": refresh_token_str},
        format="json",
    )

    assert response.status_code == HTTP_204_NO_CONTENT

    token = BlacklistedToken.objects.all().first()
    assert token.hashed_token == generate_hash(refresh_token_str)
    assert token.expires_at.timestamp() == refresh_token.payload["exp"]
