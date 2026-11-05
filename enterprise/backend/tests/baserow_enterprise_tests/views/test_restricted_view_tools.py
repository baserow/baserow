"""Shared tools must not expose fields or rows hidden by restricted-view access."""

import pytest
from baserow_enterprise_tests.assistant.utils import make_test_ctx

from baserow.contrib.database.tools import rows, tables
from baserow.contrib.database.tools.view_config import RowColour, add_row_colours
from baserow.contrib.database.tools.views import (
    ViewFiltersArgs,
    create_view_filters,
    list_views,
)
from baserow.contrib.database.views.models import View, ViewFilter
from baserow.core.exceptions import PermissionDenied
from baserow.core.tools import ToolContext
from baserow_enterprise.assistant.tools.database import helpers
from baserow_enterprise.assistant.tools.database.tools import list_rows, load_row_tools
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role
from baserow_enterprise.view_ownership_types import RestrictedViewOwnershipType

BELOW_BUILDER = ["VIEWER", "COMMENTER", "EDITOR"]


@pytest.fixture(autouse=True)
def debug_licences(settings):
    # Enterprise licences only count in debug mode, so roles would be ignored.
    settings.DEBUG = True


def _restricted_view(fixture, role):
    fixture.enable_enterprise()
    admin = fixture.create_user()
    member = fixture.create_user()
    workspace = fixture.create_workspace(user=admin, members=[member])
    database = fixture.create_database_application(workspace=workspace)
    table = fixture.create_database_table(database=database)
    name = fixture.create_text_field(table=table, name="Name", primary=True)
    secret = fixture.create_text_field(table=table, name="Salary notes")
    view = fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    fixture.create_grid_view_field_option(view, secret, hidden=True)
    fixture.create_grid_view_field_option(view, name, hidden=False)
    fixture.create_view_filter(view=view, field=secret, type="equal", value="secret")
    fixture.create_view_filter_group(view=view)
    fixture.create_view_sort(view=view, field=secret, order="ASC")
    fixture.create_view_decoration(
        view=view,
        type="background_color",
        value_provider_type="conditional_color",
        value_provider_conf={
            "colors": [
                {
                    "id": "a",
                    "color": "red",
                    "operator": "AND",
                    "filters": [
                        {
                            "id": "b",
                            "field": secret.id,
                            "type": "equal",
                            "value": "secret",
                        }
                    ],
                }
            ]
        },
    )

    handler = RoleAssignmentHandler()
    handler.assign_role(
        member, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=workspace
    )
    handler.assign_role(
        member,
        workspace,
        role=Role.objects.get(uid=role),
        scope=View.objects.get(id=view.id),
    )
    return ToolContext(user=member, workspace=workspace), table, view, secret


@pytest.mark.django_db
@pytest.mark.parametrize("role", BELOW_BUILDER)
def test_list_views_leaves_out_what_a_restricted_view_hides(
    enterprise_data_fixture, role
):
    ctx, table, view, secret = _restricted_view(enterprise_data_fixture, role)

    listed = list_views(ctx, table.id)["views"]

    assert [item["id"] for item in listed] == [view.id]
    assert listed[0]["filters"] == []
    assert listed[0]["filter_groups"] == []
    assert listed[0]["sorts"] == []
    assert listed[0]["row_colours"] == []
    assert "hidden_field_ids" not in listed[0]


@pytest.mark.django_db
def test_list_views_shows_a_builder_all_of_a_restricted_view(enterprise_data_fixture):
    ctx, table, _, secret = _restricted_view(enterprise_data_fixture, "BUILDER")

    listed = list_views(ctx, table.id)["views"][0]

    assert [item["field_id"] for item in listed["filters"]] == [secret.id]
    assert len(listed["filter_groups"]) == 1
    assert [item["field_id"] for item in listed["sorts"]] == [secret.id]
    assert len(listed["row_colours"]) == 1
    assert listed["hidden_field_ids"] == [secret.id]


@pytest.mark.django_db
@pytest.mark.parametrize("role", BELOW_BUILDER)
def test_add_row_colours_denied_before_naming_a_hidden_field(
    enterprise_data_fixture, role
):
    ctx, _, view, secret = _restricted_view(enterprise_data_fixture, role)
    colour = RowColour(
        style="background_color", by="single_select_color", field_id=secret.id
    )

    with pytest.raises(PermissionDenied):
        add_row_colours(ctx, view.id, colour)


@pytest.mark.django_db
@pytest.mark.parametrize("role", BELOW_BUILDER)
@pytest.mark.parametrize("field_type", ["number", "missing"])
def test_create_view_filters_denied_before_naming_hidden_fields(
    enterprise_data_fixture, role, field_type
):
    ctx, _, view, secret = _restricted_view(enterprise_data_fixture, role)
    field_id = secret.id if field_type == "number" else 999999
    args = ViewFiltersArgs(
        view_id=view.id,
        filters=[
            {"field_id": field_id, "type": "number", "operator": "equal", "value": 1}
        ],
    )

    before = ViewFilter.objects.count()
    with pytest.raises(PermissionDenied):
        create_view_filters(ctx, [args])
    assert ViewFilter.objects.count() == before


@pytest.fixture
def restricted_view_member(enable_enterprise, enterprise_data_fixture):
    """
    A member whose only role is on a restricted view. The table is listed to them,
    but REST refuses its rows and fields.
    """

    admin = enterprise_data_fixture.create_user()
    member = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin, members=[member])
    table = enterprise_data_fixture.create_database_table(
        database=enterprise_data_fixture.create_database_application(
            workspace=workspace
        )
    )
    field = enterprise_data_fixture.create_text_field(
        table=table, name="Salary", primary=True
    )
    view = enterprise_data_fixture.create_grid_view(
        table=table, ownership_type=RestrictedViewOwnershipType.type
    )
    roles = RoleAssignmentHandler()
    roles.assign_role(
        member, workspace, role=Role.objects.get(uid="NO_ACCESS"), scope=workspace
    )
    roles.assign_role(
        member,
        workspace,
        role=Role.objects.get(uid="EDITOR"),
        scope=View.objects.get(id=view.id),
    )
    row = table.get_model().objects.create(**{field.db_column: "100"})
    return ToolContext(user=member, workspace=workspace), admin, table, row


@pytest.mark.django_db
def test_a_table_reached_through_a_view_is_listed_without_its_fields(
    restricted_view_member,
):
    ctx, _, table, _ = restricted_view_member

    assert [listed["id"] for listed in tables.list_tables(ctx)] == [table.id]
    assert tables.get_table_schema(ctx, [table.id]) == []


@pytest.mark.django_db
@pytest.mark.parametrize(
    "call",
    [
        pytest.param(
            lambda ctx, table, row: rows.list_table_rows(ctx, table.id), id="list"
        ),
        # An unknown field name would otherwise answer with the table's fields.
        pytest.param(
            lambda ctx, table, row: rows.create_rows(ctx, table.id, [{"Bonus": 1}]),
            id="create",
        ),
        pytest.param(
            lambda ctx, table, row: rows.update_rows(
                ctx, table.id, [rows.RowUpdate(id=row.id, Bonus=1)]
            ),
            id="update",
        ),
        pytest.param(
            lambda ctx, table, row: rows.delete_rows(ctx, table.id, [row.id]),
            id="delete",
        ),
    ],
)
def test_row_tools_refuse_a_table_reached_through_a_view(restricted_view_member, call):
    ctx, _, table, row = restricted_view_member

    with pytest.raises(PermissionDenied):
        call(ctx, table, row)


@pytest.mark.django_db
def test_kuma_refuses_rows_of_a_table_reached_through_a_view(restricted_view_member):
    ctx, _, table, _ = restricted_view_member
    kuma_ctx = make_test_ctx(ctx.user, ctx.workspace)

    with pytest.raises(PermissionDenied):
        list_rows(kuma_ctx, table.id, 0, 20, None, thought="Read rows")
    with pytest.raises(PermissionDenied):
        load_row_tools(
            kuma_ctx, [table.id], ["create", "update", "delete"], thought="Edit rows"
        )
    assert kuma_ctx.deps.dynamic_tools == []


@pytest.mark.django_db
def test_kuma_formulas_leave_out_tables_reached_through_a_view(
    restricted_view_member,
):
    ctx, admin, table, _ = restricted_view_member

    def readable(user):
        return helpers.readable_database_tables(user, ctx.workspace, table.database_id)

    assert readable(admin) == [table]
    assert readable(ctx.user) == []
