from unittest.mock import patch

import pytest

from baserow.core.trash.handler import TrashHandler
from baserow.core.user_sources.registries import user_source_type_registry
from baserow.core.user_sources.service import UserSourceService
from baserow.core.user_sources.trash_types import UserSourceTrashableItemType


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.user_sources.ws.signals.broadcast_to_permitted_users")
def test_user_source_created(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    application = data_fixture.create_builder_application(user=user)
    integration = data_fixture.create_local_baserow_integration(
        application=application, user=user
    )
    user_source_type = list(user_source_type_registry.get_all())[0]

    user_source = UserSourceService().create_user_source(
        user,
        user_source_type,
        application,
        name="User source",
        integration_id=integration.id,
    )

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "user_source_created"
    assert args[0][4]["user_source"]["id"] == user_source.id


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.user_sources.ws.signals.broadcast_to_permitted_users")
def test_user_source_updated(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)

    UserSourceService().update_user_source(user, user_source, name="Updated")

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "user_source_updated"
    assert args[0][4]["user_source"]["name"] == "Updated"


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.user_sources.ws.signals.broadcast_to_permitted_users")
def test_user_source_deleted(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)
    user_source_id = user_source.id

    UserSourceService().delete_user_source(user, user_source)

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "user_source_deleted"
    assert args[0][4]["user_source_id"] == user_source_id


@pytest.mark.django_db(transaction=True)
@patch("baserow.core.user_sources.ws.signals.broadcast_to_permitted_users")
def test_user_source_restored(mock_broadcast, data_fixture):
    user = data_fixture.create_user()
    user_source = data_fixture.create_user_source_with_first_type(user=user)
    user_source_id = user_source.id

    UserSourceService().delete_user_source(user, user_source)
    mock_broadcast.reset_mock()

    TrashHandler.restore_item(
        user, UserSourceTrashableItemType.type, user_source_id
    )

    mock_broadcast.delay.assert_called_once()
    args = mock_broadcast.delay.call_args
    assert args[0][4]["type"] == "user_source_created"
    assert args[0][4]["user_source"]["id"] == user_source_id
    # The frontend realtime handler resolves the application from this field; if it's
    # missing the restored user source is silently dropped (getApplicationContext
    # bails), so it must be present in the broadcast payload.
    assert "application_id" in args[0][4]["user_source"]
