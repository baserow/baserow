"""The shared tools that create and rename automations."""

import pydantic
import pytest

from baserow.contrib.automation.models import Automation
from baserow.contrib.automation.tools.automations import (
    create_automation,
    update_automation,
)
from baserow.contrib.automation.workflows.models import AutomationWorkflow
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database
from baserow.core.exceptions import ApplicationDoesNotExist, UserNotInWorkspace
from baserow.core.integrations.models import Integration
from baserow.core.tools import ToolContext


@pytest.fixture
def ctx(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    return ToolContext(user=user, workspace=workspace)


@pytest.mark.django_db
def test_create_automation_creates_the_automation_and_its_integration(ctx):
    result = create_automation(ctx, "Flows")

    automation = Automation.objects.get(id=result["created_automation"]["id"])
    assert result == {"created_automation": {"id": automation.id, "name": "Flows"}}
    assert automation.workspace_id == ctx.workspace.id
    assert not AutomationWorkflow.objects.exists()
    (integration,) = Integration.objects.filter(application=automation)
    assert integration.get_type().type == "local_baserow"
    assert not Database.objects.exists()
    assert not Builder.objects.exists()
    assert not Dashboard.objects.exists()


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["", "x" * 161])
def test_create_automation_rejects_an_invalid_name(ctx, name):
    with pytest.raises(pydantic.ValidationError):
        create_automation(ctx, name)

    assert not Automation.objects.exists()


@pytest.mark.django_db
def test_create_automation_keeps_nothing_when_denied(data_fixture):
    workspace = data_fixture.create_workspace()
    ctx = ToolContext(user=data_fixture.create_user(), workspace=workspace)

    with pytest.raises(UserNotInWorkspace):
        create_automation(ctx, "Flows")

    assert not Automation.objects.exists()
    assert not Integration.objects.exists()


@pytest.mark.django_db
def test_update_automation_renames_it(ctx, data_fixture):
    automation = data_fixture.create_automation_application(
        workspace=ctx.workspace, name="Old"
    )

    result = update_automation(ctx, automation.id, "New")

    assert result == {
        "updated_automation": {"id": automation.id, "name": "New"},
        "changed": True,
    }
    automation.refresh_from_db()
    assert automation.name == "New"


@pytest.mark.django_db
def test_update_automation_with_the_same_name_reports_no_change(ctx, data_fixture):
    automation = data_fixture.create_automation_application(
        workspace=ctx.workspace, name="Same"
    )

    result = update_automation(ctx, automation.id, "Same")

    assert result["changed"] is False


@pytest.mark.django_db
def test_update_automation_refuses_another_application_type(ctx, data_fixture):
    database = data_fixture.create_database_application(
        workspace=ctx.workspace, name="Sales"
    )

    with pytest.raises(ApplicationDoesNotExist):
        update_automation(ctx, database.id, "New")

    database.refresh_from_db()
    assert database.name == "Sales"
