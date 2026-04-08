from datetime import datetime
from unittest.mock import ANY, call, patch

from django.db import connection
from django.test.utils import CaptureQueriesContext, override_settings
from django.urls import reverse

import pytest
from starlette.status import (
    HTTP_200_OK,
    HTTP_400_BAD_REQUEST,
    HTTP_401_UNAUTHORIZED,
    HTTP_404_NOT_FOUND,
)

from baserow.contrib.database.api.constants import PUBLIC_PLACEHOLDER_ENTITY_ID
from baserow.contrib.database.fields.models import DateField
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import (
    GalleryViewFieldOptions,
    GridViewFieldOptions,
    View,
    ViewDecoration,
    ViewGroupBy,
    ViewSort,
)
from baserow.contrib.database.views.registries import view_type_registry
from baserow.contrib.database.views.view_ownership_types import (
    CollaborativeViewOwnershipType,
)
from baserow.contrib.database.views.view_types import GalleryViewType, GridViewType
from baserow.contrib.database.ws.views.rows.handler import ViewRealtimeRowsHandler
from baserow.core.exceptions import PermissionDenied as BaserowPermissionDenied
from baserow.core.utils import get_value_at_path
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType
from baserow_enterprise.ws.restricted_view.fields.signals import (
    _broadcast_payload_to_all_restricted_views,
)
from baserow_premium.row_comments.handler import (
    RowCommentHandler,
    RowCommentsNotificationModes,
)
from baserow_premium.views.models import (
    CalendarViewFieldOptions,
    KanbanViewFieldOptions,
    TimelineViewFieldOptions,
)
from baserow_premium.views.view_types import (
    CalendarViewType,
    KanbanViewType,
    TimelineViewType,
)


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


def _set_field_option(view, field, hidden):
    model_map = {
        "gridviewfieldoptions_set": (GridViewFieldOptions, "grid_view"),
        "galleryviewfieldoptions_set": (GalleryViewFieldOptions, "gallery_view"),
        "kanbanviewfieldoptions_set": (KanbanViewFieldOptions, "kanban_view"),
        "calendarviewfieldoptions_set": (CalendarViewFieldOptions, "calendar_view"),
        "timelineviewfieldoptions_set": (TimelineViewFieldOptions, "timeline_view"),
    }
    for attr, (model_cls, fk_name) in model_map.items():
        if hasattr(view, attr):
            model_cls.objects.update_or_create(
                **{fk_name: view, "field": field}, defaults={"hidden": hidden}
            )
            return

    raise ValueError(f"Unsupported view type: {type(view)}")


def _set_field_hidden(view, hidden_field, visible_fields=None):
    _set_field_option(view, hidden_field, hidden=True)
    for f in visible_fields or []:
        _set_field_option(view, f, hidden=False)


# Maps view type to (url_name, fixture method name, response_path). Kanban and
# Calendar are tested separately because they need extra setup (single_select field
# and date field respectively).
hidden_field_view_type_url_mapping = {
    GridViewType.type: (
        "api:database:views:grid:list",
        "create_grid_view",
        "results",
    ),
    GalleryViewType.type: (
        "api:database:views:gallery:list",
        "create_gallery_view",
        "results",
    ),
    TimelineViewType.type: (
        "api:database:views:timeline:list",
        "create_timeline_view",
        "results",
    ),
}


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_hidden_fields_visible_for_builders_and_up(
    enterprise_data_fixture, premium_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "vis",
            f"field_{hidden_field.id}": "hid",
        },
    )

    for view_type_str, (
        view_path,
        fixture_create,
        response_path,
    ) in hidden_field_view_type_url_mapping.items():
        view = getattr(premium_data_fixture, fixture_create)(
            table=table, ownership_type=RestrictedViewOwnershipType.type
        )

        _set_field_hidden(view, hidden_field, visible_fields=[visible_field])

        response = api_client.get(
            reverse(view_path, kwargs={"view_id": view.id}) + "?include=field_options",
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token}",
        )
        assert response.status_code == HTTP_200_OK, view_type_str
        response_json = response.json()
        rows = get_value_at_path(response_json, response_path)
        assert f"field_{hidden_field.id}" in rows[0], (
            f"Builder should see hidden field in {view_type_str}"
        )
        assert str(hidden_field.id) in response_json.get("field_options", {}), (
            f"Builder should see hidden field options in {view_type_str}"
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_hidden_fields_excluded_for_editors_and_down(
    enterprise_data_fixture, premium_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )

    RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "vis",
            f"field_{hidden_field.id}": "hid",
        },
    )

    for view_type_str, (
        view_path,
        fixture_create,
        response_path,
    ) in hidden_field_view_type_url_mapping.items():
        view = getattr(premium_data_fixture, fixture_create)(
            table=table, ownership_type=RestrictedViewOwnershipType.type
        )

        # Hide the field in this view.
        _set_field_hidden(view, hidden_field, visible_fields=[visible_field])

        RoleAssignmentHandler().assign_role(
            user2,
            workspace,
            role=editor_role,
            scope=View.objects.get(id=view.id),
        )

        response = api_client.get(
            reverse(view_path, kwargs={"view_id": view.id}) + "?include=field_options",
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token2}",
        )
        assert response.status_code == HTTP_200_OK, view_type_str
        response_json = response.json()
        rows = get_value_at_path(response_json, response_path)
        # Editor should NOT see the hidden field value.
        assert f"field_{hidden_field.id}" not in rows[0], (
            f"Editor should not see hidden field in {view_type_str}"
        )
        # Editor should see the visible field.
        assert f"field_{visible_field.id}" in rows[0], (
            f"Editor should see visible field in {view_type_str}"
        )
        field_options = response_json.get("field_options", {})
        assert str(hidden_field.id) not in field_options, (
            f"Editor should not see hidden field options in {view_type_str}"
        )
        assert str(visible_field.id) in field_options, (
            f"Editor should see visible field options in {view_type_str}"
        )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_editor_cannot_create_row_with_hidden_field_values(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    user2 = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    with pytest.raises(BaserowPermissionDenied):
        RowHandler().create_row(
            user2,
            table,
            values={f"field_{hidden_field.id}": "sneaky"},
            view=view,
        )

    # Editor can create a row with only visible field values.
    row = RowHandler().create_row(
        user2,
        table,
        values={f"field_{visible_field.id}": "ok"},
        view=view,
    )
    assert row is not None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_editor_cannot_update_row_with_hidden_field_values(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    user2 = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    row = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "vis",
            f"field_{hidden_field.id}": "hid",
        },
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    # Editor tries to update hidden field value via view — should fail.
    with pytest.raises(BaserowPermissionDenied):
        RowHandler().update_row(
            user2,
            table,
            row,
            values={f"field_{hidden_field.id}": "sneaky"},
            view=view,
        )

    # Editor can update visible field values.
    updated_row = RowHandler().update_row(
        user2,
        table,
        row,
        values={f"field_{visible_field.id}": "updated"},
        view=view,
    )
    assert getattr(updated_row, f"field_{visible_field.id}") == "updated"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_editor_cannot_create_row_with_hidden_field_values_user_field_names(
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    user2 = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(
        table=table, primary=True, name="Visible"
    )
    hidden_field = enterprise_data_fixture.create_text_field(table=table, name="Hidden")

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    # Editor tries to create a row setting a hidden field via user_field_names — should
    # fail.
    with pytest.raises(BaserowPermissionDenied):
        RowHandler().create_row(
            user2,
            table,
            values={"Hidden": "sneaky"},
            view=view,
            user_field_names=True,
        )

    # Editor can create a row with only visible field values using user_field_names.
    row = RowHandler().create_row(
        user2,
        table,
        values={"Visible": "ok"},
        view=view,
        user_field_names=True,
    )
    assert row is not None


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_fetching_restricted_view_fields(
    enterprise_data_fixture,
    api_client,
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table, primary=False)

    grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user,
        create_options=False,
        ownership_type=RestrictedViewOwnershipType.type,
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, visible_field, hidden=False
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, hidden_field, hidden=True
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=editor_role, scope=View.objects.get(pk=grid.id)
    )

    # Without view param, editor has no table-level field access.
    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url,
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    # With view param, editor sees only visible fields.
    response = api_client.get(
        url + f"?view={grid.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 1
    assert response_json[0]["id"] == visible_field.id


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_fetching_restricted_view_fields_as_admin(
    enterprise_data_fixture,
    api_client,
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table, primary=False)

    grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user,
        create_options=False,
        ownership_type=RestrictedViewOwnershipType.type,
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, visible_field, hidden=False
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, hidden_field, hidden=True
    )

    admin_role = Role.objects.get(uid="ADMIN")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(user2, workspace, role=admin_role, scope=table)

    # Admin sees all fields even hidden ones.
    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url + f"?view={grid.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_200_OK
    assert len(response_json) == 2


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_fetching_restricted_view_fields_view_does_not_belong_to_table(
    enterprise_data_fixture,
    api_client,
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    table2 = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)

    grid = enterprise_data_fixture.create_grid_view(
        table=table2,
        user=user,
        create_options=False,
        ownership_type=RestrictedViewOwnershipType.type,
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, visible_field, hidden=False
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    workspace = table.database.workspace
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=editor_role, scope=View.objects.get(pk=grid.id)
    )

    # View belongs to a different table — should return 404.
    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url + f"?view={grid.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    response_json = response.json()
    assert response.status_code == HTTP_404_NOT_FOUND
    assert response_json["error"] == "ERROR_VIEW_DOES_NOT_EXIST"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_hidden_fields_excluded_for_kanban_view_editor(
    enterprise_data_fixture, premium_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "vis",
            f"field_{hidden_field.id}": "hid",
        },
    )

    view = premium_data_fixture.create_kanban_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    _set_field_hidden(view, hidden_field, visible_fields=[visible_field])

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    response = api_client.get(
        reverse("api:database:views:kanban:list", kwargs={"view_id": view.id})
        + "?include=field_options",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    # Kanban groups rows under select option keys. Check any group's first row.
    for key, group in response_json.get("rows", {}).items():
        for row in group.get("results", []):
            assert f"field_{hidden_field.id}" not in row, (
                "Editor should not see hidden field in kanban row"
            )
            assert f"field_{visible_field.id}" in row, (
                "Editor should see visible field in kanban row"
            )

    field_options = response_json.get("field_options", {})
    assert str(hidden_field.id) not in field_options, (
        "Editor should not see hidden field options in kanban"
    )
    assert str(visible_field.id) in field_options, (
        "Editor should see visible field options in kanban"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_hidden_fields_excluded_for_calendar_view_editor(
    enterprise_data_fixture, premium_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = premium_data_fixture.create_calendar_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    _set_field_hidden(view, hidden_field, visible_fields=[visible_field])

    # Fill date field so the calendar has rows in the queried range.
    date_field = view.date_field
    model = table.get_model()
    RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "vis",
            f"field_{hidden_field.id}": "hid",
            f"field_{date_field.id}": "2021-01-15",
        },
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    response = api_client.get(
        reverse("api:database:views:calendar:list", kwargs={"view_id": view.id})
        + "?include=field_options&from_timestamp=2021-01-01&to_timestamp=2021-02-01",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()

    # Calendar groups rows by date. Check each group's rows.
    for key, group in response_json.get("rows", {}).items():
        for row in group.get("results", []):
            assert f"field_{hidden_field.id}" not in row, (
                "Editor should not see hidden field in calendar row"
            )
            assert f"field_{visible_field.id}" in row, (
                "Editor should see visible field in calendar row"
            )

    field_options = response_json.get("field_options", {})
    assert str(hidden_field.id) not in field_options, (
        "Editor should not see hidden field options in calendar"
    )
    assert str(visible_field.id) in field_options, (
        "Editor should see visible field options in calendar"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_grid_view_filter_endpoint_excludes_hidden_fields(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    row = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "vis",
            f"field_{hidden_field.id}": "secret",
        },
    )

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    # The POST filter endpoint fetches specific rows/fields.
    response = api_client.post(
        reverse("api:database:views:grid:list", kwargs={"view_id": view.id}),
        {"row_ids": [row.id], "field_ids": [visible_field.id, hidden_field.id]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert len(response_json) == 1
    assert f"field_{hidden_field.id}" not in response_json[0]
    assert f"field_{visible_field.id}" in response_json[0]


@pytest.mark.django_db
@override_settings(DEBUG=True)
@pytest.mark.parametrize("role_uid", ["VIEWER", "COMMENTER"])
def test_hidden_fields_excluded_from_field_listing_for_all_lower_roles(
    enterprise_data_fixture, api_client, role_uid
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    grid = enterprise_data_fixture.create_grid_view(
        table=table,
        user=user,
        create_options=False,
        ownership_type=RestrictedViewOwnershipType.type,
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, visible_field, hidden=False
    )
    enterprise_data_fixture.create_grid_view_field_option(
        grid, hidden_field, hidden=True
    )

    role = Role.objects.get(uid=role_uid)
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=role, scope=View.objects.get(pk=grid.id)
    )

    url = reverse("api:database:fields:list", kwargs={"table_id": table.id})
    response = api_client.get(
        url + f"?view={grid.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    field_ids = {f["id"] for f in response.json()}
    assert visible_field.id in field_ids
    assert hidden_field.id not in field_ids


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_hidden_field_row_values_not_leaked_in_grid_view(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "public",
            f"field_{hidden_field.id}": "secret",
        },
    )
    RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "public2",
            f"field_{hidden_field.id}": "secret2",
        },
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    response = api_client.get(
        reverse("api:database:views:grid:list", kwargs={"view_id": view.id}),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    rows = response.json()["results"]
    assert len(rows) == 2
    for row in rows:
        assert f"field_{hidden_field.id}" not in row, (
            "Hidden field value must not appear in row response"
        )
        assert "secret" not in str(row), (
            "Hidden field value must not leak anywhere in the row"
        )
        assert f"field_{visible_field.id}" in row


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_hidden_field_aggregation_excluded_for_editor(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_number_field(table=table)
    hidden_field = enterprise_data_fixture.create_number_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view,
        field=hidden_field,
        defaults={
            "hidden": True,
            "aggregation_type": "sum",
            "aggregation_raw_type": "sum",
        },
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view,
        field=visible_field,
        defaults={
            "hidden": False,
            "aggregation_type": "sum",
            "aggregation_raw_type": "sum",
        },
    )

    RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": 10,
            f"field_{hidden_field.id}": 99,
        },
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    response = api_client.get(
        reverse(
            "api:database:views:grid:field-aggregations",
            kwargs={"view_id": view.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    # Visible field aggregation should be present.
    assert f"field_{visible_field.id}" in response_json
    # Hidden field aggregation must not leak.
    assert f"field_{hidden_field.id}" not in response_json


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_search_does_not_match_hidden_fields_for_editor(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "public",
            f"field_{hidden_field.id}": "uniquesecret",
        },
    )

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    # Editor searches for a value only present in the hidden field.
    response = api_client.get(
        reverse("api:database:views:grid:list", kwargs={"view_id": view.id})
        + "?search=uniquesecret",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 0, (
        "Editor should not find rows by hidden field value"
    )

    # Admin can still find the row by searching the hidden field value.
    response = api_client.get(
        reverse("api:database:views:grid:list", kwargs={"view_id": view.id})
        + "?search=uniquesecret",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    assert response.json()["count"] == 1, "Admin should find rows by hidden field value"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_sorts_on_hidden_fields_excluded_for_editor(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    # Create sorts: one on hidden field, one on visible field.
    ViewSort.objects.create(view=view, field=hidden_field, order=0)
    ViewSort.objects.create(view=view, field=visible_field, order=1)

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    # Editor lists views with sortings included.
    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=sortings",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    views_json = response.json()
    target_view = [v for v in views_json if v["id"] == view.id][0]
    sort_fields = [s["field"] for s in target_view["sortings"]]
    assert hidden_field.id not in sort_fields, (
        "Editor should not see sort on hidden field"
    )
    assert visible_field.id in sort_fields, "Editor should see sort on visible field"

    # Admin sees all sorts.
    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=sortings",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    views_json = response.json()
    target_view = [v for v in views_json if v["id"] == view.id][0]
    sort_fields = [s["field"] for s in target_view["sortings"]]
    assert hidden_field.id in sort_fields, "Admin should see sort on hidden field"
    assert visible_field.id in sort_fields, "Admin should see sort on visible field"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_group_bys_on_hidden_fields_excluded_for_editor(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    # Create group bys: one on hidden field, one on visible field.
    ViewGroupBy.objects.create(view=view, field=hidden_field, order=0)
    ViewGroupBy.objects.create(view=view, field=visible_field, order=1)

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    # Editor lists views with group_bys included.
    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=group_bys",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    views_json = response.json()
    target_view = [v for v in views_json if v["id"] == view.id][0]
    group_by_fields = [g["field"] for g in target_view["group_bys"]]
    assert hidden_field.id not in group_by_fields, (
        "Editor should not see group by on hidden field"
    )
    assert visible_field.id in group_by_fields, (
        "Editor should see group by on visible field"
    )

    # Admin sees all group bys.
    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=group_bys",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    views_json = response.json()
    target_view = [v for v in views_json if v["id"] == view.id][0]
    group_by_fields = [g["field"] for g in target_view["group_bys"]]
    assert hidden_field.id in group_by_fields, (
        "Admin should see group by on hidden field"
    )
    assert visible_field.id in group_by_fields, (
        "Admin should see group by on visible field"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_decorations_excluded_for_editor(enterprise_data_fixture, api_client):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    # Create a decoration on the view.
    ViewDecoration.objects.create(
        view=view,
        type="left_border_color",
        value_provider_type="conditional_color",
        value_provider_conf={
            "colors": [
                {
                    "filters": [
                        {"field": hidden_field.id, "type": "equal", "value": "test"}
                    ],
                    "color": "red",
                }
            ]
        },
        order=0,
    )

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )
    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=editor_role,
        scope=View.objects.get(id=view.id),
    )

    # Editor lists views with decorations included.
    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=decorations",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    views_json = response.json()
    target_view = [v for v in views_json if v["id"] == view.id][0]
    assert len(target_view["decorations"]) == 0, "Editor should not see any decorations"

    # Admin sees decorations.
    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=decorations",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    views_json = response.json()
    target_view = [v for v in views_json if v["id"] == view.id][0]
    assert len(target_view["decorations"]) == 1, "Admin should see decorations"


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_realtime_row_created_does_not_expose_hidden_field(
    mock_broadcast_to_channel_group,
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    visible_field = enterprise_data_fixture.create_text_field(table=table)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table,
        ownership_type=RestrictedViewOwnershipType.type,
        public=False,
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=restricted_view, field=hidden_field, defaults={"hidden": True}
    )

    row = RowHandler().create_row(
        user=user,
        table=table,
        values={
            f"field_{visible_field.id}": "Visible",
            f"field_{hidden_field.id}": "Secret",
        },
    )

    # Find the restricted-view broadcast call.
    restricted_calls = [
        c
        for c in mock_broadcast_to_channel_group.delay.mock_calls
        if f"restricted-view-{restricted_view.id}" in str(c)
    ]
    assert len(restricted_calls) == 1

    payload = restricted_calls[0].args[1]
    assert payload["type"] == "rows_created"
    broadcast_row = payload["rows"][0]
    assert f"field_{visible_field.id}" in broadcast_row
    assert broadcast_row[f"field_{visible_field.id}"] == "Visible"
    assert f"field_{hidden_field.id}" not in broadcast_row, (
        "Hidden field value must not be included in the restricted view WS event"
    )


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_realtime_row_updated_does_not_expose_hidden_field(
    mock_broadcast_to_channel_group,
    enterprise_data_fixture,
):
    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    visible_field = enterprise_data_fixture.create_text_field(table=table)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table,
        ownership_type=RestrictedViewOwnershipType.type,
        public=False,
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=restricted_view, field=hidden_field, defaults={"hidden": True}
    )

    row = RowHandler().create_row(
        user=user,
        table=table,
        values={
            f"field_{visible_field.id}": "Visible",
            f"field_{hidden_field.id}": "Secret",
        },
    )

    mock_broadcast_to_channel_group.delay.reset_mock()

    RowHandler().update_row_by_id(
        user=user,
        table=table,
        row_id=row.id,
        values={
            f"field_{visible_field.id}": "Updated",
            f"field_{hidden_field.id}": "StillSecret",
        },
    )

    # Find the restricted-view broadcast call.
    restricted_calls = [
        c
        for c in mock_broadcast_to_channel_group.delay.mock_calls
        if f"restricted-view-{restricted_view.id}" in str(c)
    ]
    assert len(restricted_calls) == 1

    payload = restricted_calls[0].args[1]
    assert payload["type"] == "rows_updated"

    # Check the updated row payload.
    broadcast_row = payload["rows"][0]
    assert f"field_{visible_field.id}" in broadcast_row
    assert broadcast_row[f"field_{visible_field.id}"] == "Updated"
    assert f"field_{hidden_field.id}" not in broadcast_row, (
        "Hidden field value must not be included in the restricted view WS update event"
    )

    # Check the before-update row payload.
    old_row = payload["rows_before_update"][0]
    assert f"field_{visible_field.id}" in old_row
    assert old_row[f"field_{visible_field.id}"] == "Visible"
    assert f"field_{hidden_field.id}" not in old_row, (
        "Hidden field value must not be in rows_before_update of the restricted view "
        "WS event"
    )


@pytest.mark.django_db
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_broadcast_payload_to_all_restricted_views_no_n_plus_one_queries(
    mock_broadcast_to_channel_group,
    enterprise_data_fixture,
    premium_data_fixture,
    django_assert_num_queries,
):
    """
    Test that _broadcast_payload_to_all_restricted_views does not issue N+1
    queries when checking hidden fields across multiple restricted views.
    All view types except form are tested.
    """

    enterprise_data_fixture.enable_enterprise()
    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    visible_field = enterprise_data_fixture.create_text_field(table=table)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    restricted = RestrictedViewOwnershipType.type
    num_views_per_type = 2

    # Grid views
    for _ in range(num_views_per_type):
        view = enterprise_data_fixture.create_grid_view(
            user, table=table, ownership_type=restricted
        )
        enterprise_data_fixture.create_grid_view_field_option(
            view, visible_field, hidden=False, order=1
        )
        enterprise_data_fixture.create_grid_view_field_option(
            view, hidden_field, hidden=True, order=2
        )

    # Gallery views
    for _ in range(num_views_per_type):
        view = enterprise_data_fixture.create_gallery_view(
            user, table=table, ownership_type=restricted, create_options=False
        )
        enterprise_data_fixture.create_gallery_view_field_option(
            view, visible_field, hidden=False, order=1
        )
        enterprise_data_fixture.create_gallery_view_field_option(
            view, hidden_field, hidden=True, order=2
        )

    # Kanban views
    single_select_field = enterprise_data_fixture.create_single_select_field(
        table=table
    )
    for _ in range(num_views_per_type):
        view = premium_data_fixture.create_kanban_view(
            table=table,
            ownership_type=restricted,
            single_select_field=single_select_field,
            create_options=False,
        )
        premium_data_fixture.create_kanban_view_field_option(
            view, visible_field, hidden=False, order=1
        )
        premium_data_fixture.create_kanban_view_field_option(
            view, hidden_field, hidden=True, order=2
        )

    # Calendar views
    date_field = enterprise_data_fixture.create_date_field(table=table)
    for _ in range(num_views_per_type):
        view = premium_data_fixture.create_calendar_view(
            table=table,
            ownership_type=restricted,
            date_field=date_field,
            create_options=False,
        )
        premium_data_fixture.create_calendar_view_field_option(
            view, visible_field, hidden=False, order=1
        )
        premium_data_fixture.create_calendar_view_field_option(
            view, hidden_field, hidden=True, order=2
        )

    # Timeline views
    start_date_field = enterprise_data_fixture.create_date_field(table=table)
    end_date_field = enterprise_data_fixture.create_date_field(table=table)
    for _ in range(num_views_per_type):
        view = premium_data_fixture.create_timeline_view(
            table=table,
            ownership_type=restricted,
            start_date_field=start_date_field,
            end_date_field=end_date_field,
            create_options=False,
        )
        premium_data_fixture.create_timeline_view_field_option(
            view, visible_field, hidden=False, order=1
        )
        premium_data_fixture.create_timeline_view_field_option(
            view, hidden_field, hidden=True, order=2
        )

    total_views = num_views_per_type * 5
    payload = {"type": "field_created", "field": {"id": visible_field.id}}

    # The query count should be constant regardless of the number of views.
    # We expect:
    # 1. Base View query (with content_type select_related)
    # 2-3. Prefetch for table__field_set (table lookup + field_set lookup)
    # 4-13. One query per content type (5 types) to fetch specific view subclass
    #       rows + one prefetch query per content type for the field options
    # Total: 1 (base) + 2 (table + field_set) + 5 (specific) + 5 (options) = 13
    with django_assert_num_queries(13):
        _broadcast_payload_to_all_restricted_views(
            user, table.id, payload, field_id=visible_field.id
        )

    assert mock_broadcast_to_channel_group.delay.call_count == total_views

    mock_broadcast_to_channel_group.delay.reset_mock()

    # Now test with a hidden field — no broadcasts should be made, same query count.
    payload_hidden = {"type": "field_created", "field": {"id": hidden_field.id}}
    with django_assert_num_queries(13):
        _broadcast_payload_to_all_restricted_views(
            user, table.id, payload_hidden, field_id=hidden_field.id
        )

    assert mock_broadcast_to_channel_group.delay.call_count == 0


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_commenter_with_view_access_included_in_users_to_notify_for_comment(
    enterprise_data_fixture,
    premium_data_fixture,
    synced_roles,
):
    """
    Tests that get_users_to_notify_for_comment includes users who only have
    view-level COMMENTER access (NO_ACCESS at workspace level, COMMENTER on a
    restricted view) when they are subscribed to row comment notifications.
    """

    enterprise_data_fixture.enable_enterprise()

    owner = enterprise_data_fixture.create_user()
    view_commenter = premium_data_fixture.create_user(
        has_active_premium_license=True,
    )
    workspace = enterprise_data_fixture.create_workspace(
        user=owner, members=[view_commenter]
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)

    no_access_role = Role.objects.get(uid="NO_ACCESS")
    commenter_role = Role.objects.get(uid="COMMENTER")
    RoleAssignmentHandler().assign_role(
        view_commenter, workspace, role=no_access_role, scope=workspace
    )

    row = RowHandler().create_row(
        owner, table, values={f"field_{text_field.id}": "visible"}
    )

    view = premium_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=view, field=text_field, type="equal", value="visible"
    )

    RoleAssignmentHandler().assign_role(
        view_commenter,
        workspace,
        role=commenter_role,
        scope=View.objects.get(id=view.id),
    )

    # Subscribe the view_commenter to notifications on this row.
    RowCommentHandler.update_row_comments_notification_mode(
        view_commenter,
        table.id,
        row.id,
        RowCommentsNotificationModes.MODE_ALL_COMMENTS.value,
        skip_permission_check=True,
    )

    row_outside = RowHandler().create_row(
        owner, table, values={f"field_{text_field.id}": "hidden"}
    )

    # Also subscribe to notifications on the row outside the view's filters.
    RowCommentHandler.update_row_comments_notification_mode(
        view_commenter,
        table.id,
        row_outside.id,
        RowCommentsNotificationModes.MODE_ALL_COMMENTS.value,
        skip_permission_check=True,
    )

    message = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "owner comment"}],
            }
        ],
    }

    # The row is within the view's filters, so the view-level commenter should
    # be included in users to notify.
    row_comment = RowCommentHandler.create_comment(owner, table.id, row.id, message)
    users_to_notify = RowCommentHandler.get_users_to_notify_for_comment(row_comment)
    assert view_commenter in users_to_notify, (
        "A user with view-level COMMENTER access who is subscribed to row comment "
        "notifications should be included when the row is within the view's filters"
    )

    # The row is outside the view's filters, so the view-level commenter should
    # NOT be included because the row is not visible in any restricted view
    # they have access to.
    row_comment_outside = RowCommentHandler.create_comment(
        owner, table.id, row_outside.id, message
    )
    users_to_notify = RowCommentHandler.get_users_to_notify_for_comment(
        row_comment_outside
    )
    assert view_commenter not in users_to_notify, (
        "A user with view-level COMMENTER access should NOT be notified for "
        "comments on rows outside the view's filters"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_get_users_to_notify_for_comment_no_n_plus_one_queries(
    enterprise_data_fixture,
    premium_data_fixture,
    synced_roles,
):
    """
    Verifies that increasing the number of view-level commenters does not
    increase the number of database queries executed by
    get_users_to_notify_for_comment (no N+1 problem).
    """

    enterprise_data_fixture.enable_enterprise()

    owner = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=owner)
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)

    no_access_role = Role.objects.get(uid="NO_ACCESS")
    commenter_role = Role.objects.get(uid="COMMENTER")

    row = RowHandler().create_row(
        owner, table, values={f"field_{text_field.id}": "visible"}
    )

    view = premium_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=view, field=text_field, type="equal", value="visible"
    )

    message = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "test"}],
            }
        ],
    }
    row_comment = RowCommentHandler.create_comment(owner, table.id, row.id, message)

    def _create_commenter():
        user = premium_data_fixture.create_user(has_active_premium_license=True)
        enterprise_data_fixture.create_user_workspace(
            user=user, workspace=workspace, order=0
        )
        RoleAssignmentHandler().assign_role(
            user, workspace, role=no_access_role, scope=workspace
        )
        RoleAssignmentHandler().assign_role(
            user,
            workspace,
            role=commenter_role,
            scope=View.objects.get(id=view.id),
        )
        RowCommentHandler.update_row_comments_notification_mode(
            user,
            table.id,
            row.id,
            RowCommentsNotificationModes.MODE_ALL_COMMENTS.value,
            skip_permission_check=True,
        )
        return user

    # Create 2 commenters and measure query count.
    _create_commenter()
    _create_commenter()

    # Warm up caches with a first call.
    RowCommentHandler.get_users_to_notify_for_comment(row_comment)

    with CaptureQueriesContext(connection) as ctx_two:
        result_two = RowCommentHandler.get_users_to_notify_for_comment(row_comment)
    assert len(result_two) == 2

    # Create 3 more commenters (5 total) and measure again.
    _create_commenter()
    _create_commenter()
    _create_commenter()

    # Warm up caches again.
    RowCommentHandler.get_users_to_notify_for_comment(row_comment)

    with CaptureQueriesContext(connection) as ctx_five:
        result_five = RowCommentHandler.get_users_to_notify_for_comment(row_comment)
    assert len(result_five) == 5

    assert len(ctx_five) == len(ctx_two), (
        f"Query count should not grow with the number of users. "
        f"2 users: {len(ctx_two)} queries, 5 users: {len(ctx_five)} queries"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_editor_row_endpoints_exclude_hidden_fields_in_response(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    row = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "vis",
            f"field_{hidden_field.id}": "hid",
        },
    )

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
        scope=View.objects.get(id=view.id),
    )

    # GET single row - editor should not see hidden field.
    response = api_client.get(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row.id},
        )
        + f"?view={view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert f"field_{visible_field.id}" in response_json
    assert f"field_{hidden_field.id}" not in response_json

    # UPDATE single row - editor should not see hidden field in response.
    response = api_client.patch(
        reverse(
            "api:database:rows:item",
            kwargs={"table_id": table.id, "row_id": row.id},
        )
        + f"?view={view.id}",
        {f"field_{visible_field.id}": "updated"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert f"field_{visible_field.id}" in response_json
    assert response_json[f"field_{visible_field.id}"] == "updated"
    assert f"field_{hidden_field.id}" not in response_json

    # CREATE single row - editor should not see hidden field in response.
    response = api_client.post(
        reverse(
            "api:database:rows:list",
            kwargs={"table_id": table.id},
        )
        + f"?view={view.id}",
        {f"field_{visible_field.id}": "new_val"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert f"field_{visible_field.id}" in response_json
    assert f"field_{hidden_field.id}" not in response_json

    # BATCH CREATE rows - editor should not see hidden field in response.
    response = api_client.post(
        reverse(
            "api:database:rows:batch",
            kwargs={"table_id": table.id},
        )
        + f"?view={view.id}",
        {"items": [{f"field_{visible_field.id}": "batch_val1"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    row_data = response_json["items"][0]
    assert f"field_{visible_field.id}" in row_data
    assert f"field_{hidden_field.id}" not in row_data

    # BATCH UPDATE rows - editor should not see hidden field in response.
    response = api_client.patch(
        reverse(
            "api:database:rows:batch",
            kwargs={"table_id": table.id},
        )
        + f"?view={view.id}",
        {"items": [{"id": row.id, f"field_{visible_field.id}": "batch_updated"}]},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    row_data = response_json["items"][0]
    assert f"field_{visible_field.id}" in row_data
    assert row_data[f"field_{visible_field.id}"] == "batch_updated"
    assert f"field_{hidden_field.id}" not in row_data

    # GET ADJACENT row - editor should not see hidden field in response.
    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row.id},
        )
        + f"?view_id={view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert f"field_{visible_field.id}" in response_json
    assert f"field_{hidden_field.id}" not in response_json


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_editor_adjacent_row_requires_view_and_excludes_hidden_fields(
    api_client, enterprise_data_fixture
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    GridViewFieldOptions.objects.update_or_create(
        grid_view=view, field=hidden_field, defaults={"hidden": True}
    )

    row1 = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "row1_vis",
            f"field_{hidden_field.id}": "row1_hid",
        },
    )
    row2 = RowHandler().create_row(
        user,
        table,
        values={
            f"field_{visible_field.id}": "row2_vis",
            f"field_{hidden_field.id}": "row2_hid",
        },
    )

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
        scope=View.objects.get(id=view.id),
    )

    # Without view_id, the editor should NOT have access (no table-level perm).
    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row1.id},
        ),
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_401_UNAUTHORIZED

    # With view_id, the editor should have access and hidden fields excluded.
    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row1.id},
        )
        + f"?view_id={view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == HTTP_200_OK, response.json()
    response_json = response.json()
    assert f"field_{visible_field.id}" in response_json
    assert response_json[f"field_{visible_field.id}"] == "row2_vis"
    assert f"field_{hidden_field.id}" not in response_json

    # Builder should see hidden fields when using the same view.
    response = api_client.get(
        reverse(
            "api:database:rows:adjacent",
            kwargs={"table_id": table.id, "row_id": row1.id},
        )
        + f"?view_id={view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_200_OK
    response_json = response.json()
    assert f"field_{visible_field.id}" in response_json
    assert f"field_{hidden_field.id}" in response_json


@pytest.mark.django_db(transaction=True)
@patch("baserow.ws.registries.broadcast_to_channel_group")
def test_when_restricted_view_updated_force_view_refresh_is_broadcasted(
    mock_broadcast_to_channel_group,
    enterprise_data_fixture,
):
    enterprise_data_fixture.enable_enterprise()

    user = enterprise_data_fixture.create_user()
    table = enterprise_data_fixture.create_database_table(user=user)
    restricted_view = enterprise_data_fixture.create_grid_view(
        table=table,
        ownership_type=RestrictedViewOwnershipType.type,
    )

    mock_broadcast_to_channel_group.delay.reset_mock()

    ViewHandler().update_view(user=user, view=restricted_view, name="Updated name")

    restricted_channel = f"restricted-view-{restricted_view.id}"
    restricted_call = None
    for c in mock_broadcast_to_channel_group.delay.call_args_list:
        if c[0][0] == restricted_channel:
            restricted_call = c
            break
    assert restricted_call is not None, f"No broadcast to {restricted_channel} found"

    payload = restricted_call[0][1]
    assert payload["type"] == "force_view_refresh_and_default_values"
    assert payload["view_id"] == restricted_view.id


def _setup_default_values_test(enterprise_data_fixture):
    """
    Helper that creates a workspace with an admin (builder) and a second user,
    a table with a visible and a hidden field, a restricted view with hidden
    field configuration, and a default value on each field. Returns a dict with
    all the objects needed by the tests.
    """

    enterprise_data_fixture.enable_enterprise()

    admin, admin_token = enterprise_data_fixture.create_user_and_token()
    other_user, other_token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[other_user]
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)
    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )

    _set_field_hidden(view, hidden_field, visible_fields=[visible_field])

    ViewHandler().update_view_default_values(
        user=admin,
        view=view,
        items=[
            {
                "field": visible_field.id,
                "enabled": True,
                "value": "visible default",
            },
            {
                "field": hidden_field.id,
                "enabled": True,
                "value": "hidden default",
            },
        ],
    )

    return {
        "admin": admin,
        "admin_token": admin_token,
        "other_user": other_user,
        "other_token": other_token,
        "workspace": workspace,
        "table": table,
        "visible_field": visible_field,
        "hidden_field": hidden_field,
        "view": view,
    }


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_default_values_list_views_builder_sees_all(
    enterprise_data_fixture, api_client
):
    ctx = _setup_default_values_test(enterprise_data_fixture)

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": ctx["table"].id})
        + "?include=default_row_values",
        HTTP_AUTHORIZATION=f"JWT {ctx['admin_token']}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    view_data = next(v for v in data if v["id"] == ctx["view"].id)
    default_values = view_data["default_row_values"]
    field_ids = {dv["field"] for dv in default_values}
    assert ctx["visible_field"].id in field_ids
    assert ctx["hidden_field"].id in field_ids


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_default_values_list_views_editor_sees_visible_only(
    enterprise_data_fixture, api_client
):
    ctx = _setup_default_values_test(enterprise_data_fixture)

    no_access_role = Role.objects.get(uid="NO_ACCESS")
    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        ctx["other_user"],
        ctx["workspace"],
        role=no_access_role,
        scope=ctx["workspace"],
    )
    RoleAssignmentHandler().assign_role(
        ctx["other_user"],
        ctx["workspace"],
        role=editor_role,
        scope=View.objects.get(id=ctx["view"].id),
    )

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": ctx["table"].id})
        + "?include=default_row_values",
        HTTP_AUTHORIZATION=f"JWT {ctx['other_token']}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    view_data = next(v for v in data if v["id"] == ctx["view"].id)
    default_values = view_data["default_row_values"]
    field_ids = {dv["field"] for dv in default_values}
    assert ctx["visible_field"].id in field_ids
    assert ctx["hidden_field"].id not in field_ids


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_default_values_list_views_viewer_sees_none(
    enterprise_data_fixture, api_client
):
    ctx = _setup_default_values_test(enterprise_data_fixture)

    no_access_role = Role.objects.get(uid="NO_ACCESS")
    viewer_role = Role.objects.get(uid="VIEWER")
    RoleAssignmentHandler().assign_role(
        ctx["other_user"],
        ctx["workspace"],
        role=no_access_role,
        scope=ctx["workspace"],
    )
    RoleAssignmentHandler().assign_role(
        ctx["other_user"],
        ctx["workspace"],
        role=viewer_role,
        scope=View.objects.get(id=ctx["view"].id),
    )

    response = api_client.get(
        reverse("api:database:views:list", kwargs={"table_id": ctx["table"].id})
        + "?include=default_row_values",
        HTTP_AUTHORIZATION=f"JWT {ctx['other_token']}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    view_data = next(v for v in data if v["id"] == ctx["view"].id)
    default_values = view_data["default_row_values"]
    assert default_values == []


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_default_values_list_views_no_n_plus_one_queries(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    admin, admin_token = enterprise_data_fixture.create_user_and_token()
    editor_user, editor_token = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(
        user=admin, members=[editor_user]
    )
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    visible_field = enterprise_data_fixture.create_text_field(table=table, primary=True)
    hidden_field = enterprise_data_fixture.create_text_field(table=table)

    no_access_role = Role.objects.get(uid="NO_ACCESS")
    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        editor_user, workspace, role=no_access_role, scope=workspace
    )

    def _create_restricted_view_with_defaults():
        view = enterprise_data_fixture.create_grid_view(
            table=table, ownership_type=RestrictedViewOwnershipType.type
        )
        _set_field_hidden(view, hidden_field, visible_fields=[visible_field])
        ViewHandler().update_view_default_values(
            user=admin,
            view=view,
            items=[
                {"field": visible_field.id, "enabled": True, "value": "vis"},
                {"field": hidden_field.id, "enabled": True, "value": "hid"},
            ],
        )
        RoleAssignmentHandler().assign_role(
            editor_user,
            workspace,
            role=editor_role,
            scope=View.objects.get(id=view.id),
        )
        return view

    # Create one view and measure the query count.
    _create_restricted_view_with_defaults()

    url = (
        reverse("api:database:views:list", kwargs={"table_id": table.id})
        + "?include=default_row_values"
    )

    response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {editor_token}")
    assert response.status_code == HTTP_200_OK
    # Warm up caches (content types, etc.) by making the first request above.

    with CaptureQueriesContext(connection) as context_one_view:
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {editor_token}")
    assert response.status_code == HTTP_200_OK
    baseline_query_count = len(context_one_view)

    # Create two more views.
    _create_restricted_view_with_defaults()
    _create_restricted_view_with_defaults()

    with CaptureQueriesContext(connection) as context_three_views:
        response = api_client.get(url, HTTP_AUTHORIZATION=f"JWT {editor_token}")
    assert response.status_code == HTTP_200_OK
    three_views_query_count = len(context_three_views)

    # Verify all three views have filtered default values (only visible field).
    data = response.json()
    for view_data in data:
        default_values = view_data["default_row_values"]
        assert len(default_values) == 1
        assert default_values[0]["field"] == visible_field.id

    # The query count should be the same regardless of view count.
    assert three_views_query_count == baseline_query_count


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_default_values_get_view_editor_sees_visible_only(
    enterprise_data_fixture, api_client
):
    ctx = _setup_default_values_test(enterprise_data_fixture)

    no_access_role = Role.objects.get(uid="NO_ACCESS")
    editor_role = Role.objects.get(uid="EDITOR")
    RoleAssignmentHandler().assign_role(
        ctx["other_user"],
        ctx["workspace"],
        role=no_access_role,
        scope=ctx["workspace"],
    )
    RoleAssignmentHandler().assign_role(
        ctx["other_user"],
        ctx["workspace"],
        role=editor_role,
        scope=View.objects.get(id=ctx["view"].id),
    )

    response = api_client.get(
        reverse("api:database:views:item", kwargs={"view_id": ctx["view"].id})
        + "?include=default_row_values",
        HTTP_AUTHORIZATION=f"JWT {ctx['other_token']}",
    )
    assert response.status_code == HTTP_200_OK
    data = response.json()
    default_values = data["default_row_values"]
    field_ids = {dv["field"] for dv in default_values}
    assert ctx["visible_field"].id in field_ids
    assert ctx["hidden_field"].id not in field_ids


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_editor_with_view_access_can_list_rows_for_all_view_types(
    enterprise_data_fixture,
    premium_data_fixture,
    api_client,
):
    """
    Tests that a user who has NO_ACCESS at workspace level but EDITOR on a
    specific restricted view can still list rows through all view type
    endpoints via the view-level permission fallback.
    """

    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = enterprise_data_fixture.create_user_and_token()
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)

    editor_role = Role.objects.get(uid="EDITOR")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )

    RowHandler().create_row(user, table, values={f"field_{text_field.id}": "a"})

    for view_type in view_type_registry.get_all():
        if view_type.type not in view_type_url_mapping:
            continue

        view_path, fixture_create, response_path = view_type_url_mapping[view_type.type]

        view = getattr(premium_data_fixture, fixture_create)(
            table=table, ownership_type=RestrictedViewOwnershipType.type
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

        query_param = "?from_timestamp=2021-01-01&to_timestamp=2021-02-01"
        response = api_client.get(
            reverse(view_path, kwargs={"view_id": view.id}) + query_param,
            format="json",
            HTTP_AUTHORIZATION=f"JWT {token2}",
        )
        assert response.status_code == HTTP_200_OK, (
            f"Editor with view-level access should be able to list rows in "
            f"{view_type.type}"
        )
        response_json = response.json()
        rows = get_value_at_path(response_json, response_path)
        assert len(rows) == 1, f"Editor should see the row in {view_type.type}"


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_editor_with_view_access_can_comment_on_rows(
    enterprise_data_fixture,
    premium_data_fixture,
    api_client,
    synced_roles,
):
    """
    Tests that a user who has NO_ACCESS at workspace level but COMMENTER on a
    specific restricted view can create, read, update, and delete comments on
    rows that match the view's filters.
    """

    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    user2, token2 = premium_data_fixture.create_user_and_token(
        has_active_premium_license=True,
    )
    workspace = enterprise_data_fixture.create_workspace(user=user, members=[user2])
    database = enterprise_data_fixture.create_database_application(workspace=workspace)
    table = enterprise_data_fixture.create_database_table(database=database)
    text_field = enterprise_data_fixture.create_text_field(table=table, primary=True)

    commenter_role = Role.objects.get(uid="COMMENTER")
    no_access_role = Role.objects.get(uid="NO_ACCESS")
    RoleAssignmentHandler().assign_role(
        user2, workspace, role=no_access_role, scope=workspace
    )

    row = RowHandler().create_row(
        user, table, values={f"field_{text_field.id}": "visible"}
    )
    row_outside = RowHandler().create_row(
        user, table, values={f"field_{text_field.id}": "hidden"}
    )

    view = premium_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    enterprise_data_fixture.create_view_filter(
        view=view, field=text_field, type="equal", value="visible"
    )

    RoleAssignmentHandler().assign_role(
        user2,
        workspace,
        role=commenter_role,
        scope=View.objects.get(id=view.id),
    )

    # User2 can create a comment on a row that matches the view's filters.
    message = {
        "type": "doc",
        "content": [
            {"type": "paragraph", "content": [{"type": "text", "text": "test comment"}]}
        ],
    }
    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": row.id},
        )
        + f"?view={view.id}",
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == 200, (
        f"Commenter with view-level access should be able to create a comment: "
        f"{response.json()}"
    )
    comment_id = response.json()["id"]

    # User2 can read comments on the row.
    response = api_client.get(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": row.id},
        )
        + f"?view={view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == 200
    assert response.json()["count"] == 1

    # User2 can update their own comment.
    updated_message = {
        "type": "doc",
        "content": [
            {
                "type": "paragraph",
                "content": [{"type": "text", "text": "updated comment"}],
            }
        ],
    }
    response = api_client.patch(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment_id},
        )
        + f"?view={view.id}",
        {"message": updated_message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == 200

    # User2 can delete their own comment.
    response = api_client.delete(
        reverse(
            "api:premium:row_comments:item",
            kwargs={"table_id": table.id, "comment_id": comment_id},
        )
        + f"?view={view.id}",
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == 200

    # User2 can update notification mode on a row within the view's filters.
    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"table_id": table.id, "row_id": row.id},
        )
        + f"?view={view.id}",
        {"mode": "all"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code == 204, (
        f"Commenter with view-level access should be able to update notification "
        f"mode: {response.json() if response.status_code != 204 else ''}"
    )

    # User2 cannot update notification mode on a row outside the view's filters.
    response = api_client.put(
        reverse(
            "api:premium:row_comments:notification_mode",
            kwargs={"table_id": table.id, "row_id": row_outside.id},
        )
        + f"?view={view.id}",
        {"mode": "all"},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code != 204, (
        "Commenter should not be able to update notification mode on a row "
        "outside the view's filters"
    )

    # User2 cannot create a comment on a row outside the view's filters.
    response = api_client.post(
        reverse(
            "api:premium:row_comments:list",
            kwargs={"table_id": table.id, "row_id": row_outside.id},
        )
        + f"?view={view.id}",
        {"message": message},
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token2}",
    )
    assert response.status_code != 200, (
        "Commenter should not be able to comment on a row outside the view's filters"
    )


@pytest.mark.django_db
@override_settings(DEBUG=True)
def test_cannot_create_form_view_with_restricted_ownership_type(
    enterprise_data_fixture, api_client
):
    enterprise_data_fixture.enable_enterprise()

    user, token = enterprise_data_fixture.create_user_and_token()
    table = enterprise_data_fixture.create_database_table(user=user)

    response = api_client.post(
        reverse("api:database:views:list", kwargs={"table_id": table.id}),
        {
            "name": "Test Form",
            "type": "form",
            "ownership_type": "restricted",
        },
        format="json",
        HTTP_AUTHORIZATION=f"JWT {token}",
    )
    assert response.status_code == HTTP_400_BAD_REQUEST
    assert (
        response.json()["error"]
        == "ERROR_VIEW_OWNERSHIP_TYPE_INCOMPATIBLE_WITH_VIEW_TYPE"
    )
