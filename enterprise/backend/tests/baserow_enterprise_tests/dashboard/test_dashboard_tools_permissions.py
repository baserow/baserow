import pytest

from baserow.contrib.dashboard.tools.dashboards import list_dashboards
from baserow.contrib.dashboard.tools.widgets import (
    create_widgets,
    delete_widgets,
    get_widget_data,
    list_widgets,
    update_widgets,
)
from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.tools import ToolContext

NOT_FOUND = "Not found in this workspace."


def _workspace_with_role(data_fixture, uid):
    from baserow_enterprise.role.handler import RoleAssignmentHandler
    from baserow_enterprise.role.models import Role

    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    data_fixture.create_local_baserow_integration(
        application=dashboard, authorized_user=admin
    )
    widget = data_fixture.create_summary_widget(dashboard=dashboard)
    RoleAssignmentHandler().assign_role(
        member, workspace, role=Role.objects.get(uid=uid)
    )
    return ToolContext(user=member, workspace=workspace), dashboard, widget


@pytest.mark.django_db
def test_hidden_dashboard_and_widget_are_not_found(
    data_fixture, enable_enterprise, synced_roles
):
    from baserow_enterprise.role.handler import RoleAssignmentHandler
    from baserow_enterprise.role.models import Role

    ctx, dashboard, widget = _workspace_with_role(data_fixture, "BUILDER")
    RoleAssignmentHandler().assign_role(
        ctx.user,
        ctx.workspace,
        role=Role.objects.get(uid="NO_ACCESS"),
        scope=dashboard.application_ptr,
    )

    assert list_dashboards(ctx) == {"dashboards": []}
    with pytest.raises(ApplicationDoesNotExist):
        list_widgets(ctx, dashboard.id)
    assert get_widget_data(ctx, [widget.id])["errors"] == [
        {"widget_id": widget.id, "error": NOT_FOUND}
    ]
    assert update_widgets(ctx, [{"widget_id": widget.id, "title": "New"}])[
        "errors"
    ] == [{"index": 0, "widget_id": widget.id, "error": NOT_FOUND}]
    assert delete_widgets(ctx, [widget.id])["errors"] == [
        {"widget_id": widget.id, "error": NOT_FOUND}
    ]


@pytest.mark.django_db
def test_viewer_cannot_change_widgets(data_fixture, enable_enterprise, synced_roles):
    ctx, dashboard, widget = _workspace_with_role(data_fixture, "VIEWER")
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    amount = data_fixture.create_number_field(table=table, name="Amount")

    # A viewer may read the dashboard, so the call fails as a whole, as for the
    # other write tools.
    with pytest.raises(PermissionException):
        create_widgets(
            ctx,
            dashboard.id,
            [
                {
                    "type": "summary",
                    "title": "Total",
                    "table_id": table.id,
                    "field_id": amount.id,
                    "aggregation_type": "sum",
                }
            ],
        )
    with pytest.raises(PermissionException):
        update_widgets(ctx, [{"widget_id": widget.id, "title": "New"}])
    with pytest.raises(PermissionException):
        delete_widgets(ctx, [widget.id])


@pytest.mark.django_db
def test_a_refused_write_keeps_nothing_of_the_batch(
    data_fixture, enable_enterprise, synced_roles
):
    from baserow.contrib.dashboard.widgets.models import Widget
    from baserow_enterprise.role.handler import RoleAssignmentHandler
    from baserow_enterprise.role.models import Role

    ctx, editable, widget = _workspace_with_role(data_fixture, "BUILDER")
    viewable = data_fixture.create_dashboard_application(workspace=ctx.workspace)
    other = data_fixture.create_summary_widget(dashboard=viewable)
    RoleAssignmentHandler().assign_role(
        ctx.user,
        ctx.workspace,
        role=Role.objects.get(uid="VIEWER"),
        scope=viewable.application_ptr,
    )

    with pytest.raises(PermissionException):
        update_widgets(
            ctx,
            [
                {"widget_id": widget.id, "title": "Changed"},
                {"widget_id": other.id, "title": "Changed"},
            ],
        )
    with pytest.raises(PermissionException):
        delete_widgets(ctx, [widget.id, other.id])

    widget.refresh_from_db()
    assert widget.title != "Changed"
    assert not Widget.objects_and_trash.get(id=widget.id).trashed


@pytest.mark.django_db
def test_personal_view_of_another_user_is_not_found(
    data_fixture, enable_enterprise, synced_roles
):
    from baserow.contrib.database.views.handler import ViewHandler

    ctx, dashboard, _ = _workspace_with_role(data_fixture, "BUILDER")
    admin = ctx.workspace.workspaceuser_set.exclude(user=ctx.user).get().user
    database = data_fixture.create_database_application(workspace=ctx.workspace)
    table = data_fixture.create_database_table(database=database)
    amount = data_fixture.create_number_field(table=table, name="Amount")
    personal = ViewHandler().create_view(
        user=admin,
        table=table,
        type_name="grid",
        name="Mine",
        ownership_type="personal",
    )

    result = create_widgets(
        ctx,
        dashboard.id,
        [
            {
                "type": "summary",
                "title": "Total",
                "table_id": table.id,
                "view_id": personal.id,
                "field_id": amount.id,
                "aggregation_type": "sum",
            }
        ],
    )

    assert result["created"] == []
    assert result["errors"] == [
        {"index": 0, "error": f"View {personal.id} not found in this workspace."}
    ]
