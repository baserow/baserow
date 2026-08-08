from django.shortcuts import reverse
from django.test import override_settings

import pytest
from freezegun import freeze_time
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.throttling.types import RateLimit

HTTP_429_TOO_MANY_REQUESTS = 429


def invite(api_client, data_fixture, user, workspace, email="test@test.nl"):
    # The token must be generated at the (possibly frozen) time of the request,
    # otherwise it isn't valid yet.
    token = data_fixture.generate_token(user)
    return api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace.id}
        ),
        {
            "email": email,
            "permissions": "ADMIN",
            "base_url": "http://localhost:3000/invite",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_invitations_are_not_rate_limited_by_default(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    for index in range(10):
        response = invite(
            api_client, data_fixture, user, workspace, f"test{index}@test.nl"
        )
        assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(
    BASEROW_WORKSPACE_INVITATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=3600, number_of_calls=2),
    ),
)
def test_invitations_are_rate_limited(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with freeze_time("2024-01-01 12:00:00"):
        assert invite(
            api_client, data_fixture, user, workspace, "1@test.nl"
        ).status_code == (HTTP_200_OK)
        assert invite(
            api_client, data_fixture, user, workspace, "2@test.nl"
        ).status_code == (HTTP_200_OK)

        response = invite(api_client, data_fixture, user, workspace, "3@test.nl")

    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
    # The generic throttled response of DRF, so no Baserow specific error code.
    assert "error" not in response.json()
    assert "detail" in response.json()
    assert int(response["Retry-After"]) > 0


@pytest.mark.django_db
@override_settings(
    BASEROW_WORKSPACE_INVITATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=3600, number_of_calls=2),
    ),
)
def test_failing_invitations_do_not_consume_the_rate_limit(api_client, data_fixture):
    user = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(users=[user, member])

    with freeze_time("2024-01-01 12:00:00"):
        # Inviting someone that already is a member fails, and therefore no
        # invitation email is sent.
        for _ in range(5):
            response = invite(api_client, data_fixture, user, workspace, member.email)
            assert response.status_code == HTTP_400_BAD_REQUEST

        assert invite(
            api_client, data_fixture, user, workspace, "1@test.nl"
        ).status_code == (HTTP_200_OK)
        assert invite(
            api_client, data_fixture, user, workspace, "2@test.nl"
        ).status_code == (HTTP_200_OK)
        assert invite(
            api_client, data_fixture, user, workspace, "3@test.nl"
        ).status_code == (HTTP_429_TOO_MANY_REQUESTS)


@pytest.mark.django_db
@override_settings(
    BASEROW_WORKSPACE_INVITATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=3600, number_of_calls=2),
    ),
)
def test_re_inviting_the_same_email_consumes_the_rate_limit(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with freeze_time("2024-01-01 12:00:00"):
        # Every request sends another email, even though the invitation itself is
        # only updated.
        assert (
            invite(api_client, data_fixture, user, workspace).status_code == HTTP_200_OK
        )
        assert (
            invite(api_client, data_fixture, user, workspace).status_code == HTTP_200_OK
        )
        assert invite(api_client, data_fixture, user, workspace).status_code == (
            HTTP_429_TOO_MANY_REQUESTS
        )


@pytest.mark.django_db
@override_settings(
    BASEROW_WORKSPACE_INVITATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=3600, number_of_calls=2),
    ),
)
def test_rate_limit_is_shared_between_the_workspaces_of_a_user(
    api_client, data_fixture
):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace(user=user)

    with freeze_time("2024-01-01 12:00:00"):
        assert invite(
            api_client, data_fixture, user, workspace_1, "1@test.nl"
        ).status_code == (HTTP_200_OK)
        assert invite(
            api_client, data_fixture, user, workspace_2, "2@test.nl"
        ).status_code == (HTTP_200_OK)
        assert invite(
            api_client, data_fixture, user, workspace_2, "3@test.nl"
        ).status_code == (HTTP_429_TOO_MANY_REQUESTS)


@pytest.mark.django_db
@override_settings(
    BASEROW_WORKSPACE_INVITATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=3600, number_of_calls=1),
    ),
)
def test_rate_limit_is_not_shared_between_users(api_client, data_fixture):
    user_1 = data_fixture.create_user(email="user1@test.nl")
    user_2 = data_fixture.create_user(email="user2@test.nl")
    workspace = data_fixture.create_workspace(users=[user_1, user_2])

    with freeze_time("2024-01-01 12:00:00"):
        assert invite(
            api_client, data_fixture, user_1, workspace, "1@test.nl"
        ).status_code == (HTTP_200_OK)
        assert invite(
            api_client, data_fixture, user_1, workspace, "2@test.nl"
        ).status_code == (HTTP_429_TOO_MANY_REQUESTS)
        assert invite(
            api_client, data_fixture, user_2, workspace, "3@test.nl"
        ).status_code == (HTTP_200_OK)


@pytest.mark.django_db
@override_settings(
    BASEROW_WORKSPACE_INVITATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=3600, number_of_calls=1),
    ),
)
def test_staff_users_are_not_rate_limited(api_client, data_fixture):
    user = data_fixture.create_user(is_staff=True)
    workspace = data_fixture.create_workspace(user=user)

    with freeze_time("2024-01-01 12:00:00"):
        for index in range(5):
            response = invite(
                api_client, data_fixture, user, workspace, f"test{index}@test.nl"
            )
            assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(
    BASEROW_WORKSPACE_INVITATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=60, number_of_calls=1),
    ),
)
def test_rate_limit_recovers_when_the_window_passes(api_client, data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with freeze_time("2024-01-01 12:00:00"):
        assert invite(
            api_client, data_fixture, user, workspace, "1@test.nl"
        ).status_code == (HTTP_200_OK)
        response = invite(api_client, data_fixture, user, workspace, "2@test.nl")
        assert response.status_code == HTTP_429_TOO_MANY_REQUESTS
        assert int(response["Retry-After"]) == 60

    with freeze_time("2024-01-01 12:01:01"):
        assert invite(
            api_client, data_fixture, user, workspace, "3@test.nl"
        ).status_code == (HTTP_200_OK)
