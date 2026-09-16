from unittest.mock import patch

from django.shortcuts import reverse

import pytest
from rest_framework.exceptions import AuthenticationFailed

from baserow.api.authentication import JSONWebTokenAuthentication


@pytest.mark.django_db
def test_authenticate_fails_with_user_source_token(data_fixture, api_request_factory):
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

    refresh_token = data_fixture.create_user_source_user(
        user_source=user_source,
        user_id=user.id,  # The user_source id match an existing user
    ).get_refresh_token()

    access_token = refresh_token.access_token

    fake_request = api_request_factory.post(
        reverse("api:workspaces:list"),
        {},
        HTTP_AUTHORIZATION=f"JWT {access_token}",
    )

    auth = JSONWebTokenAuthentication()

    with patch.object(auth, "get_user") as get_user:
        with pytest.raises(AuthenticationFailed):
            auth.authenticate(fake_request)
        get_user.assert_not_called()

    fake_request = api_request_factory.post(
        reverse("api:workspaces:list"),
        {},
        HTTP_AUTHORIZATION=f"JWT {refresh_token}",
    )

    auth = JSONWebTokenAuthentication()

    with patch.object(auth, "get_user") as get_user:
        with pytest.raises(AuthenticationFailed):
            auth.authenticate(fake_request)
        get_user.assert_not_called()
