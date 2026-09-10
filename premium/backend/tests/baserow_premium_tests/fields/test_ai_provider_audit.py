import json
from io import StringIO

from django.core.management import call_command

import pytest


@pytest.mark.django_db
def test_audit_includes_only_the_requested_workspaces_ai_fields(premium_data_fixture):
    workspace = premium_data_fixture.create_workspace()
    database = premium_data_fixture.create_database_application(workspace=workspace)
    table = premium_data_fixture.create_database_table(database=database)
    field = premium_data_fixture.create_ai_field(
        table=table,
        ai_generative_ai_type="openai",
        ai_generative_ai_model="selected-model",
        ai_prompt="'private-field-prompt'",
    )
    premium_data_fixture.create_ai_field()
    output = StringIO()

    call_command("audit_ai_provider_settings", workspace_id=workspace.id, stdout=output)

    assert json.loads(output.getvalue())["ai_fields"] == [
        {
            "id": field.id,
            "trashed": False,
            "table_id": table.id,
            "table__database__workspace_id": workspace.id,
            "ai_generative_ai_type": "openai",
            "ai_generative_ai_model": "selected-model",
        }
    ]
    assert "private-field-prompt" not in output.getvalue()
