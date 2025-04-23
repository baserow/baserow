import string

import pytest

from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.mcp.exceptions import (
    MaximumUniqueEndpointTriesError,
    MCPEndpointDoesNotBelongToUser,
    MCPEndpointDoesNotExist,
)
from baserow.core.mcp.handler import MCPEndpointHandler
from baserow.core.mcp.models import MCPEndpoint


@pytest.mark.django_db
def test_get_by_key(data_fixture):
    user = data_fixture.create_user()
    data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)
    data_fixture.create_mcp_endpoint(user=user, workspace=workspace_2)

    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotExist):
        handler.get_by_key(key="abc")

    endpoint_tmp = handler.get_by_key(key=endpoint.key)
    assert endpoint_tmp.id == endpoint.id
    assert endpoint.workspace_id == workspace_1.id
    assert isinstance(endpoint_tmp, MCPEndpoint)


@pytest.mark.django_db
def test_get_endpoint(data_fixture):
    user = data_fixture.create_user()
    user_2 = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)
    endpoint_2 = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_2)

    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotExist):
        handler.get_endpoint(user=user, endpoint_id=99999)

    with pytest.raises(MCPEndpointDoesNotExist):
        handler.get_endpoint(user=user_2, endpoint_id=endpoint.id)

    with pytest.raises(UserNotInWorkspace):
        handler.get_endpoint(user=user, endpoint_id=endpoint_2.id)

    endpoint_tmp = handler.get_endpoint(user, endpoint.id)
    assert endpoint_tmp.id == endpoint.id
    assert endpoint.workspace_id == workspace_1.id
    assert isinstance(endpoint_tmp, MCPEndpoint)

    # If the error is raised we know for sure that the query has resolved.
    with pytest.raises(AttributeError):
        handler.get_endpoint(
            user=user,
            endpoint_id=endpoint.id,
            base_queryset=MCPEndpoint.objects.prefetch_related("UNKNOWN"),
        )


@pytest.mark.django_db
def test_generate_unique_key(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    handler = MCPEndpointHandler()

    assert len(handler.generate_unique_key(32)) == 32
    assert len(handler.generate_unique_key(10)) == 10
    assert handler.generate_unique_key(32) != handler.generate_unique_key(32)

    key = handler.generate_unique_key(32)
    assert not MCPEndpoint.objects.filter(key=key).exists()

    for char in string.ascii_letters + string.digits:
        data_fixture.create_mcp_endpoint(key=char, user=user, workspace=workspace)

    with pytest.raises(MaximumUniqueEndpointTriesError):
        handler.generate_unique_key(1, 3)


@pytest.mark.django_db
def test_create_endpoint(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    workspace_2 = data_fixture.create_workspace()

    handler = MCPEndpointHandler()

    with pytest.raises(UserNotInWorkspace):
        handler.create_endpoint(user=user, workspace=workspace_2, name="Test")

    endpoint = handler.create_endpoint(user=user, workspace=workspace_1, name="Test")
    assert endpoint.user_id == user.id
    assert endpoint.workspace_id == workspace_1.id
    assert endpoint.name == "Test"
    assert len(endpoint.key) == 32

    assert MCPEndpoint.objects.all().count() == 1


@pytest.mark.django_db
def test_update_endpoint(data_fixture):
    user = data_fixture.create_user()
    endpoint_1 = data_fixture.create_mcp_endpoint(user=user)
    endpoint_2 = data_fixture.create_mcp_endpoint()

    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotBelongToUser):
        handler.update_endpoint(user=user, endpoint=endpoint_2, name="New")

    endpoint_1 = handler.update_endpoint(user=user, endpoint=endpoint_1, name="New")
    assert endpoint_1.name == "New"

    endpoint_1 = MCPEndpoint.objects.get(pk=endpoint_1.id)
    assert endpoint_1.name == "New"


@pytest.mark.django_db
def test_delete_endpoint(data_fixture):
    user = data_fixture.create_user()
    endpoint_1 = data_fixture.create_mcp_endpoint(user=user)
    endpoint_2 = data_fixture.create_mcp_endpoint()

    handler = MCPEndpointHandler()

    with pytest.raises(MCPEndpointDoesNotBelongToUser):
        handler.delete_endpoint(user=user, endpoint=endpoint_2)

    handler.delete_endpoint(user=user, endpoint=endpoint_1)

    assert MCPEndpoint.objects.all().count() == 1
    assert MCPEndpoint.objects.all().first().id == endpoint_2.id
