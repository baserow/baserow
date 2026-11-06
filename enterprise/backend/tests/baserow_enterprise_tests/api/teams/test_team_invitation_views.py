from django.shortcuts import reverse
from django.test.utils import override_settings

import pytest
from freezegun import freeze_time
from rest_framework.status import (
    HTTP_200_OK,
    HTTP_204_NO_CONTENT,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.core.models import WorkspaceInvitation
from baserow.test_utils.helpers import AnyInt
from baserow.throttling.types import RateLimit
from baserow_enterprise.audit_log.models import AuditLogEntry
from baserow_enterprise.role.constants import NO_ROLE_LOW_PRIORITY_ROLE_UID
from baserow_enterprise.teams.actions import (
    CreateTeamInvitationActionType,
    DeleteTeamInvitationActionType,
)
from baserow_enterprise.teams.handler import TeamHandler
from baserow_enterprise.teams.models import WorkspaceTeamInvitation

HTTP_429_TOO_MANY_REQUESTS = 429

CAPTCHA_SETTINGS = {
    "BASEROW_CAPTCHA_PROVIDER": "cloudflare_turnstile",
    "BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY": "test-site-key",
    "BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY": "test-secret-key",
}


@pytest.fixture(autouse=True)
def enable_enterprise_and_roles_for_all_tests_here(enable_enterprise, synced_roles):
    pass


def setup_team(data_fixture, enterprise_data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)
    team = enterprise_data_fixture.create_team(name="Sales", workspace=workspace)
    return user, token, workspace, team


def list_url(team):
    return reverse("api:enterprise:teams:invitation-list", kwargs={"team_id": team.id})


def detail_url(team, team_invitation):
    return reverse(
        "api:enterprise:teams:invitation-detail",
        kwargs={"team_id": team.id, "team_invitation_id": team_invitation.id},
    )


@pytest.mark.django_db
def test_create_team_invitation(api_client, data_fixture, enterprise_data_fixture):
    user, token, workspace, team = setup_team(data_fixture, enterprise_data_fixture)

    response = api_client.post(
        list_url(team),
        {"email": "Foo@Bar.com"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert response_json == {
        "id": AnyInt(),
        "invitation_id": AnyInt(),
        "email": "foo@bar.com",
        "team_id": team.id,
        "created_on": response_json["created_on"],
    }
    invitation = WorkspaceInvitation.objects.get(id=response_json["invitation_id"])
    assert invitation.permissions == NO_ROLE_LOW_PRIORITY_ROLE_UID
    assert WorkspaceTeamInvitation.objects.get(id=response_json["id"]).team == team

    entry = AuditLogEntry.objects.get(action_type=CreateTeamInvitationActionType.type)
    assert entry.params["email"] == "foo@bar.com"
    assert entry.params["team_id"] == team.id


@pytest.mark.django_db
def test_create_team_invitation_errors(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token, workspace, team = setup_team(data_fixture, enterprise_data_fixture)
    member = data_fixture.create_user(email="member@bar.com")
    data_fixture.create_user_workspace(
        workspace=workspace, user=member, permissions="VIEWER"
    )
    builder, builder_token = data_fixture.create_user_and_token(email="builder@bar.com")
    data_fixture.create_user_workspace(
        workspace=workspace, user=builder, permissions="BUILDER"
    )
    _, outsider_token = data_fixture.create_user_and_token(email="outsider@bar.com")
    body = {"email": "foo@bar.com"}

    response = api_client.post(
        list_url(team),
        {"email": "member@bar.com"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_GROUP_USER_ALREADY_EXISTS"

    response = api_client.post(
        list_url(team),
        {"email": "not an email"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_REQUEST_BODY_VALIDATION"

    response = api_client.post(
        reverse("api:enterprise:teams:invitation-list", kwargs={"team_id": 999999}),
        body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEAM_DOES_NOT_EXIST"

    # A member who can't add people to the team.
    response = api_client.post(
        list_url(team), body, format="json", HTTP_AUTHORIZATION=f"JWT {builder_token}"
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"

    # A user outside the workspace.
    response = api_client.post(
        list_url(team), body, format="json", HTTP_AUTHORIZATION=f"JWT {outsider_token}"
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_USER_NOT_IN_GROUP"

    assert WorkspaceTeamInvitation.objects.count() == 0
    assert WorkspaceInvitation.objects.count() == 0


@pytest.mark.django_db
@override_settings(BASEROW_ENABLE_CAPTCHA="workspace_invitation", **CAPTCHA_SETTINGS)
def test_create_team_invitation_requires_captcha_when_enabled(
    api_client, data_fixture, enterprise_data_fixture
):
    user, token, workspace, team = setup_team(data_fixture, enterprise_data_fixture)

    response = api_client.post(
        list_url(team),
        {"email": "foo@bar.com"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CAPTCHA_VERIFICATION_FAILED"
    assert WorkspaceTeamInvitation.objects.count() == 0


@pytest.mark.django_db
@override_settings(
    BASEROW_WORKSPACE_INVITATION_RATE_LIMITS=(
        RateLimit(period_in_seconds=3600, number_of_calls=2),
    ),
)
def test_create_team_invitation_is_rate_limited(
    api_client, data_fixture, enterprise_data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    member = data_fixture.create_user(email="member@bar.com")
    data_fixture.create_user_workspace(workspace=workspace, user=member)
    team = enterprise_data_fixture.create_team(workspace=workspace)

    def invite(email):
        # The token must be generated at the frozen time of the request,
        # otherwise it isn't valid yet.
        token = data_fixture.generate_token(user)
        return api_client.post(
            list_url(team),
            {"email": email},
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )

    with freeze_time("2024-01-01 12:00:00"):
        assert invite("1@bar.com").status_code == HTTP_200_OK
        # A failing invitation doesn't use up the limit.
        assert invite("member@bar.com").status_code == HTTP_400_BAD_REQUEST
        assert invite("2@bar.com").status_code == HTTP_200_OK
        response = invite("3@bar.com")

    assert response.status_code == HTTP_429_TOO_MANY_REQUESTS


@pytest.mark.django_db
def test_list_team_invitations(api_client, data_fixture, enterprise_data_fixture):
    user, token, workspace, team = setup_team(data_fixture, enterprise_data_fixture)
    other_team = enterprise_data_fixture.create_team(workspace=workspace)
    builder, builder_token = data_fixture.create_user_and_token()
    data_fixture.create_user_workspace(
        workspace=workspace, user=builder, permissions="BUILDER"
    )
    handler = TeamHandler()
    first = handler.create_team_invitation(user, team, "foo@bar.com")
    handler.create_team_invitation(user, other_team, "other@bar.com")

    response = api_client.get(list_url(team), HTTP_AUTHORIZATION=f"JWT {token}")

    assert response.status_code == HTTP_200_OK
    assert response.json() == [
        {
            "id": first.id,
            "invitation_id": first.invitation_id,
            "email": "foo@bar.com",
            "team_id": team.id,
            "created_on": response.json()[0]["created_on"],
        }
    ]

    # The invitations hold email addresses, which only who can list the
    # invitations of the workspace may see.
    response = api_client.get(list_url(team), HTTP_AUTHORIZATION=f"JWT {builder_token}")
    assert response.status_code == HTTP_401_UNAUTHORIZED
    assert response.json()["error"] == "PERMISSION_DENIED"


@pytest.mark.django_db
def test_delete_team_invitation(api_client, data_fixture, enterprise_data_fixture):
    user, token, workspace, team = setup_team(data_fixture, enterprise_data_fixture)
    other_team = enterprise_data_fixture.create_team(workspace=workspace)
    builder, builder_token = data_fixture.create_user_and_token()
    data_fixture.create_user_workspace(
        workspace=workspace, user=builder, permissions="BUILDER"
    )
    handler = TeamHandler()
    team_invitation = handler.create_team_invitation(user, team, "foo@bar.com")
    other_invitation = handler.create_team_invitation(user, other_team, "foo@bar.com")

    response = api_client.delete(
        detail_url(team, team_invitation),
        HTTP_AUTHORIZATION=f"JWT {builder_token}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    # The invitation belongs to another team than the one in the URL.
    response = api_client.delete(
        detail_url(team, other_invitation), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response.json()["error"] == "ERROR_TEAM_INVITATION_DOES_NOT_EXIST"

    response = api_client.delete(
        detail_url(team, team_invitation), HTTP_AUTHORIZATION=f"JWT {token}"
    )
    assert response.status_code == HTTP_204_NO_CONTENT

    # Only the team is revoked, the workspace invitation stays pending.
    assert list(WorkspaceTeamInvitation.objects.all()) == [other_invitation]
    assert WorkspaceInvitation.objects.filter(id=team_invitation.invitation_id).exists()
    entry = AuditLogEntry.objects.get(action_type=DeleteTeamInvitationActionType.type)
    assert entry.params["email"] == "foo@bar.com"
