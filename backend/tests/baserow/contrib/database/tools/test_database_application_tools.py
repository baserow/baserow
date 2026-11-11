"""The shared tools that list, create and rename databases."""

import pydantic
import pytest

from baserow.contrib.automation.models import Automation
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database
from baserow.contrib.database.tools.databases import (
    create_database,
    list_databases,
    update_database,
)
from baserow.core.exceptions import ApplicationDoesNotExist, UserNotInWorkspace
from baserow.core.tools import ToolContext


@pytest.fixture
def ctx(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    return ToolContext(user=user, workspace=workspace)


@pytest.mark.django_db
def test_list_databases_only_lists_active_databases_of_the_workspace(ctx, data_fixture):
    sales = data_fixture.create_database_application(
        workspace=ctx.workspace, name="Sales"
    )
    data_fixture.create_database_application(
        workspace=ctx.workspace, name="Archived", trashed=True
    )
    data_fixture.create_database_application(user=ctx.user, name="Elsewhere")
    data_fixture.create_builder_application(workspace=ctx.workspace, name="Portal")
    data_fixture.create_automation_application(workspace=ctx.workspace, name="Flows")
    data_fixture.create_dashboard_application(workspace=ctx.workspace, name="KPIs")

    assert list_databases(ctx) == {
        "databases": [{"id": sales.id, "name": "Sales"}],
        "total": 1,
        "page": 1,
        "has_more": False,
    }


@pytest.mark.django_db
def test_list_databases_pages_in_sidebar_order(ctx, data_fixture):
    databases = [
        data_fixture.create_database_application(
            workspace=ctx.workspace, name=f"Database {order}", order=order
        )
        for order in (3, 1, 2)
    ]

    first = list_databases(ctx, page=1, size=2)
    last = list_databases(ctx, page=2, size=2)
    beyond_last = list_databases(ctx, page=3, size=2)

    assert first == {
        "databases": [
            {"id": database.id, "name": database.name} for database in databases[1:]
        ],
        "total": 3,
        "page": 1,
        "has_more": True,
    }
    assert last == {
        "databases": [{"id": databases[0].id, "name": databases[0].name}],
        "total": 3,
        "page": 2,
        "has_more": False,
    }
    assert beyond_last == {
        "databases": [],
        "total": 3,
        "page": 3,
        "has_more": False,
    }


@pytest.mark.django_db
def test_list_databases_hides_databases_from_a_nonmember(data_fixture):
    database = data_fixture.create_database_application()
    ctx = ToolContext(user=data_fixture.create_user(), workspace=database.workspace)

    assert list_databases(ctx) == {
        "databases": [],
        "total": 0,
        "page": 1,
        "has_more": False,
    }


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
