from unittest.mock import patch

from django.db import connection, transaction
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.ws.views.rows.handler import ViewRealtimeRowsHandler


def _payloads_for_view(mock_broadcast_to_channel_group, slug):
    """The payloads broadcast to a public view's page group, in call order."""

    group_name = f"view-{slug}"
    return [
        call.args[1]
        for call in mock_broadcast_to_channel_group.delay.mock_calls
        if call.args and call.args[0] == group_name
    ]


def _setup_linked_tables_with_public_view(data_fixture, user, filter_value):
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific
    lookup_a = data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'primary'), '')"
    )

    public_view = data_fixture.create_grid_view(
        user, table=table_a, public=True, create_options=False
    )
    data_fixture.create_grid_view_field_option(public_view, lookup_a, hidden=False)
    data_fixture.create_view_filter(
        view=public_view, field=lookup_a, type="contains", value=filter_value
    )

    return table_a, table_b, link_a_b, primary_b, lookup_a, public_view


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_dependant_row_still_matching_filter_receives_rows_updated_in_public_view(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    (
        table_a,
        table_b,
        link_a_b,
        primary_b,
        lookup_a,
        public_view,
    ) = _setup_linked_tables_with_public_view(data_fixture, user, filter_value="keep")

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

    payloads = _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["type"] == "rows_updated"
    assert payload["table_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    assert [row["id"] for row in payload["rows"]] == [row_a1.id]
    assert payload["rows"][0][f"field_{lookup_a.id}"] == "keep me too"
    # No pre-cascade values are sent: they might belong to a row the view never
    # showed. The client resolves the before state from its own buffered copy.
    assert payload["rows_before_update"] == [{"id": row_a1.id}]
    # Fields without a grid view option are hidden, so only the visible field leaks.
    assert set(payload["rows"][0].keys()) == {"id", "order", f"field_{lookup_a.id}"}


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_dependant_row_leaving_filter_gets_no_realtime_event_in_public_view(
    mock_broadcast_to_channel_group, data_fixture
):
    # A cascade that pushes a row out of a filtered public view can't be
    # reconciled without its pre-cascade visibility: no delete is sent (a bare
    # delete would corrupt the filterless public client's row count), so the row
    # settles on the next refresh. See #5649.
    user = data_fixture.create_user()
    (
        table_a,
        table_b,
        link_a_b,
        primary_b,
        lookup_a,
        public_view,
    ) = _setup_linked_tables_with_public_view(data_fixture, user, filter_value="old")

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

    assert _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug) == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_only_still_matching_dependant_rows_are_broadcast_to_public_view(
    mock_broadcast_to_channel_group, data_fixture
):
    # When a single cascade updates several dependant rows, the public view only
    # receives the ones still matching its filters; a row pushed out is silently
    # left for the next refresh and its values never reach the view.
    user = data_fixture.create_user()
    (
        table_a,
        table_b,
        link_a_b,
        primary_b,
        lookup_a,
        public_view,
    ) = _setup_linked_tables_with_public_view(data_fixture, user, filter_value="keep")

    row_b1, row_b2 = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [{primary_b.db_column: "keep"}, {primary_b.db_column: "keep"}],
        )
        .created_rows
    )
    row_a1 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])
        .created_rows[0]
    )
    row_a2 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b2.id]}])
        .created_rows[0]
    )

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(
            user,
            table_b,
            [
                {"id": row_b1.id, primary_b.db_column: "keep still"},
                {"id": row_b2.id, primary_b.db_column: "dropped"},
            ],
        )

    payloads = _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug)
    assert len(payloads) == 1
    payload = payloads[0]
    assert payload["type"] == "rows_updated"
    # Only row_a1 still matches "keep"; row_a2 left the view and must be absent.
    assert [row["id"] for row in payload["rows"]] == [row_a1.id]
    assert payload["rows"][0][f"field_{lookup_a.id}"] == "keep still"
    assert row_a2.id not in [row["id"] for row in payload["rows"]]


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_dependant_rows_updates_are_not_broadcast_when_table_has_no_public_view(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific
    data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'primary'), '')"
    )

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "b1"}])
        .created_rows[0]
    )
    RowHandler().create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(
            user, table_b, [{"id": row_b1.id, primary_b.db_column: "renamed"}]
        )

    view_calls = [
        call
        for call in mock_broadcast_to_channel_group.delay.mock_calls
        if call.args and str(call.args[0]).startswith("view-")
    ]
    assert view_calls == []


def _count_broadcast_to_views_queries(data_fixture, user, n_public_views):
    table_a, table_b, link_a_b = data_fixture.create_two_linked_tables(user=user)
    primary_b = table_b.field_set.get(primary=True).specific
    lookup_a = data_fixture.create_formula_field(
        table=table_a, formula="join(lookup('link', 'primary'), '')"
    )
    for _ in range(n_public_views):
        view = data_fixture.create_grid_view(
            user, table=table_a, public=True, create_options=False
        )
        data_fixture.create_grid_view_field_option(view, lookup_a, hidden=False)
        data_fixture.create_view_filter(
            view=view, field=lookup_a, type="contains", value="keep"
        )

    row_b1 = (
        RowHandler()
        .create_rows(user, table_b, [{primary_b.db_column: "keep"}])
        .created_rows[0]
    )
    row_a1 = (
        RowHandler()
        .create_rows(user, table_a, [{link_a_b.db_column: [row_b1.id]}])
        .created_rows[0]
    )

    model = table_a.get_model()
    rows = list(model.objects.filter(id__in=[row_a1.id]).enhance_by_fields())
    serialized_rows = get_row_serializer_class(model, RowSerializer, is_response=True)(
        rows, many=True
    ).data

    with CaptureQueriesContext(connection) as captured:
        ViewRealtimeRowsHandler().broadcast_dependant_rows_updated_to_views(
            table_a, model, rows, serialized_rows, [lookup_a.id]
        )
    return len(captured.captured_queries)


@pytest.mark.django_db
def test_broadcast_to_views_is_one_query_without_views_and_flat_across_views(
    data_fixture,
):
    user = data_fixture.create_user()

    # No public/restricted view: a single lookup that finds none, then nothing.
    assert _count_broadcast_to_views_queries(data_fixture, user, 0) == 1

    # The per-row-batch work is fixed, so adding more views must not add queries.
    one_view = _count_broadcast_to_views_queries(data_fixture, user, 1)
    three_views = _count_broadcast_to_views_queries(data_fixture, user, 3)
    assert one_view == three_views
