from django.shortcuts import reverse
from django.test import override_settings

import pytest
import responses
from rest_framework.status import HTTP_200_OK, HTTP_400_BAD_REQUEST

from baserow.core.models import WorkspaceInvitation

CAPTCHA_SETTINGS = {
    "BASEROW_CAPTCHA_PROVIDER": "cloudflare_turnstile",
    "BASEROW_CLOUDFLARE_TURNSTILE_SITE_KEY": "test-site-key",
    "BASEROW_CLOUDFLARE_TURNSTILE_SECRET_KEY": "test-secret-key",
}


def invite(api_client, token, workspace, captcha_token=None):
    body = {
        "email": "test@test.nl",
        "permissions": "ADMIN",
        "base_url": "http://localhost:3000/invite",
    }

    if captcha_token is not None:
        body["captcha_token"] = captcha_token

    return api_client.post(
        reverse(
            "api:workspaces:invitations:list", kwargs={"workspace_id": workspace.id}
        ),
        body,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )


@pytest.mark.django_db
def test_invitation_captcha_not_required_by_default(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = invite(api_client, token, workspace)

    assert response.status_code == HTTP_200_OK
    assert WorkspaceInvitation.objects.count() == 1


@pytest.mark.django_db
@override_settings(BASEROW_ENABLE_CAPTCHA="workspace_invitation", **CAPTCHA_SETTINGS)
def test_invitation_captcha_required_when_enabled(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = invite(api_client, token, workspace)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CAPTCHA_VERIFICATION_FAILED"
    assert WorkspaceInvitation.objects.count() == 0


@pytest.mark.django_db
@responses.activate
@override_settings(BASEROW_ENABLE_CAPTCHA="workspace_invitation", **CAPTCHA_SETTINGS)
def test_invitation_captcha_valid_token(api_client, data_fixture):
    from baserow.core.captcha.provider_types import TURNSTILE_VERIFY_URL

    responses.add(
        responses.POST, TURNSTILE_VERIFY_URL, json={"success": True}, status=200
    )

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = invite(api_client, token, workspace, captcha_token="valid-token")

    assert response.status_code == HTTP_200_OK
    assert WorkspaceInvitation.objects.count() == 1
    assert len(responses.calls) == 1


@pytest.mark.django_db
@responses.activate
@override_settings(BASEROW_ENABLE_CAPTCHA="workspace_invitation", **CAPTCHA_SETTINGS)
def test_invitation_captcha_invalid_token(api_client, data_fixture):
    from baserow.core.captcha.provider_types import TURNSTILE_VERIFY_URL

    responses.add(
        responses.POST,
        TURNSTILE_VERIFY_URL,
        json={"success": False, "error-codes": ["invalid-input-response"]},
        status=200,
    )

    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = invite(api_client, token, workspace, captcha_token="invalid-token")

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CAPTCHA_VERIFICATION_FAILED"
    assert WorkspaceInvitation.objects.count() == 0


@pytest.mark.django_db
@override_settings(BASEROW_ENABLE_CAPTCHA="signup", **CAPTCHA_SETTINGS)
def test_invitation_captcha_not_required_for_another_context(api_client, data_fixture):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = invite(api_client, token, workspace)

    assert response.status_code == HTTP_200_OK


@pytest.mark.django_db
@override_settings(BASEROW_ENABLE_CAPTCHA="all", **CAPTCHA_SETTINGS)
def test_invitation_captcha_required_when_all_contexts_are_enabled(
    api_client, data_fixture
):
    user, token = data_fixture.create_user_and_token()
    workspace = data_fixture.create_workspace(user=user)

    response = invite(api_client, token, workspace)

    assert response.status_code == HTTP_400_BAD_REQUEST
    assert response.json()["error"] == "ERROR_CAPTCHA_VERIFICATION_FAILED"


@pytest.mark.django_db
@override_settings(BASEROW_ENABLE_CAPTCHA="workspace_invitation", **CAPTCHA_SETTINGS)
def test_workspace_invitation_captcha_context_is_exposed_in_the_settings(
    api_client, data_fixture
):
    response = api_client.get(reverse("api:settings:get"))

    captcha = response.json()["captcha"]
    assert captcha["enabled"] is True
    assert captcha["enabled_contexts"] == ["workspace_invitation"]
