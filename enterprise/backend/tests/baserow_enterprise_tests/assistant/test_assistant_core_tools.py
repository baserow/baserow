import pytest

from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.assistant.tools.core.tools import (
    create_builders,
    list_builders,
)
from baserow_enterprise.assistant.tools.core.types import BuilderItemCreate

from .utils import make_test_ctx


@pytest.mark.django_db
def test_list_builders_all(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    db = data_fixture.create_database_application(workspace=workspace, name="My DB")
    automation = data_fixture.create_automation_application(
        workspace=workspace, name="My Automation"
    )

    ctx = make_test_ctx(user, workspace)
    result = list_builders(ctx, builder_types=None, thought="list all")

    assert "database" in result
    assert any(b["name"] == "My DB" for b in result["database"])
    assert "automation" in result
    assert any(b["name"] == "My Automation" for b in result["automation"])


@pytest.mark.django_db
def test_list_builders_filter_by_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace, name="DB 1")
    data_fixture.create_automation_application(workspace=workspace, name="Auto 1")

    ctx = make_test_ctx(user, workspace)
    result = list_builders(ctx, builder_types=["database"], thought="databases only")

    assert "database" in result
    assert "automation" not in result


@pytest.mark.django_db
def test_list_builders_empty(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    ctx = make_test_ctx(user, workspace)
    result = list_builders(ctx, builder_types=None, thought="list all")

    assert result == {}


@pytest.mark.django_db
def test_list_builders_truncation(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    for i in range(25):
        data_fixture.create_database_application(workspace=workspace, name=f"DB {i}")

    ctx = make_test_ctx(user, workspace)
    result = list_builders(ctx, builder_types=None, thought="list all")

    assert "_info" in result
    assert len(result["database"]) == 20


@pytest.mark.django_db
def test_create_builders_database(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    ctx = make_test_ctx(user, workspace)
    builders = [BuilderItemCreate(name="New Database", type="database")]
    result = create_builders(ctx, builders=builders, thought="create db")

    assert len(result["created_builders"]) == 1
    created = result["created_builders"][0]
    assert created["name"] == "New Database"
    assert created["type"] == "database"
    assert created["id"] == AnyInt()


@pytest.mark.django_db
def test_create_builders_multiple(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    ctx = make_test_ctx(user, workspace)
    builders = [
        BuilderItemCreate(name="DB One", type="database"),
        BuilderItemCreate(name="DB Two", type="database"),
    ]
    result = create_builders(ctx, builders=builders, thought="create two dbs")

    assert len(result["created_builders"]) == 2
    names = [b["name"] for b in result["created_builders"]]
    assert "DB One" in names
    assert "DB Two" in names


@pytest.mark.django_db
def test_create_application_applies_default_theme(data_fixture):
    """Creating an application should apply the default 'baserow' theme."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    ctx = make_test_ctx(user, workspace)
    builders = [BuilderItemCreate(name="My App", type="application")]
    result = create_builders(ctx, builders=builders, thought="create app")

    assert len(result["created_builders"]) == 1
    app_id = result["created_builders"][0]["id"]

    from baserow.contrib.builder.models import Builder

    builder = Builder.objects.get(id=app_id)
    # Baserow theme has primary_color="#4e5cfe"
    assert builder.colorthemeconfigblock.primary_color == "#4e5cfe"


@pytest.mark.django_db
def test_create_application_applies_eclipse_theme(data_fixture):
    """Creating an application with theme='eclipse' should apply the dark theme."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    ctx = make_test_ctx(user, workspace)
    builders = [
        BuilderItemCreate(name="Dashboard", type="application", theme="eclipse")
    ]
    result = create_builders(ctx, builders=builders, thought="create dark app")

    assert len(result["created_builders"]) == 1
    app_id = result["created_builders"][0]["id"]

    from baserow.contrib.builder.models import Builder

    builder = Builder.objects.get(id=app_id)
    # Eclipse theme should have different colors from baserow
    assert builder.colorthemeconfigblock.primary_color != "#4e5cfe"


@pytest.mark.django_db
def test_create_database_ignores_theme(data_fixture):
    """Creating a database should not fail even though databases have no theme."""

    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    ctx = make_test_ctx(user, workspace)
    builders = [BuilderItemCreate(name="My DB", type="database")]
    result = create_builders(ctx, builders=builders, thought="create db")

    assert len(result["created_builders"]) == 1
    assert result["created_builders"][0]["type"] == "database"
