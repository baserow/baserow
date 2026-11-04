"""The shared view tools must not show or name what a restricted view hides."""

import pytest

from baserow.contrib.database.tools.view_config import RowColour, set_row_colours
from baserow.contrib.database.tools.views import (
    ViewFiltersArgs,
    create_view_filters,
    list_views,
)
from baserow.contrib.database.views.models import View, ViewFilter
from baserow.core.exceptions import PermissionDenied
from baserow.core.tools import ToolContext
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
def test_set_row_colours_denied_before_naming_a_hidden_field(
    enterprise_data_fixture, role
):
    ctx, _, view, secret = _restricted_view(enterprise_data_fixture, role)
    colour = RowColour(
        style="background_color", by="single_select_color", field_id=secret.id
    )

    with pytest.raises(PermissionDenied):
        set_row_colours(ctx, view.id, colour)


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
