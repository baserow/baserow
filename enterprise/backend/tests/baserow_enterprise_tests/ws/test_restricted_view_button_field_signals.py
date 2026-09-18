from unittest.mock import patch

import pytest

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.views.models import GridViewFieldOptions
from baserow.contrib.database.workflow_actions.models import (
    LocalBaserowCreateRowWorkflowAction,
)
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


def _restricted_view_messages(mock_broadcast_to_channel_group, view_id):
    """The button messages broadcast to a restricted view, in order."""

    group_name = f"restricted-view-{view_id}"
    return [
        call.args[1]
        for call in mock_broadcast_to_channel_group.delay.mock_calls
        if call.args
        and call.args[0] == group_name
        and call.args[1].get("type") == "button_fields_updated"
    ]


def _setup(enterprise_data_fixture):
    """A button in a restricted view, writing to a field in another table."""

    user = enterprise_data_fixture.create_user()
    button_table = enterprise_data_fixture.create_database_table(user=user)
    target = enterprise_data_fixture.create_database_table(
        user=user, database=button_table.database
    )
    mapped = enterprise_data_fixture.create_text_field(table=target, name="Mapped")
    button_field = enterprise_data_fixture.create_button_field(
        table=button_table, label="Go"
    )
    action = enterprise_data_fixture.create_database_workflow_action(
        LocalBaserowCreateRowWorkflowAction, field=button_field
    )
    service = action.service.specific
    service.table = target
    service.save()
    service.field_mappings.create(field=mapped, value="'x'", enabled=True)
    restricted_view = enterprise_data_fixture.create_grid_view(
        user,
        table=button_table,
        ownership_type=RestrictedViewOwnershipType.type,
        public=False,
    )
    return user, mapped, button_field, restricted_view


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_trashed_target_reaches_a_restricted_view(
    mock_broadcast_to_channel_group, enterprise_data_fixture
):
    """Someone who reaches the table only through a restricted view is
    subscribed to that view's page, not the table's."""

    user, mapped, button_field, restricted_view = _setup(enterprise_data_fixture)
    mock_broadcast_to_channel_group.reset_mock()

    FieldHandler().delete_field(user, mapped)

    [message] = _restricted_view_messages(
        mock_broadcast_to_channel_group, restricted_view.id
    )
    assert [field["id"] for field in message["fields"]] == [button_field.id]
    assert message["fields"][0]["requires_reconfiguration"] is True


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_button_hidden_in_a_restricted_view_is_left_out(
    mock_broadcast_to_channel_group, enterprise_data_fixture
):
    user, mapped, button_field, restricted_view = _setup(enterprise_data_fixture)
    GridViewFieldOptions.objects.update_or_create(
        grid_view=restricted_view, field=button_field, defaults={"hidden": True}
    )
    mock_broadcast_to_channel_group.reset_mock()

    FieldHandler().delete_field(user, mapped)

    assert (
        _restricted_view_messages(mock_broadcast_to_channel_group, restricted_view.id)
        == []
    )
