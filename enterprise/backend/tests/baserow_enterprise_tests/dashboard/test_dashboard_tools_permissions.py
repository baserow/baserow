import pytest

from baserow.contrib.dashboard.tools.dashboards import list_dashboards
from baserow.contrib.dashboard.tools.widgets import get_widget_data, list_widgets
from baserow.core.exceptions import PermissionException
from baserow.core.tools import ToolContext


@pytest.mark.django_db
def test_dashboard_tools_respect_no_access_on_the_dashboard(
    data_fixture, enable_enterprise, synced_roles
):
    from baserow_enterprise.role.handler import RoleAssignmentHandler
    from baserow_enterprise.role.models import Role

    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    hidden = data_fixture.create_dashboard_application(workspace=workspace)
    widget = data_fixture.create_summary_widget(dashboard=hidden)
    RoleAssignmentHandler().assign_role(
        member, workspace, role=Role.objects.get(uid="BUILDER")
    )
    RoleAssignmentHandler().assign_role(
        member,
        workspace,
        role=Role.objects.get(uid="NO_ACCESS"),
        scope=hidden.application_ptr,
    )
    ctx = ToolContext(user=member, workspace=workspace)

    assert list_dashboards(ctx) == {"dashboards": []}
    with pytest.raises(PermissionException):
        list_widgets(ctx, hidden.id)
    result = get_widget_data(ctx, [widget.id])
    assert result["widgets"] == []
    assert result["errors"][0]["widget_id"] == widget.id
