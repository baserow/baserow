from unittest.mock import patch

from django.db import transaction

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


def _payloads_for_restricted_view(mock_broadcast_to_channel_group, view_id):
    """The payloads broadcast to a restricted view's page group, in call order."""

    group_name = f"restricted-view-{view_id}"
    return [
        call.args[1]
        for call in mock_broadcast_to_channel_group.delay.mock_calls
        if call.args and call.args[0] == group_name
    ]


def _setup_linked_tables_with_restricted_view(
    enterprise_data_fixture, user, filter_value
):
    table_a, table_b, link_a_b = enterprise_data_fixture.create_two_linked_tables(
        user=user
    )
    primary_b = table_b.field_set.get(primary=True).specific
    lookup_a = enterprise_data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'primary'), '')"
    )

    restricted_view = enterprise_data_fixture.create_grid_view(
        user,
        table=table_a,
        ownership_type=RestrictedViewOwnershipType.type,
        create_options=False,
    )
    enterprise_data_fixture.create_grid_view_field_option(
        restricted_view, lookup_a, hidden=False
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=lookup_a, type="contains", value=filter_value
    )

    return table_a, table_b, link_a_b, primary_b, lookup_a, restricted_view


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_dependant_row_still_matching_filter_receives_rows_updated_in_restricted_view(
    mock_broadcast_to_channel_group, enterprise_data_fixture
):
    user = enterprise_data_fixture.create_user()
    (
        table_a,
        table_b,
        link_a_b,
        primary_b,
        lookup_a,
        restricted_view,
    ) = _setup_linked_tables_with_restricted_view(
        enterprise_data_fixture, user, filter_value="keep"
    )

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "keep me"}])
        .created_rows[0]
    )
    row_a1 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])
        .created_rows[0]
    )

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(
            user, table_b, [{"id": row_b1.id, primary_b.db_column: "keep me too"}]
        )

    payloads = _payloads_for_restricted_view(
        mock_broadcast_to_channel_group, restricted_view.id
    )
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["type"] == "rows_updated"
    assert payload["table_id"] == table_a.id
    assert [row["id"] for row in payload["rows"]] == [row_a1.id]
    assert payload["rows"][0][f"field_{lookup_a.id}"] == "keep me too"
    assert payload["rows_before_update"] == [{"id": row_a1.id}]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_dependant_row_leaving_filter_gets_no_realtime_event_in_restricted_view(
    mock_broadcast_to_channel_group, enterprise_data_fixture
):
    # A cascade that pushes a row out of a filtered restricted view can't be
    # reconciled without its pre-cascade visibility, so no event is sent and the
    # row settles on the next refresh. See #5649.
    user = enterprise_data_fixture.create_user()
    (
        table_a,
        table_b,
        link_a_b,
        primary_b,
        lookup_a,
        restricted_view,
    ) = _setup_linked_tables_with_restricted_view(
        enterprise_data_fixture, user, filter_value="old"
    )

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "old"}])
        .created_rows[0]
    )
    RowHandler().create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(
            user, table_b, [{"id": row_b1.id, primary_b.db_column: "new"}]
        )

    assert (
        _payloads_for_restricted_view(
            mock_broadcast_to_channel_group, restricted_view.id
        )
        == []
    )
