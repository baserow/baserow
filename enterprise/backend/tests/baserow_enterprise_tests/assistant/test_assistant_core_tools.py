from uuid import uuid4

import pytest
from pydantic_ai import ModelRetry

from baserow.core.action.models import Action
from baserow.core.action.scopes import WorkspaceActionScopeType
from baserow.core.subjects import UserSubjectType
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.assistant.tools.builder.themes import (
    apply_theme,
    builder_uses_theme,
)
from baserow_enterprise.assistant.tools.core.tools import (
    create_builders,
    list_builders,
    update_builder,
)
from baserow_enterprise.assistant.tools.core.types import (
    BuilderItemCreate,
    BuilderUpdate,
)
from baserow_enterprise.audit_log.models import AuditLogEntry

from .utils import make_test_ctx


@pytest.mark.django_db
def test_list_builders_all(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(workspace=workspace, name="My DB")
    data_fixture.create_automation_application(
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

    assert "page=2" in result["_info"]
    assert len(result["database"]) == 20

    result = list_builders(ctx, builder_types=None, thought="list all", page=2)

    assert "_info" not in result
    assert [b["name"] for b in result["database"]] == [f"DB {i}" for i in range(20, 25)]


@pytest.mark.django_db
def test_list_builders_names_applications_with_kuma_types(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(workspace=workspace, name="App")

    ctx = make_test_ctx(user, workspace)
    result = list_builders(ctx, builder_types=["application"], thought="apps", size=5)

    assert result == {
        "application": [{"id": builder.id, "name": "App", "type": "application"}]
    }


@pytest.mark.django_db
def test_list_builders_leaves_out_applications_the_user_cannot_see(
    data_fixture, enable_enterprise, synced_roles
):
    from baserow_enterprise.role.handler import RoleAssignmentHandler
    from baserow_enterprise.role.models import Role

    admin = data_fixture.create_user()
    member = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=admin, members=[member])
    visible = data_fixture.create_database_application(
        workspace=workspace, name="Visible"
    )
    hidden = data_fixture.create_database_application(
        workspace=workspace, name="Hidden"
    )
    RoleAssignmentHandler().assign_role(
        member, workspace, role=Role.objects.get(uid="BUILDER")
    )
    RoleAssignmentHandler().assign_role(
        member,
        workspace,
        role=Role.objects.get(uid="NO_ACCESS"),
        scope=hidden.application_ptr,
    )

    result = list_builders(
        make_test_ctx(member, workspace), builder_types=None, thought="list all"
    )

    assert result == {
        "database": [{"id": visible.id, "name": "Visible", "type": "database"}]
    }


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
def test_create_builders_rejects_an_empty_request(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    with pytest.raises(ModelRetry, match="empty `builders`"):
        create_builders(
            make_test_ctx(user, workspace), builders=[], thought="create database"
        )


@pytest.mark.django_db
def test_create_builders_reuses_an_exact_existing_builder(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)
    builders = [BuilderItemCreate(name="Restaurant", type="database")]

    first = create_builders(ctx, builders=builders, thought="create db")
    second = create_builders(ctx, builders=builders, thought="continue setup")

    assert second["created_builders"] == []
    assert second["reused_builders"] == first["created_builders"]
    listed = list_builders(ctx, builder_types=["database"], thought="check dbs")
    assert [builder["name"] for builder in listed["database"]] == ["Restaurant"]


@pytest.mark.django_db
def test_create_builders_only_reuses_the_same_name_and_type(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    existing = data_fixture.create_database_application(
        workspace=workspace, name="Restaurant"
    )
    ctx = make_test_ctx(user, workspace)

    result = create_builders(
        ctx,
        builders=[
            BuilderItemCreate(name="Restaurant", type="database"),
            BuilderItemCreate(name="Kitchen", type="database"),
            BuilderItemCreate(name="Restaurant", type="automation"),
        ],
        thought="finish setup",
    )

    assert result["reused_builders"] == [
        {
            "id": existing.id,
            "name": "Restaurant",
            "type": "database",
            "theme": None,
        }
    ]
    assert {(item["name"], item["type"]) for item in result["created_builders"]} == {
        ("Kitchen", "database"),
        ("Restaurant", "automation"),
    }


@pytest.mark.django_db
def test_reused_application_requires_authorization_before_applying_theme(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    existing = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Restaurant"
    )
    apply_theme(existing, "baserow", user)
    ctx = make_test_ctx(user, workspace)

    result = create_builders(
        ctx,
        builders=[
            BuilderItemCreate(name="Restaurant", type="application", theme="eclipse")
        ],
        thought="create restaurant app",
    )

    assert result["unapplied_reused_builder_themes"] == [
        {
            "id": existing.id,
            "name": "Restaurant",
            "requested_theme": "eclipse",
        }
    ]
    existing.refresh_from_db()
    assert builder_uses_theme(existing, "baserow")
    steps = result["next_steps"]
    assert "ask_user" in steps
    assert "already authorized" in steps
    assert "then stop" in steps
    assert steps.index("ask_user") < steps.index("set_theme")
    assert "Only after that authorization" in steps


@pytest.mark.django_db
def test_reused_application_does_not_report_an_already_applied_theme(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    existing = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Restaurant"
    )
    apply_theme(existing, "eclipse", user)
    ctx = make_test_ctx(user, workspace)

    result = create_builders(
        ctx,
        builders=[
            BuilderItemCreate(name="Restaurant", type="application", theme="eclipse")
        ],
        thought="reuse restaurant app",
    )

    assert result["reused_builders"][0]["id"] == existing.id
    assert "unapplied_reused_builder_themes" not in result
    assert "next_steps" not in result


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
def test_create_builders_deduplicates_identical_requests(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)
    builder = BuilderItemCreate(name="Restaurant", type="database")

    result = create_builders(
        ctx, builders=[builder, builder], thought="create restaurant"
    )

    assert len(result["created_builders"]) == 1
    assert result["reused_builders"] == []


@pytest.mark.django_db
def test_create_builders_rejects_conflicting_requests(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)

    with pytest.raises(ModelRetry, match="Conflicting builder definitions"):
        create_builders(
            ctx,
            builders=[
                BuilderItemCreate(
                    name="Restaurant", type="application", theme="baserow"
                ),
                BuilderItemCreate(
                    name="Restaurant", type="application", theme="eclipse"
                ),
            ],
            thought="create restaurant",
        )


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


@pytest.mark.django_db
def test_update_builder_renames_an_application(data_fixture):
    message_group = uuid4()
    session_id = "assistant-session"
    user = data_fixture.create_user(session_id=session_id, action_group=message_group)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Old Name"
    )

    ctx = make_test_ctx(user, workspace)
    result = update_builder(
        ctx,
        builder_id=database.id,
        update=BuilderUpdate(name="New Name"),
        thought="rename",
    )

    assert result == {"id": database.id, "name": "New Name", "changed": True}
    database.refresh_from_db()
    assert database.name == "New Name"

    action = Action.objects.get(type="update_application")
    assert action.user_id == user.id
    assert action.workspace_id == workspace.id
    assert action.session == session_id
    assert action.action_group == message_group
    assert action.scope == WorkspaceActionScopeType.value(workspace.id)
    assert action.params["application_id"] == database.id
    assert action.params["original_application_name"] == "Old Name"
    assert action.params["application_name"] == "New Name"

    entry = AuditLogEntry.objects.get(action_type="update_application")
    assert entry.actor_id == user.id
    assert entry.actor_type == UserSubjectType.type
    assert entry.workspace_id == workspace.id
    assert entry.action_command_type == "DO"
    assert entry.action_params == action.params


@pytest.mark.django_db
def test_update_builder_sets_the_login_page(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Portal"
    )
    page = data_fixture.create_builder_page(
        builder=builder, name="Login", path="/login"
    )

    ctx = make_test_ctx(user, workspace)
    result = update_builder(
        ctx,
        builder_id=builder.id,
        update=BuilderUpdate(login_page_id=page.id),
        thought="set login page",
    )

    assert result["login_page_id"] == page.id
    builder.refresh_from_db()
    assert builder.login_page_id == page.id


@pytest.mark.django_db
def test_update_builder_with_nothing_to_change_is_a_no_op(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(
        workspace=workspace, name="Unchanged"
    )

    ctx = make_test_ctx(user, workspace)
    result = update_builder(
        ctx, builder_id=database.id, update=BuilderUpdate(), thought="no-op"
    )

    assert result["name"] == "Unchanged"
    assert result["changed"] is False
    database.refresh_from_db()
    assert database.name == "Unchanged"
    assert not Action.objects.filter(type="update_application").exists()
    assert not AuditLogEntry.objects.filter(action_type="update_application").exists()
