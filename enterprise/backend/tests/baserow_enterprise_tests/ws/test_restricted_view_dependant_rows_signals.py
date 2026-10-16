from unittest.mock import ANY, patch

from django.db import transaction
from django.test.utils import override_settings

import pytest

from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
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
def test_dependant_rows_leaving_or_entering_restricted_view_are_deleted_or_created(
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
    hidden_a = enterprise_data_fixture.create_text_field(table=table_a)
    enterprise_data_fixture.create_grid_view_field_option(
        restricted_view, hidden_a, hidden=True
    )

    row_b1, row_b2 = (
        RowHandler()
        .create_rows(
            user, table_b, [{primary_b.db_column: name} for name in ("keep", "")]
        )
        .created_rows
    )
    row_a1, row_a2 = (
        RowHandler()
        .create_rows(
            user, table_a, [{link_a_b.db_column: [row.id]} for row in (row_b1, row_b2)]
        )
        .created_rows
    )

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(
            user,
            table_b,
            [
                {"id": row_b1.id, primary_b.db_column: "gone"},
                {"id": row_b2.id, primary_b.db_column: "keep now"},
            ],
        )

    payloads = _payloads_for_restricted_view(
        mock_broadcast_to_channel_group, restricted_view.id
    )
    assert [payload["type"] for payload in payloads] == [
        "rows_deleted",
        "rows_created",
        "rows_updated",
    ]
    deleted, created, _ = payloads
    lookup = f"field_{lookup_a.id}"
    primary_a = f"field_{table_a.get_primary_field().id}"
    assert deleted["table_id"] == table_a.id
    assert deleted["row_ids"] == [row_a1.id]
    # The before values the view showed: no hidden field, and no renamed link.
    assert deleted["rows"] == [
        {"id": row_a1.id, "order": ANY, primary_a: None, lookup: "keep"}
    ]
    assert created["before_row_id"] is None
    assert [(row["id"], row[lookup]) for row in created["rows"]] == [
        (row_a2.id, "keep now")
    ]
    assert f"field_{hidden_a.id}" not in created["rows"][0]


@pytest.mark.parametrize(
    "cascades", [[[0, 1]], [[0], [1]]], ids=["one_cascade", "two_cascades"]
)
@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_cascades_over_the_limit_refresh_the_restricted_views(
    mock_broadcast_to_channel_group, enterprise_data_fixture, cascades
):
    user = enterprise_data_fixture.create_user()
    (
        table_a,
        table_b,
        link_a_b,
        primary_b,
        lookup_a,
        filtered_view,
    ) = _setup_linked_tables_with_restricted_view(
        enterprise_data_fixture, user, filter_value="b"
    )
    unfiltered_view = enterprise_data_fixture.create_grid_view(
        user, table=table_a, ownership_type=RestrictedViewOwnershipType.type
    )
    collaborative_view = enterprise_data_fixture.create_grid_view(user, table=table_a)
    rows_b = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "b"}] * 2)
        .created_rows
    )
    RowHandler().create_rows(
        user, table_a, [{link_a_b.db_column: [row_b.id]} for row_b in rows_b]
    )

    mock_broadcast_to_channel_group.reset_mock()
    with override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=1):
        with transaction.atomic():
            for indexes in cascades:
                RowHandler().update_rows(
                    user,
                    table_b,
                    [{"id": rows_b[i].id, primary_b.db_column: "c"} for i in indexes],
                )

    for view in (filtered_view, unfiltered_view):
        assert _payloads_for_restricted_view(
            mock_broadcast_to_channel_group, view.id
        ) == [{"type": "force_view_rows_refresh", "view_id": view.id}]
    assert (
        _payloads_for_restricted_view(
            mock_broadcast_to_channel_group, collaborative_view.id
        )
        == []
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_creating_a_filter_refreshes_the_rows_of_the_restricted_view(
    mock_broadcast_to_channel_group, enterprise_data_fixture
):
    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    field = enterprise_data_fixture.create_text_field(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        user, table=table, ownership_type=RestrictedViewOwnershipType.type
    )

    mock_broadcast_to_channel_group.reset_mock()
    ViewHandler().create_filter(user, restricted_view, field, "equal", "a")

    assert _payloads_for_restricted_view(
        mock_broadcast_to_channel_group, restricted_view.id
    ) == [{"type": "force_view_rows_refresh", "view_id": restricted_view.id}]
