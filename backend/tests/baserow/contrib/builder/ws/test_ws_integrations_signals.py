from unittest.mock import patch

import pytest

from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.integrations.signals.broadcast_to_permitted_users")
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
@patch("baserow.contrib.builder.ws.integrations.signals.broadcast_to_permitted_users")
def test_integration_updated(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)

    IntegrationService().update_integration(user, integration, name="Updated")

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "integration_updated"
    assert args[0][4]["integration"]["name"] == "Updated"


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.builder.ws.integrations.signals.broadcast_to_permitted_users")
def test_integration_deleted(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    integration = data_fixture.create_local_baserow_integration(user=user)
    integration_id = integration.id

    IntegrationService().delete_integration(user, integration)

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "integration_deleted"
    assert args[0][4]["integration_id"] == integration_id
