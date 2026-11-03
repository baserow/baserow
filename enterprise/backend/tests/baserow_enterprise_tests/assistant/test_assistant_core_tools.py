import pytest

from baserow.contrib.automation.models import Automation
from baserow.contrib.builder.models import Builder
from baserow.contrib.dashboard.models import Dashboard
from baserow.contrib.database.models import Database
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.integrations.models import Integration
from baserow.core.models import Application
from baserow.test_utils.helpers import AnyInt
from baserow_enterprise.assistant.tools.core.tools import (
    create_automation,
    create_builder,
    create_dashboard,
    create_database,
    list_builders,
    update_automation,
    update_builder,
    update_dashboard,
    update_database,
)
from baserow_enterprise.assistant.tools.shared import ToolInputError
from baserow_enterprise.builder.tools.themes import (
    apply_theme,
    builder_uses_theme,
)

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
@pytest.mark.parametrize(
    "tool,model,kuma_type",
    [
        (create_database, Database, "database"),
        (create_automation, Automation, "automation"),
        (create_dashboard, Dashboard, "dashboard"),
        (create_builder, Builder, "application"),
    ],
)
def test_create_tool_creates_only_its_type(data_fixture, tool, model, kuma_type):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    result = tool(make_test_ctx(user, workspace), name="Thing", thought="create")

    (created,) = result["created_builders"]
    assert created == {"id": AnyInt(), "name": "Thing", "type": kuma_type}
    assert result["reused_builders"] == []
    assert model.objects.get(id=created["id"]).workspace_id == workspace.id
    assert Application.objects.filter(workspace=workspace).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool",
    [create_database, create_automation, create_dashboard, create_builder],
)
def test_create_tool_reuses_an_exact_match(data_fixture, tool):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    ctx = make_test_ctx(user, workspace)

    first = tool(ctx, name="Restaurant", thought="create")
    second = tool(ctx, name="Restaurant", thought="continue setup")

    assert second["created_builders"] == []
    assert second["reused_builders"] == first["created_builders"]
    assert Application.objects.filter(workspace=workspace).count() == 1


@pytest.mark.django_db
def test_create_tool_creates_when_the_name_or_type_differs(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    existing = data_fixture.create_database_application(
        workspace=workspace, name="Restaurant"
    )
    ctx = make_test_ctx(user, workspace)

    other_name = create_database(ctx, name="Kitchen", thought="create")
    other_type = create_automation(ctx, name="Restaurant", thought="create")

    assert other_name["reused_builders"] == []
    assert other_name["created_builders"][0]["type"] == "database"
    assert other_type["reused_builders"] == []
    assert other_type["created_builders"][0]["type"] == "automation"
    assert other_type["created_builders"][0]["id"] != existing.id


@pytest.mark.django_db
def test_create_tool_does_not_reuse_an_application_of_another_workspace(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    data_fixture.create_database_application(
        workspace=data_fixture.create_workspace(user=user), name="Restaurant"
    )

    result = create_database(
        make_test_ctx(user, workspace), name="Restaurant", thought="create"
    )

    assert result["reused_builders"] == []
    assert len(result["created_builders"]) == 1


@pytest.mark.django_db
def test_create_tool_keeps_nothing_when_denied(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace()

    with pytest.raises(UserNotInWorkspace):
        create_database(make_test_ctx(user, workspace), name="Sales", thought="create")

    assert not Database.objects.exists()


@pytest.mark.django_db
def test_create_automation_adds_no_integration(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    result = create_automation(
        make_test_ctx(user, workspace), name="Flows", thought="create"
    )

    assert not Integration.objects.filter(
        application_id=result["created_builders"][0]["id"]
    ).exists()


@pytest.mark.django_db
def test_reused_application_requires_authorization_before_applying_theme(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    existing = data_fixture.create_builder_application(
        user=user, workspace=workspace, name="Restaurant"
    )
    apply_theme(existing, "baserow", user)
    ctx = make_test_ctx(user, workspace)

    result = create_builder(
        ctx, name="Restaurant", theme="eclipse", thought="create restaurant app"
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

    result = create_builder(
        ctx, name="Restaurant", theme="eclipse", thought="reuse restaurant app"
    )

    assert result["reused_builders"][0]["id"] == existing.id
    assert "unapplied_reused_builder_themes" not in result
    assert "next_steps" not in result


@pytest.mark.django_db
def test_create_builder_applies_default_theme(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    result = create_builder(
        make_test_ctx(user, workspace), name="My App", thought="create app"
    )

    builder = Builder.objects.get(id=result["created_builders"][0]["id"])
    assert builder_uses_theme(builder, "baserow")
    assert Integration.objects.filter(application=builder).count() == 1


@pytest.mark.django_db
def test_create_builder_applies_eclipse_theme(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)

    result = create_builder(
        make_test_ctx(user, workspace),
        name="Dashboard",
        theme="eclipse",
        thought="create dark app",
    )

    builder = Builder.objects.get(id=result["created_builders"][0]["id"])
    assert builder_uses_theme(builder, "eclipse")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,id_argument,make",
    [
        (update_database, "database_id", "create_database_application"),
        (update_automation, "automation_id", "create_automation_application"),
        (update_dashboard, "dashboard_id", "create_dashboard_application"),
        (update_builder, "builder_id", "create_builder_application"),
    ],
)
def test_update_tool_renames_its_type(data_fixture, tool, id_argument, make):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    application = getattr(data_fixture, make)(workspace=workspace, name="Old Name")
    ctx = make_test_ctx(user, workspace)

    result = tool(
        ctx, **{id_argument: application.id}, name="New Name", thought="rename"
    )

    assert result["id"] == application.id
    assert result["name"] == "New Name"
    assert result["changed"] is True
    application.refresh_from_db()
    assert application.name == "New Name"

    again = tool(
        ctx, **{id_argument: application.id}, name="New Name", thought="rename"
    )
    assert again["changed"] is False


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,id_argument,make",
    [
        (update_database, "database_id", "create_automation_application"),
        (update_automation, "automation_id", "create_dashboard_application"),
        (update_dashboard, "dashboard_id", "create_builder_application"),
        (update_builder, "builder_id", "create_database_application"),
    ],
)
def test_update_tool_refuses_another_type(data_fixture, tool, id_argument, make):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    other = getattr(data_fixture, make)(workspace=workspace, name="Other")

    with pytest.raises(ToolInputError, match=f"with ID {other.id} not found"):
        tool(
            make_test_ctx(user, workspace),
            **{id_argument: other.id},
            name="New Name",
            thought="rename",
        )

    other.refresh_from_db()
    assert other.name == "Other"


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
        login_page_id=page.id,
        thought="set login page",
    )

    assert result["login_page_id"] == page.id
    builder.refresh_from_db()
    assert builder.login_page_id == page.id


@pytest.mark.django_db
def test_update_builder_with_nothing_to_change_is_a_no_op(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    builder = data_fixture.create_builder_application(
        workspace=workspace, name="Unchanged"
    )

    result = update_builder(
        make_test_ctx(user, workspace), builder_id=builder.id, thought="no-op"
    )

    assert result["name"] == "Unchanged"
    assert result["changed"] is False
    builder.refresh_from_db()
    assert builder.name == "Unchanged"
