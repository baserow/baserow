from django.contrib.auth.models import AnonymousUser
from django.urls import reverse

import pytest
from rest_framework.exceptions import AuthenticationFailed

from baserow.api.user_sources.middleware import AddUserSourceUserMiddleware
from baserow.contrib.builder.preview import BuilderPreviewActor
from baserow.core.user_sources.user_source_user import UserSourceUser


@pytest.mark.django_db
def test_user_source_middleware_adds_user_source_user(
    data_fixture, api_request_factory, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    user_source_user = data_fixture.create_user_source_user(
        user_source=user_source,
    )
    us_token = user_source_user.get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {us_token.access_token}",
    )
    fake_request.user = user

    middleware = AddUserSourceUserMiddleware(lambda: None)

    with stub_user_source_registry():
        middleware.process_request(fake_request)

        # As it's a lazy object we need to access at least one property to load it.
        assert fake_request.user_source_user.is_authenticated

    assert isinstance(fake_request.user_source_user, UserSourceUser)

    # Should user the already authenticated user_source_user if any
    published_builder = data_fixture.create_builder_application(workspace=None)
    data_fixture.create_builder_custom_domain(
        builder=builder, published_to=published_builder
    )
    user_source2 = data_fixture.create_user_source_with_first_type(
        application=published_builder
    )
    user_source_user2 = data_fixture.create_user_source_user(
        user_source=user_source2,
    )

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source2.id},
        ),
        {},
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {us_token.access_token}",
    )
    fake_request.user = user_source_user2

    with stub_user_source_registry():
        middleware.process_request(fake_request)

        # As it's a lazy object we need to access at least one property to load it.
        assert fake_request.user_source_user.is_authenticated

    assert isinstance(fake_request.user_source_user, UserSourceUser)
    assert fake_request.user_source_user.user_source == user_source2


@pytest.mark.django_db
def test_user_source_middleware_adds_user_source_user_from_authorization_for_preview(
    data_fixture, api_request_factory, stub_user_source_registry
):
    user = data_fixture.create_user()
    builder = data_fixture.create_builder_application(user=user)
    user_source = data_fixture.create_user_source_with_first_type(application=builder)

    user_source_user = data_fixture.create_user_source_user(
        user_source=user_source,
    )
    us_token = user_source_user.get_refresh_token()

    fake_request = api_request_factory.post(
        reverse(
            "api:user_sources:token_auth",
            kwargs={"user_source_id": user_source.id},
        ),
        {},
        HTTP_AUTHORIZATION=f"JWT {us_token.access_token}",
    )
    fake_request.user = BuilderPreviewActor(
        builder_id=builder.id,
        workspace_id=builder.workspace_id,
        grant_id=1,
        issued_by_user_id=user.id,
    )

    middleware = AddUserSourceUserMiddleware(lambda: None)

    with stub_user_source_registry():
        middleware.process_request(fake_request)

        # As it's a lazy object we need to access at least one property to load it.
        assert fake_request.user_source_user.is_authenticated

    assert isinstance(fake_request.user_source_user, UserSourceUser)
    assert fake_request.user_source_user.user_source == user_source


@pytest.mark.django_db
def test_user_source_middleware_dont_adds_user_source_user_if_published(
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
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {us_token.access_token}",
    )
    fake_request.user = user

    middleware = AddUserSourceUserMiddleware(lambda: None)

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        middleware.process_request(fake_request)

        # As it's a lazy object we need to access at least one property to load it.
        assert not fake_request.user_source_user.is_authenticated


@pytest.mark.django_db
def test_user_source_middleware_dont_adds_user_source_user_if_no_permissions(
    data_fixture, api_request_factory, stub_user_source_registry
):
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
    fake_request.user = other_user

    middleware = AddUserSourceUserMiddleware(lambda: None)

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        middleware.process_request(fake_request)

        # As it's a lazy object we need to access at least one property to load it.
        assert fake_request.user_source_user.is_authenticated

    fake_request.user = AnonymousUser()

    with pytest.raises(AuthenticationFailed), stub_user_source_registry():
        middleware.process_request(fake_request)

        # As it's a lazy object we need to access at least one property to load it.
        assert fake_request.user_source_user.is_authenticated


@pytest.mark.django_db
def test_user_source_middleware_dont_adds_user_source_bad_token(
    data_fixture, api_request_factory, stub_user_source_registry
):
    user, token = data_fixture.create_user_and_token()
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
        HTTP_USERSOURCEAUTHORIZATION=f"JWT {token}",
    )

    middleware = AddUserSourceUserMiddleware(lambda: None)

    with stub_user_source_registry():
        middleware.process_request(fake_request)

        # As it's a lazy object we need to access at least one property to load it.
        assert not fake_request.user_source_user.is_authenticated
