from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.contrib.database.views.handler import ViewHandler


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_copy_view_configuration_broadcasts_once(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user(web_socket_id="web-socket-id")
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)
    data_fixture.create_view_filter(
        view=source_view, field=field, type="equal", value="a"
    )
    data_fixture.create_view_sort(view=source_view, field=field)
    data_fixture.create_view_filter(
        view=dest_view, field=field, type="equal", value="old"
    )

    ViewHandler().copy_view_configuration(
        user, source_view, dest_view, ["filters", "sorts"]
    )

    # Even though multiple filters and sorts were deleted and created, only a
    # single event is broadcast, and the requester is excluded.
    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][0] == f"table-{table.id}"
    assert args[0][1]["type"] == "view_configuration_changed"
    assert args[0][1]["view_id"] == dest_view.id
    assert args[0][1]["view"]["id"] == dest_view.id
    assert len(args[0][1]["view"]["filters"]) == 1
    assert args[0][1]["view"]["filters"][0]["value"] == "a"
    assert len(args[0][1]["view"]["sortings"]) == 1
    assert args[0][1]["categories"] == ["filters", "sorts"]
    assert args[0][2] == "web-socket-id"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_copy_view_configuration_field_options_broadcast(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table)
    source_view = data_fixture.create_grid_view(table=table)
    dest_view = data_fixture.create_grid_view(table=table)

    with transaction.atomic():
        ViewHandler().copy_view_configuration(
            user, source_view, dest_view, ["field_visibility", "field_order"]
        )

    # The granular field options signal is suppressed, the single
    # `view_configuration_changed` event covers the change.
    mock_broadcast_to_channel_group.delay.assert_called_once()
    args = mock_broadcast_to_channel_group.delay.call_args
    assert args[0][1]["type"] == "view_configuration_changed"
    assert args[0][1]["categories"] == ["field_visibility", "field_order"]
