import threading
import time
import uuid
from dataclasses import dataclass
from functools import partial
from typing import Any, Dict, Iterable, List, Optional, Tuple
from unittest.mock import ANY, patch

from django.contrib.auth.models import AbstractUser
from django.db import connection, transaction
from django.test import override_settings
from django.test.utils import CaptureQueriesContext

import pytest

from baserow.api.sessions import set_client_undo_redo_action_group_id
from baserow.contrib.database.action.scopes import TableActionScopeType
from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.api.rows.serializers import (
    RowSerializer,
    get_row_serializer_class,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.rows.actions import UpdateRowsActionType
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.models import GridView
from baserow.contrib.database.ws.views.rows.handler import ViewRealtimeRowsHandler
from baserow.core.action.handler import ActionHandler
from baserow.test_utils.fixtures import Fixtures


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
def test_dependant_rows_leaving_or_entering_public_view_are_deleted_or_created(
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

    row_b1, row_b2, row_b3 = (
        RowHandler()
        .create_rows(
            user,
            table_b,
            [{primary_b.db_column: value} for value in ("keep", "keep", "hidden")],
        )
        .created_rows
    )
    row_a1, row_a2, row_a3 = (
        RowHandler()
        .create_rows(
            user,
            table_a,
            [{link_a_b.db_column: [row.id]} for row in (row_b1, row_b2, row_b3)],
        )
        .created_rows
    )

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(
            user,
            table_b,
            [
                {"id": row_b1.id, primary_b.db_column: "keep still"},
                {"id": row_b2.id, primary_b.db_column: "dropped"},
                {"id": row_b3.id, primary_b.db_column: "keep now"},
            ],
        )

    payloads = _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug)
    assert [payload["type"] for payload in payloads] == [
        "rows_deleted",
        "rows_created",
        "rows_updated",
    ]
    deleted, created, updated = payloads
    assert deleted["table_id"] == PUBLIC_PLACEHOLDER_ENTITY_ID
    assert deleted["row_ids"] == [row_a2.id]
    # The before values the view showed, restricted to its visible fields.
    lookup = f"field_{lookup_a.id}"
    assert deleted["rows"] == [{"id": row_a2.id, "order": ANY, lookup: "keep"}]
    assert created["before_row_id"] is None
    assert created["rows"] == [{"id": row_a3.id, "order": ANY, lookup: "keep now"}]
    assert [row["id"] for row in updated["rows"]] == [row_a1.id, row_a3.id]


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


@dataclass
class LinkedTables:
    """Table A linking table B, with a lookup of B's names and a status field."""

    data_fixture: Fixtures
    user: AbstractUser
    table_a: Table
    table_b: Table
    link: Field
    name_b: Field
    lookup: Field
    status: Field

    def create_rows(
        self, names_b: List[str], values_a: Optional[Dict[str, Any]] = None
    ) -> Tuple[List[GeneratedTableModel], List[GeneratedTableModel]]:
        """Creates a row in B per name, each linked from a new row of A."""

        rows_b = RowHandler().create_rows(
            self.user, self.table_b, [{self.name_b.db_column: n} for n in names_b]
        )
        rows_a = RowHandler().create_rows(
            self.user,
            self.table_a,
            [
                {self.link.db_column: [row.id], **(values_a or {})}
                for row in rows_b.created_rows
            ],
        )
        return rows_b.created_rows, rows_a.created_rows

    def rename(self, row_b: GeneratedTableModel, name: str) -> None:
        RowHandler().update_rows(
            self.user, self.table_b, [{"id": row_b.id, self.name_b.db_column: name}]
        )

    def create_public_view(
        self,
        filters: Iterable[Tuple[Field, str, str]],
        shown_fields: Iterable[Field] = (),
    ) -> GridView:
        return _create_public_view(
            self.data_fixture, self.user, self.table_a, filters, shown_fields
        )


def _create_linked_tables(data_fixture: Fixtures, user: AbstractUser) -> LinkedTables:
    table_a, table_b, link = data_fixture.create_two_linked_tables(user=user)
    return LinkedTables(
        data_fixture=data_fixture,
        user=user,
        table_a=table_a,
        table_b=table_b,
        link=link,
        name_b=table_b.field_set.get(primary=True).specific,
        lookup=data_fixture.create_formula_field(
            table=table_a, name="lookup", formula="join(lookup('link', 'primary'), '')"
        ),
        status=data_fixture.create_text_field(table=table_a, name="status"),
    )


def _create_public_view(
    data_fixture: Fixtures,
    user: AbstractUser,
    table: Table,
    filters: Iterable[Tuple[Field, str, str]],
    shown_fields: Iterable[Field] = (),
) -> GridView:
    view = data_fixture.create_grid_view(
        user, table=table, public=True, create_options=False
    )
    for field in shown_fields:
        data_fixture.create_grid_view_field_option(view, field, hidden=False)
    for field, filter_type, value in filters:
        data_fixture.create_view_filter(
            view=view, field=field, type=filter_type, value=value
        )
    return view


def _create_third_table_linked_from(
    data_fixture: Fixtures, user: AbstractUser, table_a: Table
) -> Tuple[Table, Field, Field]:
    table_c = data_fixture.create_database_table(database=table_a.database)
    name_c = data_fixture.create_text_field(table=table_c, name="primary", primary=True)
    link_c = FieldHandler().create_field(
        user, table_a, "link_row", name="link_c", link_row_table=table_c
    )
    return table_c, name_c, link_c


def _types_entering_or_leaving(payloads: List[Dict[str, Any]]) -> List[str]:
    return [
        p["type"] for p in payloads if p["type"] in ("rows_created", "rows_deleted")
    ]


@pytest.mark.django_db(transaction=True)
@override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=200)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_never_visible_row_changed_before_its_snapshot_sends_nothing_to_public_view(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table_b = data_fixture.create_database_table(database=database)
    x_b = data_fixture.create_text_field(table=table_b, name="x", primary=True)
    table_a = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table_a, name="primary", primary=True)
    secret_a = data_fixture.create_text_field(table=table_a, name="secret")
    link1, link2, link3 = [
        FieldHandler().create_field(
            user, table_a, "link_row", name=f"link{n}", link_row_table=table_b
        )
        for n in (1, 2, 3)
    ]
    lookup1, lookup2, lookup3 = [
        data_fixture.create_formula_field(
            table=table_a,
            name=f"lookup{n}",
            formula=f"join(lookup('link{n}', 'x'), '')",
        )
        for n in (1, 2, 3)
    ]
    filters = [(lookup2, "contains", "x2"), (lookup3, "contains", "x1")]
    shown_fields = [secret_a, lookup1, lookup2, lookup3]
    public_view = _create_public_view(
        data_fixture, user, table_a, filters, shown_fields
    )
    row_b1 = (
        RowHandler().create_rows(user, table_b, [{x_b.db_column: "x1"}]).created_rows[0]
    )
    b1 = [row_b1.id]
    secret_row = {link2.db_column: b1, link3.db_column: b1}
    secret_row[secret_a.db_column] = "NEVER VISIBLE"
    # Highest id: link2's snapshot reaches it only after the 150 rows link1's took.
    RowHandler().create_rows(
        user, table_a, [{link1.db_column: b1, link2.db_column: b1}] * 150 + [secret_row]
    )

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(
            user, table_b, [{"id": row_b1.id, x_b.db_column: "x2"}]
        )

    assert _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug) == []


@pytest.mark.parametrize(
    "actions,operations,expected_events",
    [
        ([], ["cascade:hidden too"], []),
        ([], ["cascade:keep", "cascade:hidden again"], []),
        ([], ["cascade:keep", "direct:on", "cascade:hidden again"], []),
        (["keep", "hidden again"], ["undo"], []),
        (
            ["keep"],
            ["cascade:keep too", "direct:off", "cascade:keep"],
            ["rows_deleted:a1"],
        ),
        (
            [],
            ["cascade:keep", "direct:off"],
            ["rows_created:a2", "rows_deleted:a1"],
        ),
        ([], ["cascade:keep", "direct:off", "cascade:hidden"], ["rows_deleted:a1"]),
        ([], ["cascade:keep", "create:on", "cascade:hidden"], []),
        (["keep"], ["cascade:keep too", "savepoint:hidden"], []),
        (["keep", "note:paid"], ["undo"], []),
    ],
    ids=[
        "never_visible_single_cascade",
        "never_visible_two_cascades",
        "never_visible_cascade_direct_cascade",
        "never_visible_undone_action_group",
        "direct_update_leaving_is_sent_once",
        "direct_update_leaves_its_row_to_the_direct_path",
        "direct_update_keeps_the_other_rows_snapshot",
        "row_created_in_the_transaction_is_left_to_the_create_path",
        "rows_of_two_broadcasts_are_left_undecided",
        "known_limit_a_first_cascade_no_view_follows_hides_the_leave",
    ],
)
@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_transaction_sends_each_row_entering_or_leaving_the_view_once(
    mock_broadcast_to_channel_group, data_fixture, actions, operations, expected_events
):
    user = data_fixture.create_user(session_id="session-id")
    tables = _create_linked_tables(data_fixture, user)
    public_view = tables.create_public_view(
        [(tables.lookup, "contains", "keep"), (tables.status, "equal", "on")],
        shown_fields=[tables.lookup],
    )
    note_b = data_fixture.create_text_field(table=tables.table_b, name="note")
    data_fixture.create_formula_field(
        table=tables.table_a, name="notes", formula="join(lookup('link', 'note'), '')"
    )

    def create_row_a(status: str) -> GeneratedTableModel:
        values = {tables.link.db_column: [row_b.id], tables.status.db_column: status}
        return RowHandler().create_rows(user, tables.table_a, [values]).created_rows[0]

    [row_b], [row_a1] = tables.create_rows(["hidden"], {tables.status.db_column: "on"})
    row_a2 = create_row_a("on")
    set_client_undo_redo_action_group_id(user, str(uuid.uuid4()))
    for kind, _, value in (action.rpartition(":") for action in actions):
        field = note_b if kind == "note" else tables.name_b
        with transaction.atomic():
            UpdateRowsActionType.do(
                user, tables.table_b, [{"id": row_b.id, field.db_column: value}]
            )
    set_client_undo_redo_action_group_id(user, None)

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        for kind, _, value in (operation.partition(":") for operation in operations):
            if kind == "cascade":
                tables.rename(row_b, value)
            elif kind == "savepoint":
                with transaction.atomic():
                    tables.rename(row_b, value)
            elif kind == "direct":
                RowHandler().update_rows(
                    user,
                    tables.table_a,
                    [{"id": row_a1.id, tables.status.db_column: value}],
                )
            elif kind == "create":
                create_row_a(value)
            else:
                scopes = [TableActionScopeType.value(tables.table_b.id)]
                ActionHandler.undo(user, scopes, "session-id")

    payloads = _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug)
    labels = {row_a1.id: "a1", row_a2.id: "a2"}
    assert [
        f"{payload['type']}:{labels.get(row['id'], 'new')}"
        for payload in payloads
        if payload["type"] in ("rows_created", "rows_deleted")
        for row in payload["rows"]
    ] == expected_events


@pytest.mark.parametrize(
    "filtered_link,expected_types",
    [("unchanged_link", ["rows_deleted"]), ("changed_link", [])],
)
@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_view_filtering_on_a_link_is_decided_unless_the_cascade_changed_it(
    mock_broadcast_to_channel_group, data_fixture, filtered_link, expected_types
):
    user = data_fixture.create_user()
    tables = _create_linked_tables(data_fixture, user)
    table_c, name_c, link_c = _create_third_table_linked_from(
        data_fixture, user, tables.table_a
    )
    filtered = link_c if filtered_link == "unchanged_link" else tables.link
    public_view = tables.create_public_view(
        [(tables.lookup, "contains", "keep"), (filtered, "not_empty", "")],
        shown_fields=[tables.lookup, tables.link, link_c],
    )
    [row_c] = (
        RowHandler()
        .create_rows(user, table_c, [{name_c.db_column: "shown"}])
        .created_rows
    )
    [row_b], [row_a] = tables.create_rows(["keep"], {link_c.db_column: [row_c.id]})

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        tables.rename(row_b, "gone")

    payloads = _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug)
    assert _types_entering_or_leaving(payloads) == expected_types
    assert "gone" not in str(payloads)
    if expected_types:
        assert payloads[0]["row_ids"] == [row_a.id]
        [deleted_row] = payloads[0]["rows"]
        assert [linked["value"] for linked in deleted_row[link_c.db_column]] == [
            "shown"
        ]
        # Already shows the rename at snapshot time, so its before value is unknown.
        assert tables.link.db_column not in deleted_row


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_link_changed_by_an_earlier_cascade_keeps_its_view_undecided(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    tables = _create_linked_tables(data_fixture, user)
    x_b = data_fixture.create_text_field(table=tables.table_b, name="x")
    [row_b], [row_a3] = tables.create_rows(["old"], {tables.status.db_column: "on"})
    with transaction.atomic():
        RowHandler().update_rows(
            user, tables.table_b, [{"id": row_b.id, x_b.db_column: "on"}]
        )
    lookup_x = data_fixture.create_formula_field(
        table=tables.table_a, formula="join(lookup('link', 'x'), '')"
    )
    view_v = tables.create_public_view(
        [(tables.link, "link_row_contains", "new"), (lookup_x, "contains", "on")],
    )
    view_w = tables.create_public_view([(tables.status, "equal", "on")])

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        tables.rename(row_b, "new")
        RowHandler().update_rows(
            user, tables.table_a, [{"id": row_a3.id, tables.status.db_column: "off"}]
        )
        RowHandler().update_rows(
            user, tables.table_b, [{"id": row_b.id, x_b.db_column: "off"}]
        )

    w_payloads = _payloads_for_view(mock_broadcast_to_channel_group, view_w.slug)
    assert _types_entering_or_leaving(w_payloads) == ["rows_deleted"]
    v_payloads = _payloads_for_view(mock_broadcast_to_channel_group, view_v.slug)
    assert _types_entering_or_leaving(v_payloads) == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_a_cascade_two_levels_deep_removes_a_paid_off_order_from_the_public_view(
    mock_broadcast_to_channel_group, data_fixture
):
    user = data_fixture.create_user()
    orders, payments, orders_payments = data_fixture.create_two_linked_tables(user=user)
    amount = FieldHandler().create_field(user, payments, "number", name="amount")
    FieldHandler().create_field(
        user, orders, "formula", name="paid", formula="sum(lookup('link', 'amount'))"
    )
    remaining = FieldHandler().create_field(
        user, orders, "formula", name="remaining", formula="100 - field('paid')"
    )
    public_view = _create_public_view(
        data_fixture, user, orders, [(remaining, "higher_than", "0")], [remaining]
    )
    [order] = RowHandler().create_rows(user, orders, [{}]).created_rows
    payment_values = {orders_payments.link_row_related_field.db_column: [order.id]}
    [payment] = (
        RowHandler()
        .create_rows(user, payments, [{amount.db_column: 40, **payment_values}])
        .created_rows
    )

    mock_broadcast_to_channel_group.reset_mock()
    with transaction.atomic():
        RowHandler().update_rows(
            user, payments, [{"id": payment.id, amount.db_column: 100}]
        )

    payloads = _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug)
    assert [payload["type"] for payload in payloads] == ["rows_deleted"]
    assert payloads[0]["row_ids"] == [order.id]
    assert payloads[0]["rows"][0][remaining.db_column] == "60"


def _count_cascade_queries(
    data_fixture: Fixtures,
    user: AbstractUser,
    view_filter: Optional[str],
    n_views: int = 1,
    n_entering_rows: int = 1,
    filters_disabled: bool = False,
) -> Tuple[int, bool]:
    """The query count of a cascade into A's lookup, and whether it locked A's rows."""

    tables = _create_linked_tables(data_fixture, user)
    _create_third_table_linked_from(data_fixture, user, tables.table_a)
    lookup_c = data_fixture.create_formula_field(
        table=tables.table_a, formula="join(lookup('link_c', 'primary'), '')"
    )
    filters = {
        "status": (tables.status, "equal", "on"),
        "lookup_not_updated": (lookup_c, "contains", "keep"),
        "lookup_updated": (tables.lookup, "contains", "keep"),
        "link_changed": (tables.link, "link_row_contains", "keep"),
    }
    for _ in range(n_views if view_filter else 0):
        view = tables.create_public_view([filters[view_filter]], [tables.lookup])
        GridView.objects.filter(id=view.id).update(filters_disabled=filters_disabled)
    rows_b, _ = tables.create_rows(["keep"] + [""] * n_entering_rows)

    with CaptureQueriesContext(connection) as captured:
        RowHandler().force_update_rows(
            user,
            tables.table_b,
            [
                {"id": row.id, tables.name_b.db_column: "keep" if index else "gone"}
                for index, row in enumerate(rows_b)
            ],
        )
    lock = f'FOR UPDATE OF "{tables.table_a.get_database_table_name()}"'
    sqls = [query["sql"] for query in captured.captured_queries]
    return len(sqls), any(lock in sql for sql in sqls)


@pytest.mark.parametrize(
    "view_filter,filters_disabled",
    [
        (None, False),
        ("status", False),
        ("lookup_not_updated", False),
        ("lookup_updated", True),
        ("link_changed", False),
    ],
)
@pytest.mark.django_db
def test_a_cascade_no_view_filter_can_follow_takes_no_lock_and_no_extra_query(
    data_fixture, view_filter, filters_disabled
):
    count = partial(_count_cascade_queries, data_fixture, data_fixture.create_user())
    # The first cascade fills process-wide caches, like the content types one.
    count(None)

    without_view = count(None)
    assert without_view == (ANY, False)
    assert count(view_filter, filters_disabled=filters_disabled) == without_view


@pytest.mark.django_db
def test_cascade_queries_are_flat_across_rows_and_checked_views(data_fixture):
    count = partial(_count_cascade_queries, data_fixture, data_fixture.create_user())
    # The first cascade fills process-wide caches, like the content types one.
    count("lookup_updated")

    checked = count("lookup_updated")
    assert checked == (ANY, True)
    assert count("lookup_updated", n_views=3) == checked
    assert count("lookup_updated", n_entering_rows=3) == checked


def _wait_until_another_connection_waits_for_a_lock() -> None:
    with connection.cursor() as cursor:
        for _ in range(200):
            cursor.execute(
                "SELECT 1 FROM pg_stat_activity WHERE datname = current_database() "
                "AND wait_event_type = 'Lock' AND pid <> pg_backend_pid()"
            )
            if cursor.fetchone():
                return
            time.sleep(0.05)
    raise AssertionError("No connection waited for a lock.")


@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.rows.signals.broadcast_dependant_rows_updated")
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_concurrent_cascades_into_a_row_send_one_rows_deleted(
    mock_broadcast_to_channel_group, mock_broadcast_task, data_fixture
):
    user = data_fixture.create_user()
    tables = _create_linked_tables(data_fixture, user)
    public_view = tables.create_public_view(
        [(tables.lookup, "contains_not", "gone")], [tables.lookup]
    )
    row_b1, row_b2 = (
        RowHandler()
        .create_rows(user, tables.table_b, [{tables.name_b.db_column: "keep"}] * 2)
        .created_rows
    )
    [row_a] = (
        RowHandler()
        .create_rows(
            user, tables.table_a, [{tables.link.db_column: [row_b1.id, row_b2.id]}]
        )
        .created_rows
    )
    first_cascaded = threading.Event()
    errors = []

    def first_transaction() -> None:
        try:
            with transaction.atomic():
                tables.rename(row_b1, "gone")
                first_cascaded.set()
                # Commits only once the second cascade waits for the row lock.
                _wait_until_another_connection_waits_for_a_lock()
        except Exception as exc:
            errors.append(exc)
        finally:
            connection.close()

    mock_broadcast_to_channel_group.reset_mock()
    thread = threading.Thread(target=first_transaction)
    thread.start()
    assert first_cascaded.wait(10)
    with transaction.atomic():
        tables.rename(row_b2, "gone too")
    thread.join(10)

    assert errors == []
    payloads = _payloads_for_view(mock_broadcast_to_channel_group, public_view.slug)
    assert _types_entering_or_leaving(payloads) == ["rows_deleted"]
    assert payloads[0]["row_ids"] == [row_a.id]
    assert payloads[0]["rows"][0][tables.lookup.db_column] == "keepkeep"


@pytest.mark.parametrize(
    "cascades", [[[0, 1]], [[0], [1]]], ids=["one_cascade", "two_cascades"]
)
@pytest.mark.django_db(transaction=True)
@patch("baserow.contrib.database.ws.table.signals.broadcast_to_permitted_users")
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_cascades_over_the_limit_refresh_the_table_and_its_public_views(
    mock_broadcast_to_channel_group,
    mock_broadcast_to_permitted_users,
    data_fixture,
    cascades,
):
    user = data_fixture.create_user()
    tables = _create_linked_tables(data_fixture, user)
    views = [
        tables.create_public_view(filters)
        for filters in ([(tables.lookup, "contains", "b")], [])
    ]
    rows_b, _ = tables.create_rows(["b", "b"])

    mock_broadcast_to_channel_group.reset_mock()
    with override_settings(DEPENDANT_ROWS_REALTIME_UPDATE_LIMIT=1):
        with transaction.atomic():
            for indexes in cascades:
                RowHandler().update_rows(
                    user,
                    tables.table_b,
                    [
                        {"id": rows_b[i].id, tables.name_b.db_column: "c"}
                        for i in indexes
                    ],
                )

    for view in views:
        assert _payloads_for_view(mock_broadcast_to_channel_group, view.slug) == [
            {"type": "force_view_rows_refresh", "view_id": view.slug}
        ]
    mock_broadcast_to_permitted_users.delay.assert_called_once()
    table_payload = mock_broadcast_to_permitted_users.delay.call_args[0][4]
    assert table_payload["table_id"] == tables.table_a.id
    assert table_payload["force_table_refresh"] is True
