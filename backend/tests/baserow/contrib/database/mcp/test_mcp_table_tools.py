import json

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key


@pytest.mark.django_db
def test_call_tool_list_tables(data_fixture):
    user = data_fixture.create_user()
    workspace_1 = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(user=user, workspace=workspace_1)

    database_1 = data_fixture.create_database_application(workspace=workspace_1)
    database_2 = data_fixture.create_database_application(workspace=workspace_1)
    database_3 = data_fixture.create_database_application()

    table_1 = data_fixture.create_database_table(database=database_1)
    table_2 = data_fixture.create_database_table(database=database_2)

    # Should not be in the result because the table is in a different workspace.
    table_3 = data_fixture.create_database_table(database=database_3)

    mcp = BaserowMCPServer()

    key_token = current_key.set(endpoint.key)

    try:

        async def inner():
            async with client_session(mcp._mcp_server) as client:
                result = await client.call_tool("list_tables", {})
                json_result = json.loads(result.content[0].text)
                assert json_result == [
                    {
                        "id": table_1.id,
                        "name": table_1.name,
                        "order": table_1.order,
                        "database_id": table_1.database_id,
                    },
                    {
                        "id": table_2.id,
                        "name": table_2.name,
                        "order": table_2.order,
                        "database_id": table_2.database_id,
                    },
                ]

        with transaction.atomic():
            async_to_sync(inner)()
    finally:
        current_key.reset(key_token)
