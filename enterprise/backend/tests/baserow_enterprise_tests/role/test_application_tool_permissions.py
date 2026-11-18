"""Application tools authorize unchanged requests as well as actual updates."""

import pytest

from baserow.contrib.automation.tools.automations import update_automation
from baserow.contrib.builder.tools.applications import update_builder
from baserow.contrib.dashboard.tools.dashboards import update_dashboard
from baserow.contrib.database.tools.databases import update_database
from baserow.core.action.models import Action
from baserow.core.exceptions import PermissionException
from baserow.core.identities.service import IdentityService
from baserow.core.signals import application_updated
from baserow.core.tools import ToolContext


@pytest.mark.django_db
@pytest.mark.parametrize(
    "application_type,update_tool",
    [
        ("database", update_database),
        ("automation", update_automation),
        ("dashboard", update_dashboard),
        ("builder", update_builder),
    ],
)
def test_application_updates_authorize_unchanged_requests(
    enterprise_data_fixture,
    enable_enterprise,
    synced_roles,
    mocker,
    application_type,
    update_tool,
):
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    application = getattr(
        enterprise_data_fixture, f"create_{application_type}_application"
    )(workspace=workspace, name="Original")
    signal = mocker.spy(application_updated, "send")
    ctx = ToolContext(user=admin, workspace=workspace)

    assert update_tool(ctx, application.id, name="Renamed")["changed"] is True
    signal.assert_called_once()
    signal.reset_mock()
    action_count = Action.objects.count()

    assert update_tool(ctx, application.id, name=" Renamed ")["changed"] is False
    assert Action.objects.count() == action_count
    signal.assert_not_called()

    identity = IdentityService().create_identity(
        admin, workspace, name="Reader", role_uid="VIEWER"
    )
    ctx = ToolContext(user=identity, workspace=workspace)
    for name in ("Renamed", "Another name"):
        with pytest.raises(PermissionException):
            update_tool(ctx, application.id, name=name)

    application.refresh_from_db()
    assert application.name == "Renamed"
    assert Action.objects.count() == action_count
    signal.assert_not_called()
