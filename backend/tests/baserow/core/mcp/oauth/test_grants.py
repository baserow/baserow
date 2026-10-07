import pytest
from asgiref.sync import async_to_sync

from baserow.core.mcp.auth import resolve_bearer
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint

CLIENT_ID = "https://claude.ai/oauth/client.json"


@pytest.mark.django_db
def test_grant_has_no_key(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    endpoint = MCPEndpointHandler().grant_oauth_client(
        user, workspace, CLIENT_ID, "Claude", ["list_tables"]
    )

    endpoint.refresh_from_db()
    assert endpoint.key is None
    assert endpoint.oauth_client_id == CLIENT_ID


@pytest.mark.django_db
def test_second_consent_reuses_the_grant(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    handler = MCPEndpointHandler()

    first = handler.grant_oauth_client(
        user, workspace, CLIENT_ID, "Claude", ["list_tables"]
    )
    second = handler.grant_oauth_client(
        user, workspace, CLIENT_ID, "Claude", ["list_tables", "create_rows"]
    )

    assert first.id == second.id
    assert MCPEndpoint.objects.filter(oauth_client_id=CLIENT_ID).count() == 1
    second.refresh_from_db()
    assert second.allowed_tools == ["list_tables", "create_rows"]


@pytest.mark.django_db
def test_grant_constraint_blocks_duplicates(data_fixture):
    from django.db import IntegrityError, transaction

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    MCPEndpoint.objects.create(
        user=user, workspace=workspace, name="a", oauth_client_id=CLIENT_ID
    )
    with pytest.raises(IntegrityError), transaction.atomic():
        MCPEndpoint.objects.create(
            user=user, workspace=workspace, name="b", oauth_client_id=CLIENT_ID
        )


@pytest.mark.django_db
def test_legacy_endpoints_still_get_a_key(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    endpoint = MCPEndpointHandler().create_endpoint(user, workspace, "Mine")

    assert endpoint.key and len(endpoint.key) == 32
    endpoint_found, error = async_to_sync(resolve_bearer)(endpoint.key)
    assert endpoint_found.id == endpoint.id and error is None
