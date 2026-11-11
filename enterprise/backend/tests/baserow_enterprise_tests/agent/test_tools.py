from unittest.mock import AsyncMock, Mock

import pytest
from asgiref.sync import async_to_sync

from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.database.models import Database
from baserow.core.agents.service import AgentService
from baserow.core.tools import ToolContext
from baserow_enterprise.role.handler import RoleAssignmentHandler
from baserow_enterprise.role.models import Role


@pytest.mark.django_db
def test_tool_calls_recheck_the_identity_role(
    enterprise_data_fixture, enable_enterprise, synced_roles, settings
):
    settings.BASEROW_USE_LOCAL_CACHE = True
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    table = enterprise_data_fixture.create_database_table(
        database=enterprise_data_fixture.create_database_application(
            workspace=workspace
        )
    )
    enterprise_data_fixture.create_text_field(table=table, name="Name", primary=True)
    service = AgentService()
    identity = service.create_agent(admin, workspace, name="Writer", role_uid="EDITOR")
    tool = agent_tool_type_registry.get("create_rows").get_tool(
        ToolContext(user=identity, workspace=workspace)
    )

    run = Mock(emit=AsyncMock())

    def create(name):
        arguments = tool.function_schema.validator.validate_python(
            {"table_id": table.id, "rows": [{"Name": name}]}
        )
        return async_to_sync(tool.function)(run, **arguments)

    assert create("Before downgrade").return_value[0]["Name"] == "Before downgrade"
    service.update_agent(admin, identity, role_uid="VIEWER")

    refused = create("After downgrade")
    assert refused.return_value == {
        "error": {
            "code": "permission_denied",
            "message": "You don't have permission to do this in this workspace.",
        }
    }
    assert refused.metadata == {"error_code": "permission_denied"}
    assert run.emit.await_args.args[0].input == {
        "values": {"table": table.name, "rows": [{"Name": "After downgrade"}]}
    }
    assert list(
        table.get_model(attribute_names=True).objects.values_list("name", flat=True)
    ) == ["Before downgrade"]


@pytest.mark.django_db
def test_list_databases_respects_the_identity_access_and_includes_empty_databases(
    enterprise_data_fixture, enable_enterprise, synced_roles, settings
):
    settings.BASEROW_USE_LOCAL_CACHE = True
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    empty = enterprise_data_fixture.create_database_application(
        workspace=workspace, name="Empty"
    )
    hidden = enterprise_data_fixture.create_database_application(
        workspace=workspace, name="Secret"
    )
    identity = AgentService().create_agent(
        admin, workspace, name="Reader", role_uid="VIEWER"
    )
    tool = agent_tool_type_registry.get("list_databases").get_tool(
        ToolContext(user=identity, workspace=workspace)
    )
    run = Mock(emit=AsyncMock())

    def list_databases():
        arguments = tool.function_schema.validator.validate_python({})
        return async_to_sync(tool.function)(run, **arguments).return_value

    assert {database["id"] for database in list_databases()["databases"]} == {
        empty.id,
        hidden.id,
    }
    RoleAssignmentHandler().assign_role(
        identity,
        workspace,
        Role.objects.get(uid="NO_ACCESS"),
        scope=hidden.application_ptr,
    )

    assert list_databases() == {
        "databases": [{"id": empty.id, "name": "Empty"}],
        "total": 1,
        "page": 1,
        "has_more": False,
    }
    assert not empty.table_set.exists()


@pytest.mark.django_db
def test_database_writes_recheck_the_identity_role(
    enterprise_data_fixture, enable_enterprise, synced_roles, settings
):
    settings.BASEROW_USE_LOCAL_CACHE = True
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    service = AgentService()
    identity = service.create_agent(
        admin, workspace, name="Builder", role_uid="BUILDER"
    )
    ctx = ToolContext(user=identity, workspace=workspace)
    tools = {
        name: agent_tool_type_registry.get(name).get_tool(ctx)
        for name in ("create_database", "update_database")
    }
    run = Mock(emit=AsyncMock())

    def call(tool_name, **arguments):
        tool = tools[tool_name]
        arguments = tool.function_schema.validator.validate_python(arguments)
        return async_to_sync(tool.function)(run, **arguments)

    created = call("create_database", name="Sales").return_value
    database = Database.objects.get(id=created["created_database"]["id"])
    assert database.workspace_id == workspace.id
    assert database.name == "Sales"
    renamed = call(
        "update_database", database_id=database.id, name="Sales renamed"
    ).return_value
    assert renamed == {
        "updated_database": {"id": database.id, "name": "Sales renamed"},
        "changed": True,
    }
    database.refresh_from_db()
    assert database.name == "Sales renamed"

    service.update_agent(admin, identity, role_uid="VIEWER")

    for name, arguments in (
        ("create_database", {"name": "After downgrade"}),
        (
            "update_database",
            {"database_id": database.id, "name": "After downgrade"},
        ),
    ):
        refused = call(name, **arguments)
        assert refused.return_value["error"]["code"] == "permission_denied"
        assert refused.metadata == {"error_code": "permission_denied"}

    assert list(
        Database.objects.filter(workspace=workspace).values_list("name", flat=True)
    ) == ["Sales renamed"]


@pytest.mark.django_db
def test_database_rename_preview_keeps_a_hidden_database_id(
    enterprise_data_fixture, enable_enterprise, synced_roles
):
    admin = enterprise_data_fixture.create_user()
    workspace = enterprise_data_fixture.create_workspace(user=admin)
    hidden = enterprise_data_fixture.create_database_application(
        workspace=workspace, name="Secret"
    )
    identity = AgentService().create_agent(
        admin, workspace, name="Builder", role_uid="BUILDER"
    )
    RoleAssignmentHandler().assign_role(
        identity,
        workspace,
        Role.objects.get(uid="NO_ACCESS"),
        scope=hidden.application_ptr,
    )
    tool = agent_tool_type_registry.get("update_database").get_tool(
        ToolContext(user=identity, workspace=workspace)
    )
    run = Mock(emit=AsyncMock())
    arguments = tool.function_schema.validator.validate_python(
        {"database_id": hidden.id, "name": "New name"}
    )

    refused = async_to_sync(tool.function)(run, **arguments)

    assert refused.return_value["error"]["code"] == "not_found"
    assert run.emit.await_args.args[0].input == {
        "values": {"database_id": hidden.id, "name": "New name"}
    }
    hidden.refresh_from_db()
    assert hidden.name == "Secret"
