from unittest import mock

from django.urls import reverse

import pytest
from rest_framework.exceptions import AuthenticationFailed

from baserow.api.user_sources.authentication import UserSourceJSONWebTokenAuthentication
from baserow.core.models import Application
from baserow.core.user.exceptions import UserNotFound
from baserow.core.user_sources.constants import USER_SOURCE_CLAIM
from baserow.core.user_sources.user_source_user import UserSourceUser


@pytest.mark.django_db
def test_user_source_auth_get_header(data_fixture, api_request_factory):
    _, token = data_fixture.create_user_and_token()
    _, token2 = data_fixture.create_user_and_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:builder:domains:get_builder_by_domain_name",
            kwargs={"domain_name": "test.getbaserow.io"},
        ),
        HTTP_AUTHORIZATION=f"JWT {token}",
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {token2}",
    )

    auth = UserSourceJSONWebTokenAuthentication()
    assert auth.get_header(fake_request) == bytes(f"JWT {token}", "utf-8")

    auth = UserSourceJSONWebTokenAuthentication(
        use_user_source_authentication_header=True
    )
    assert auth.get_header(fake_request) == bytes(f"JWT {token2}", "utf-8")


@pytest.mark.django_db
def test_user_source_authenticate(
    data_fixture, api_request_factory, stub_user_source_registry
):
    """
    Checks authentication with a published user source.
    """

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    us_token = data_fixture.create_user_source_user(
        user_source=user_source,
    ).get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT {us_token.access_token}",
    )

    auth = UserSourceJSONWebTokenAuthentication()

    with stub_user_source_registry():
        authenticated_user, token = auth.authenticate(fake_request)

    assert isinstance(authenticated_user, UserSourceUser)
    assert token["token_type"] == "access_user_source"
    assert token["user_source_uid"] == user_source.uid


@pytest.mark.django_db
def test_user_source_dont_authenticate_with_unpublished_user_source(
    data_fixture, api_request_factory, stub_user_source_registry
):
    """
    Checks authentication with an unpublished user source fails.
    """

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)
    builder2 = data_fixture.create_builder_application(user=user)
    user_source2 = data_fixture.create_user_source_with_first_type(application=builder2)

    us_token = data_fixture.create_user_source_user(
        user_source=user_source2,
    ).get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT {us_token.access_token}",
    )

    auth = UserSourceJSONWebTokenAuthentication()
    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        auth.authenticate(fake_request)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "use_user_source_auth_header",
    [
        True,
        False,
    ],
)
def test_user_source_authentication_handles_deleted_application(
    data_fixture,
    api_request_factory,
    stub_user_source_registry,
    use_user_source_auth_header,
):
    """
    Ensure that an appropriate error is returned if the application doesn't
    exist, e.g. it was deleted.
    """

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    us_token = data_fixture.create_user_source_user(
        user_source=user_source,
    ).get_refresh_token()

    if use_user_source_auth_header:
        auth_header = {
            "HTTP_USERSOURCEAUTHORIZATION": f"JWT {us_token.access_token}",
        }
    else:
        auth_header = {
            "HTTP_AUTHORIZATION": f"JWT {us_token.access_token}",
        }

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        **auth_header,
    )
    fake_request.user = user

    auth = UserSourceJSONWebTokenAuthentication(
        use_user_source_authentication_header=use_user_source_auth_header
    )

    with mock.patch(
        "baserow.api.user_sources.authentication.CoreHandler.check_permissions",
        side_effect=Application.DoesNotExist("This builder app doesn't exist!"),
    ):
        with stub_user_source_registry():
            with pytest.raises(AuthenticationFailed) as e:
                auth.authenticate(fake_request)


@pytest.mark.django_db
def test_user_source_authenticate_with_custom_header(
    data_fixture, api_request_factory, stub_user_source_registry
):
    """
    Checks authentication with a custom header works if you are authenticated.
    """

    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    us_token = data_fixture.create_user_source_user(
        user_source=user_source,
    ).get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {us_token.access_token}",
    )
    fake_request.user = user

    auth = UserSourceJSONWebTokenAuthentication(
        use_user_source_authentication_header=True
    )

    with stub_user_source_registry():
        authenticated_user, token = auth.authenticate(fake_request)

    assert isinstance(authenticated_user, UserSourceUser)
    assert token["token_type"] == "access_user_source"
    assert token["user_source_uid"] == user_source.uid


@pytest.mark.django_db
def test_user_source_dont_authenticate_with_custom_header_if_no_permission(
    data_fixture, api_request_factory, stub_user_source_registry
):
    """
    Checks authentication with a custom header works if you are authenticated.
    """

    # Fails if unpublished and no user in request
    user = data_fixture.create_user()
    other_user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    us_token = data_fixture.create_user_source_user(
        user_source=user_source,
    ).get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {us_token.access_token}",
    )

    auth = UserSourceJSONWebTokenAuthentication(
        use_user_source_authentication_header=True
    )

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        auth.authenticate(fake_request)

    # Should also fail if the user doesn't have the permissions on the user_source
    fake_request.user = other_user

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        auth.authenticate(fake_request)

    # And also if the builder is published
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    us_token = data_fixture.create_user_source_user(
        user_source=user_source2,
    ).get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source2.id},
        ),
        {},
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {us_token.access_token}",
    )

    fake_request.user = user

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        auth.authenticate(fake_request)


@pytest.mark.django_db
def test_user_source_dont_authenticate_with_refresh_token(
    data_fixture, api_request_factory, stub_user_source_registry
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

    us_token = data_fixture.create_user_source_user(
        user_source=user_source,
    ).get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT {us_token}",
    )

    auth = UserSourceJSONWebTokenAuthentication()

    assert auth.authenticate(fake_request) is None


@pytest.mark.django_db
def test_user_source_dont_authenticate_with_invalid_token(
    data_fixture, api_request_factory, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source1.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT invalid token",
    )

    auth = UserSourceJSONWebTokenAuthentication()

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        auth.authenticate(fake_request)


@pytest.mark.django_db
def test_user_source_dont_authenticate_with_invalid_user_source_uid(
    data_fixture, api_request_factory, stub_user_source_registry
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

    us_token = data_fixture.create_user_source_user(
        user_source=user_source,
    ).get_refresh_token()

    us_token[USER_SOURCE_CLAIM] = "fake uid"

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT {us_token.access_token}",
    )

    auth = UserSourceJSONWebTokenAuthentication()

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        auth.authenticate(fake_request)


@pytest.mark.django_db
def test_user_source_dont_authenticate_with_main_auth_token(
    data_fixture, api_request_factory, stub_user_source_registry
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

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    auth = UserSourceJSONWebTokenAuthentication()

    with stub_user_source_registry():
        assert auth.authenticate(fake_request) is None


@pytest.mark.django_db
def test_user_source_dont_authenticate_missing_user(
    data_fixture, api_request_factory, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source1 = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source1.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT invalid token",
    )

    auth = UserSourceJSONWebTokenAuthentication()

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        auth.authenticate(fake_request)


@pytest.mark.django_db
def test_user_source_authenticate_missing_user(
    data_fixture, api_request_factory, stub_user_source_registry
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

    us_token = data_fixture.create_user_source_user(
        user_source=user_source,
    ).get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT {us_token.access_token}",
    )

    auth = UserSourceJSONWebTokenAuthentication()

    def get_user_raise_user_not_found(*args, **kwargs):
        raise UserNotFound()

    with pytest.raises(AuthenticationFailed), stub_user_source_registry(
        get_user_return=get_user_raise_user_not_found
    ):
        auth.authenticate(fake_request)
