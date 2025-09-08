from unittest.mock import ANY, call, patch

import pytest

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.view_ownership_types import (
    CollaborativeViewOwnershipType,
)
from baserow.contrib.database.ws.views.rows.handler import ViewRealtimeRowsHandler
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType


@pytest.mark.django_db
def test_get_public_views_which_include_row(
    enterprise_data_fixture, django_assert_num_queries
):
    """
    One test to check if the restricted view is included in the
    `get_filtered_views_where_row_is_visible` is enough because we already have
    plenty of tests related to the public view, which reuses the same code, in
    `tests/baserow/contrib/database/view/test_view_handler.py`
    """

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    visible_field = enterprise_data_fixture.create_text_field(table=table)
    restricted_view = enterprise_data_fixture.create_grid_view(
        user, table=table, order=0, ownership_type=RestrictedViewOwnershipType.type
    )
    normal_view = enterprise_data_fixture.create_grid_view(
        user,
        table=table,
        order=0,
    )
    # Should not appear in any results
    enterprise_data_fixture.create_form_view(
        user, table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_grid_view(user, table=table)

    # Public View 1 has filters which match row 1
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, field=visible_field, type="equal", value="Visible"
    )

    row = RowHandler().create_row(
        user=user,
        table=table,
        values={
            f"field_{visible_field.id}": "Visible",
        },
    )
    row2 = RowHandler().create_row(
        user=user,
        table=table,
        values={
            f"field_{visible_field.id}": "Not Visible",
        },
    )

    model = table.get_model()
    checker = ViewRealtimeRowsHandler().get_views_row_checker(
        table, model, only_include_views_which_want_realtime_events=True
    )
    assert checker.get_filtered_views_where_row_is_visible(row) == [
        restricted_view,
    ]
    assert checker.get_filtered_views_where_row_is_visible(row2) == []


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_when_row_created_restricted_views_receive_restricted_row_ws_event(
    mock_broadcast_to_channel_group,
    enterprise_data_fixture,
):
    """
    One test to check if correct payload is broadcasted is enough because we already
    have plenty of tests related to the public view, which reuses the same code, in
    `tests/baserow/contrib/database/ws/public/test_public_ws_rows_signals.py`
    """

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    visible_field = enterprise_data_fixture.create_text_field(table=table)
    # Only restricted event should be sent to this view.
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table,
        ownership_type=RestrictedViewOwnershipType.type,
        public=False,
    )
    # Both public and restricted event should be sent to this view.
    public_and_restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type, public=True
    )
    # No event should be sent to this view.
    form_view = enterprise_data_fixture.create_form_view(
        table=table,
        ownership_type=RestrictedViewOwnershipType.type,
        public=True,
    )
    grid_view = enterprise_data_fixture.create_form_view(
        table=table,
        ownership_type=CollaborativeViewOwnershipType.type,
        public=False,
    )

    row = RowHandler().create_row(
        user=user,
        table=table,
        values={
            f"field_{visible_field.id}": "Visible",
        },
    )

    assert mock_broadcast_to_channel_group.delay.mock_calls == (
        [
            call(f"table-{table.id}", ANY, ANY, None),
            call(
                f"restricted-view-{restricted_view.id}",
                {
                    "type": "rows_created",
                    "table_id": table.id,
                    "rows": [
                        {
                            "id": row.id,
                            "order": "1.00000000000000000000",
                            f"field_{visible_field.id}": "Visible",
                        }
                    ],
                    "metadata": {},
                    "before_row_id": None,
                },
                None,
                None,
            ),
            call(
                f"view-{public_and_restricted_view.slug}",
                {
                    "type": "rows_created",
                    "table_id": PUBLIC_PLACEHOLDER_ENTITY_ID,
                    "rows": [
                        {
                            "id": row.id,
                            "order": "1.00000000000000000000",
                            f"field_{visible_field.id}": "Visible",
                        }
                    ],
                    "metadata": {},
                    "before_row_id": None,
                },
                None,
                None,
            ),
            call(
                f"restricted-view-{public_and_restricted_view.id}",
                {
                    "type": "rows_created",
                    "table_id": table.id,
                    "rows": [
                        {
                            "id": row.id,
                            "order": "1.00000000000000000000",
                            f"field_{visible_field.id}": "Visible",
                        }
                    ],
                    "metadata": {},
                    "before_row_id": None,
                },
                None,
                None,
            ),
        ]
    )
