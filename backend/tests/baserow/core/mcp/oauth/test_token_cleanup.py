from datetime import timedelta

from django.utils import timezone

import pytest
from freezegun import freeze_time
from oauth2_provider.models import AccessToken, RefreshToken

from baserow.core.mcp.oauth.tasks import clear_expired_mcp_oauth_tokens
from tests.baserow.core.mcp.oauth.helpers import obtain_tokens


@pytest.mark.django_db
def test_clear_expired_tokens_removes_stale_tokens(client, api_client, data_fixture):
    with freeze_time(timezone.now() - timedelta(days=40)):
        user, token = data_fixture.create_user_and_token()
        old = data_fixture.create_workspace(user=user)
        tokens = obtain_tokens(
            client, api_client, token, old, scope="mcp offline_access"
        )
        # Rotation revokes the first refresh token.
        response = client.post(
            "/oauth/token/",
            {
                "grant_type": "refresh_token",
                "refresh_token": tokens["refresh_token"],
                "client_id": tokens["client_id"],
            },
        )
        assert response.status_code == 200
    current_token = data_fixture.generate_token(user)
    current = data_fixture.create_workspace(user=user)
    fresh = obtain_tokens(
        client, api_client, current_token, current, scope="mcp offline_access"
    )
    assert RefreshToken.objects.filter(user=user, revoked__isnull=False).exists()

    clear_expired_mcp_oauth_tokens()

    assert list(RefreshToken.objects.filter(user=user)) == [
        RefreshToken.objects.get(application__client_id=fresh["client_id"])
    ]
    assert list(AccessToken.objects.filter(user=user)) == [
        AccessToken.objects.get(application__client_id=fresh["client_id"])
    ]
