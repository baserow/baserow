"""The shared tools that create and rename databases."""

import pydantic
import pytest

from baserow.contrib.automation.models import Automation
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database
from baserow.contrib.database.tools.databases import create_database, update_database
from baserow.core.exceptions import ApplicationDoesNotExist, UserNotInWorkspace
from baserow.core.tools import ToolContext


@pytest.fixture
def ctx(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    return ToolContext(user=user, workspace=workspace)


@pytest.mark.django_db
def test_create_database_creates_only_a_database(ctx):
    result = create_database(ctx, "Sales")

    database = Database.objects.get(id=result["created_database"]["id"])
    assert result == {"created_database": {"id": database.id, "name": "Sales"}}
    assert database.workspace_id == ctx.workspace.id
    assert not Automation.objects.exists()
    assert not Builder.objects.exists()
    assert not Dashboard.objects.exists()


@pytest.mark.django_db
def test_create_database_keeps_nothing_when_denied(data_fixture):
    workspace = data_fixture.create_workspace()
    ctx = ToolContext(user=data_fixture.create_user(), workspace=workspace)

    with pytest.raises(UserNotInWorkspace):
        create_database(ctx, "Sales")

    assert not Database.objects.exists()


@pytest.mark.django_db
def test_update_database_renames_it(ctx, data_fixture):
    database = data_fixture.create_database_application(
        workspace=ctx.workspace, name="Old"
    )

    result = update_database(ctx, database.id, "New")

    assert result == {
        "updated_database": {"id": database.id, "name": "New"},
        "changed": True,
    }
    database.refresh_from_db()
    assert database.name == "New"


@pytest.mark.django_db
@pytest.mark.parametrize("name", ["", "x" * 161])
def test_update_database_rejects_an_invalid_name(ctx, data_fixture, name):
    database = data_fixture.create_database_application(
        workspace=ctx.workspace, name="Old"
    )

    with pytest.raises(pydantic.ValidationError):
        update_database(ctx, database.id, name)

    database.refresh_from_db()
    assert database.name == "Old"


@pytest.mark.django_db
def test_update_database_refuses_another_application_type(ctx, data_fixture):
    automation = data_fixture.create_automation_application(
        workspace=ctx.workspace, name="Flows"
    )

    with pytest.raises(ApplicationDoesNotExist):
        update_database(ctx, automation.id, "New")

    automation.refresh_from_db()
    assert automation.name == "Flows"


@pytest.mark.django_db
def test_update_database_refuses_another_workspace(ctx, data_fixture):
    other = data_fixture.create_database_application(
        workspace=data_fixture.create_workspace(user=ctx.user), name="Other"
    )

    with pytest.raises(ApplicationDoesNotExist):
        update_database(ctx, other.id, "New")

    other.refresh_from_db()
    assert other.name == "Other"
