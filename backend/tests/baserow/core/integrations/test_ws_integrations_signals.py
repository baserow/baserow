from unittest.mock import patch

import pytest

from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.integrations.tasks import broadcast_to_workspace_integration_users


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.integrations.ws.signals.broadcast_to_permitted_users")
def test_integration_created(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration_type = integration_type_registry.get("local_baserow")

    integration = IntegrationService().create_integration(
        user, integration_type, application, name="Integration"
    )

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "integration_created"
    assert args[0][4]["integration"]["id"] == integration.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.integrations.ws.signals.broadcast_to_permitted_users")
def test_integration_updated(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    IntegrationService().update_integration(user, integration, name="Updated")

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "integration_updated"
    assert args[0][4]["integration"]["name"] == "Updated"


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.integrations.ws.signals.broadcast_to_permitted_users")
@patch("baserow.core.integrations.ws.signals.broadcast_to_workspace_integration_users")
def test_integration_updated_when_promoted(
    mock_workspace_broadcast, mock_broadcast, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    integration = data_fixture.create_local_baserow_integration(
        application=data_fixture.create_builder_application(workspace=workspace),
        user=user,
    )

    IntegrationService().update_integration(
        user, integration, application_id=shared_application.id
    )

    # Tells everyone who can see it from any application where it is now.
    mock_broadcast.delay.assert_not_called()
    mock_workspace_broadcast.delay.assert_called_once()
    args = mock_workspace_broadcast.delay.call_args
    assert args[0][0] == workspace.id
    assert args[0][1]["type"] == "integration_updated"
    assert args[0][1]["integration"]["application_id"] == shared_application.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.integrations.ws.signals.broadcast_to_permitted_users")
@patch("baserow.core.integrations.ws.signals.broadcast_to_workspace_integration_users")
def test_workspace_integration_events_go_to_whoever_can_see_them_from_an_application(
    mock_workspace_broadcast, mock_broadcast, data_fixture
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    shared_application = data_fixture.create_shared_application(workspace=workspace)
    integration_type = integration_type_registry.get("local_baserow")
    service = IntegrationService()

    integration = service.create_integration(
        user, integration_type, shared_application, name="Integration"
    )
    service.update_integration(user, integration, name="Updated")
    service.delete_integration(user, integration)

    mock_broadcast.delay.assert_not_called()
    calls = mock_workspace_broadcast.delay.call_args_list
    assert [call[0][0] for call in calls] == [workspace.id] * 3
    assert [call[0][1]["type"] for call in calls] == [
        "integration_created",
        "integration_updated",
        "integration_deleted",
    ]
    assert calls[2][0][1]["application_id"] == shared_application.id


@pytest.mark.django_db
@patch("baserow.ws.tasks.broadcast_to_users")
def test_workspace_integration_events_reach_every_member_without_roles(
    mock_broadcast_to_users, data_fixture
):
    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    data_fixture.create_builder_application(workspace=workspace)
    payload = {"type": "integration_updated"}

    broadcast_to_workspace_integration_users(workspace.id, payload, "socket")

    mock_broadcast_to_users.assert_called_once()
    args, kwargs = mock_broadcast_to_users.call_args
    assert set(args[0]) == {admin.id, member.id}
    assert args[1] == payload
    assert kwargs["ignore_web_socket_id"] == "socket"


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.integrations.ws.signals.broadcast_to_permitted_users")
def test_integration_deleted(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)
    integration_id = integration.id

    IntegrationService().delete_integration(user, integration)

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "integration_deleted"
    assert args[0][4]["integration_id"] == integration_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.integrations.ws.signals.broadcast_to_permitted_users")
def test_integration_updated_does_not_broadcast_secret(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_smtp_integration(
        user=user, password="supersecret"
    )

    IntegrationService().update_integration(user, integration, name="Updated")

    mock_broadcast.delay.assert_called_once()
    payload = mock_broadcast.delay.call_args[0][4]["integration"]
    assert "password" not in payload
    assert payload["has_password"] is True
