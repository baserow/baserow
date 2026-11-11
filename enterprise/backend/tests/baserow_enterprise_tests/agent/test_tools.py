from unittest.mock import AsyncMock, Mock

import pytest
from asgiref.sync import async_to_sync

from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.core.agents.service import AgentService
from baserow.core.tools import ToolContext


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
