from datetime import datetime
from unittest.mock import ANY, call, patch

from django.test.utils import override_settings
from django.urls import reverse

import pytest
from baserow_premium.views.view_types import (
    CalendarViewType,
    KanbanViewType,
    TimelineViewType,
)
from starlette.status import HTTP_200_OK

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.fields.models import DateField
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.views.view_ownership_types import (
    CollaborativeViewOwnershipType,
)
from baserow.contrib.database.views.view_types import GalleryViewType, GridViewType
from baserow.contrib.database.ws.views.rows.handler import ViewRealtimeRowsHandler
from baserow.core.utils import get_value_at_path
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
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
    enterprise_data_fixture.create_grid_view(
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
    enterprise_data_fixture.create_form_view(
        table=table,
        ownership_type=RestrictedViewOwnershipType.type,
        public=True,
    )
    enterprise_data_fixture.create_form_view(
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


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_filters_are_visible_for_builders_and_up(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, type="equal", field=text_field
    )
    enterprise_data_fixture.create_view_filter_group(view=restricted_view)

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=filters",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json)
    assert len(response_json[0]["filters"]) == 1
    assert len(response_json[0]["filter_groups"]) == 1


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_filters_are_invisible_for_editors_and_down(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=restricted_view, type="equal", field=text_field
    )
    enterprise_data_fixture.create_view_filter_group(view=restricted_view)

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=restricted_view.id),
    )

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=filters",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json)
    assert len(response_json[0]["filters"]) == 0
    assert len(response_json[0]["filter_groups"]) == 0


view_type_url_mapping = {
    GridViewType.type: ("api:database:views:grid:list", "create_grid_view", "results"),
    GalleryViewType.type: (
        "api:database:views:gallery:list",
        "create_gallery_view",
        "results",
    ),
    KanbanViewType.type: (
        "api:database:views:kanban:list",
        "create_kanban_view",
        "rows.null.results",
    ),
    CalendarViewType.type: (
        "api:database:views:calendar:list",
        "create_calendar_view",
        "rows.2021-01-01.results",
    ),
    TimelineViewType.type: (
        "api:database:views:timeline:list",
        "create_timeline_view",
        "results",
    ),
}


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_filters_are_not_forcefully_applied_to_all_views_types_for_builders_and_up(
    enterprise_data_fixture, premium_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)

    RowHandler().create_row(user, table, values={f"field_{text_field.id}": "a"})
    RowHandler().create_row(user, table, values={f"field_{text_field.id}": "b"})

    for view_type in view_type_registry.get_all():
        if not view_type.can_filter:
            continue

        if view_type.type not in view_type_url_mapping:
            assert False, f"{view_type.type} must be added to `view_type_url_mapping`"

        view_path, fixture_create, response_path = view_type_url_mapping[view_type.type]

        view = getattr(premium_data_fixture, fixture_create)(
            table=table, ownership_type=RestrictedViewOwnershipType.type
        )
        enterprise_data_fixture.create_view_filter(
            view=view, type="equal", value="a", field=text_field
        )

        for field in table.field_set.all():
            if field.specific_class == DateField:
                table.get_model().objects.all().update(
                    **{f"field_{field.id}": datetime(2021, 1, 1)}
                )

        # Adding a filter to the query params should enable the adhoc filtering,
        # if the user is builder or higher, which results in not applying the
        # original view filters. We therefore expect both row_1 and row_2 in the
        # response.
        query_param = (
            '?filters={"filter_type":"AND","filters":['
            '{"type":"not_equal","field":' + str(text_field.id) + ',"value":"c"}'
            '],"groups":[]}'
            "&from_timestamp=2021-01-01"
            "&to_timestamp=2021-02-01"
        )
        response = api_client.get(
            reverse(view_path, kwargs={"view_id": view.id}) + query_param,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        # We expect both row_1 and row_2 when applying the query params.
        assert len(get_value_at_path(response_json, response_path)) == 2, view_type.type


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_filters_are_forcefully_applied_to_all_views_types_for_editors_and_down(
    enterprise_data_fixture,
    premium_data_fixture,
    api_client,
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )

    RowHandler().create_row(user, table, values={f"field_{text_field.id}": "a"})
    RowHandler().create_row(user, table, values={f"field_{text_field.id}": "b"})

    for view_type in view_type_registry.get_all():
        if not view_type.can_filter:
            continue

        if view_type.type not in view_type_url_mapping:
            assert False, f"{view_type.type} must be added to `view_type_url_mapping`"

        view_path, fixture_create, response_path = view_type_url_mapping[view_type.type]

        view = getattr(premium_data_fixture, fixture_create)(
            table=table, ownership_type=RestrictedViewOwnershipType.type
        )
        enterprise_data_fixture.create_view_filter(
            view=view, type="equal", value="a", field=text_field
        )

        RoleAssignmentHandler().assign_role(
            user2,
            workspace,
            role=editor_role,
            scope=View.objects.get(id=view.id),
        )

        for field in table.field_set.all():
            if field.specific_class == DateField:
                table.get_model().objects.all().update(
                    **{f"field_{field.id}": datetime(2021, 1, 1)}
                )

        # Adding a filter to the query params should not enable the adhoc filtering,
        # if the user is editor or lower, so the view filters are forcefully applied.
        # We therefore expect only row_1 in the response.
        query_param = (
            '?filters={"filter_type":"AND","filters":['
            '{"type":"not_equal","field":' + str(text_field.id) + ',"value":"c"}'
            '],"groups":[]}'
            "&from_timestamp=2021-01-01"
            "&to_timestamp=2021-02-01"
        )
        response = api_client.get(
            reverse(view_path, kwargs={"view_id": view.id}) + query_param,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token2}",
        )
        response_json = response.json()
        assert response.status_code == HTTP_200_OK
        # We expect only row_1 to be in there because user2 only has editor permissions
        # to the view and should therefore not be able to see row 2 because it does not
        # match the filters of the view.
        assert len(get_value_at_path(response_json, response_path)) == 1, view_type.type
