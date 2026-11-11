import asyncio
import json
import threading
from dataclasses import dataclass
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from django.db import OperationalError
from django.urls import reverse

import pytest
from asgiref.sync import async_to_sync
from freezegun import freeze_time
from pydantic_ai import ToolReturn

from baserow.contrib.agent.database_previews import table_reference
from baserow.contrib.agent.previews import StepPreview
from baserow.contrib.agent.registries import AgentToolType, agent_tool_type_registry
from baserow.contrib.database.views.models import FormView
from baserow.core.chat_runs.steps import ToolCallInputEvent
from baserow.core.chat_runs.tool_input import MAX_INPUT_PREVIEW_SIZE
from baserow.core.models import Agent
from baserow.core.notifications.models import NotificationRecipient
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import (
    ToolErrorCode,
    ToolInputError,
)

# Whether each tool changes data, and arguments it succeeds with on workspace_data.
TOOLS = {
    "list_databases": (False, lambda s: {}),
    "create_database": (True, lambda s: {"name": "Projects"}),
    "update_database": (
        True,
        lambda s: {"database_id": s.table.database_id, "name": "Projects"},
    ),
    "list_tables": (False, lambda s: {}),
    "get_table_schema": (False, lambda s: {"table_ids": [s.table.id]}),
    "list_table_rows": (False, lambda s: {"table_id": s.table.id}),
    "list_views": (False, lambda s: {"table_id": s.table.id}),
    "create_tables": (
        True,
        lambda s: {
            "database_id": s.table.database_id,
            "tables": [
                {"name": "Projects", "primary_field_name": "Title", "fields": []}
            ],
        },
    ),
    "create_fields": (
        True,
        lambda s: {
            "table_id": s.table.id,
            "fields": [{"name": "Notes", "type": "text"}],
        },
    ),
    "update_fields": (
        True,
        lambda s: {"fields": [{"field_id": s.hours.id, "name": "Effort"}]},
    ),
    "delete_fields": (True, lambda s: {"field_ids": [s.hours.id]}),
    "create_views": (
        True,
        lambda s: {
            "table_id": s.table.id,
            "views": [{"name": "Board", "type": "grid"}],
        },
    ),
    "create_view_filters": (
        True,
        lambda s: {
            "view_filters": [
                {
                    "view_id": s.view.id,
                    "filters": [
                        {
                            "field_id": s.hours.id,
                            "type": "number",
                            "operator": "higher_than",
                            "value": 1,
                        }
                    ],
                }
            ]
        },
    ),
    "create_rows": (
        True,
        lambda s: {"table_id": s.table.id, "rows": [{"Name": "Plan"}]},
    ),
    "update_rows": (
        True,
        lambda s: {
            "table_id": s.table.id,
            "rows": [{"id": s.row.id, "Name": "Done"}],
        },
    ),
    "delete_rows": (True, lambda s: {"table_id": s.table.id, "row_ids": [s.row.id]}),
}

PRESENTATION_CONTRACT = json.loads(
    (Path(__file__).resolve().parents[5] / "tests/cases/agent_tools.json").read_text()
)
PRESENTATIONS = {case["name"]: case for case in PRESENTATION_CONTRACT["tools"]}


@pytest.fixture
def workspace_data(data_fixture):
    """A table of a workspace, and an Agent identity of that workspace to act as."""

    database = data_fixture.create_database_application(name="Work")
    table = data_fixture.create_database_table(database=database, name="Tasks")
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    identity = Agent.objects.create(workspace=database.workspace, name="Ops")
    return SimpleNamespace(
        ctx=ToolContext(user=identity, workspace=database.workspace),
        table=table,
        hours=data_fixture.create_number_field(table=table, name="Hours"),
        view=data_fixture.create_grid_view(table=table, name="Grid"),
        row=table.get_model().objects.create(**{f"field_{name.id}": "Draft"}),
    )


def preview_of(name: str, ctx: ToolContext, arguments: dict) -> dict:
    """The stored request of a call, from arguments validated as the model's are."""

    tool_type = agent_tool_type_registry.get(name)
    validated = tool_type.get_tool(ctx).function_schema.validator.validate_python(
        arguments
    )
    return tool_type.get_step_preview_input(ctx, validated)


def person_ctx(workspace_data, data_fixture) -> ToolContext:
    """A person of the workspace to act as, for tools the Agent identity can't use."""

    workspace = workspace_data.ctx.workspace
    return ToolContext(
        user=data_fixture.create_user(workspace=workspace), workspace=workspace
    )


class ModelRun:
    """The model run a tool streams its readable request to."""

    def __init__(self) -> None:
        self.input: dict = {}

    async def emit(self, event: ToolCallInputEvent) -> None:
        self.input = event.input


@dataclass
class Called:
    """A call's result, and the readable request it sent to its step."""

    return_value: Any
    metadata: dict | None
    input: dict


def call_tool(tool_type: AgentToolType, ctx: ToolContext, arguments: dict) -> Called:
    tool = tool_type.get_tool(ctx)
    run = ModelRun()
    result = async_to_sync(tool.function)(
        run, **tool.function_schema.validator.validate_python(arguments)
    )
    assert isinstance(result, ToolReturn), result
    return Called(result.return_value, result.metadata, run.input)


class TablePreviewAgentToolType(AgentToolType):
    """A change of one table whose request names the table."""

    changes_data = True

    def get_step_preview(self, ctx: ToolContext, arguments: dict) -> StepPreview:
        return StepPreview(table_reference(ctx, arguments["table_id"])[1])


def test_tool_names_and_whether_they_change_data_stay_the_same():
    """
    Agents allow tools by name: a rename drops a tool, a reused name allows the new
    tool, and a read tool that starts changing data does so where only reads were
    allowed. Change this only with a migration of the allowed tools.
    """

    assert {
        tool_type.type: tool_type.changes_data
        for tool_type in agent_tool_type_registry.get_all()
    } == {name: changes_data for name, (changes_data, _) in TOOLS.items()}
    assert set(PRESENTATIONS) == set(TOOLS)
    assert list(ToolErrorCode) == PRESENTATION_CONTRACT["step_error_codes"]


@pytest.mark.parametrize("name", PRESENTATIONS)
def test_tool_presentation_contract_uses_valid_arguments_and_safe_summaries(name):
    case = PRESENTATIONS[name]
    tool_type = agent_tool_type_registry.get(name)
    tool_type.get_tool(None).function_schema.validator.validate_python(
        case["arguments"]
    )

    assert tool_type.get_step_input(case["arguments"]) == case["input"]
    assert tool_type.get_step_input({}) == {}
    assert (
        tool_type.get_step_input({key: "private value" for key in case["arguments"]})
        == {}
    )


@pytest.mark.parametrize("name", PRESENTATIONS)
def test_tool_input_excludes_unapproved_arguments_without_mutating_the_call(name):
    case = PRESENTATIONS[name]
    arguments = {**case["arguments"], "credential": "DO_NOT_DISPLAY"}
    original = json.dumps(arguments)

    summary = agent_tool_type_registry.get(name).get_step_input(arguments)

    assert summary == case["input"]
    assert "DO_NOT_DISPLAY" not in json.dumps(summary)
    assert json.dumps(arguments) == original

    class UnrepresentedTool(AgentToolType):
        type = "unrepresented"

    assert UnrepresentedTool().get_step_input(arguments) == {}


def test_row_writes_keep_values_out_of_the_step_input():
    arguments = {"table_id": 1, "rows": [{"Password": "Hunter2!"}]}

    for name in ("create_rows", "update_rows"):
        summary = agent_tool_type_registry.get(name).get_step_input(arguments)
        assert summary == {"requested_count": 1}


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name",
    [
        pytest.param(
            name,
            marks=pytest.mark.xfail(
                strict=True,
                reason="Agent trash/user attribution requires the broader fix in #6259",
            ),
        )
        if name == "delete_fields"
        else name
        for name in TOOLS
    ],
)
def test_every_tool_acts_as_the_agent_identity(workspace_data, name):
    _, arguments = TOOLS[name]
    result = call_tool(
        agent_tool_type_registry.get(name),
        workspace_data.ctx,
        arguments(workspace_data),
    )

    value = result.return_value
    if name == "delete_fields":
        workspace_data.hours.refresh_from_db()
        assert workspace_data.hours.trashed
        assert value["deleted_field_ids"] == [workspace_data.hours.id]
    assert not (
        isinstance(value, dict) and (value.get("error") or value.get("errors"))
    ), value
    assert (result.metadata, result.input) == (
        {"facts": PRESENTATIONS[name]["facts"]},
        PRESENTATIONS[name].get("preview", {}),
    ), value


@pytest.mark.django_db
def test_successful_field_deletion_reports_its_confirmed_count(
    workspace_data, data_fixture
):
    result = call_tool(
        agent_tool_type_registry.get("delete_fields"),
        person_ctx(workspace_data, data_fixture),
        {"field_ids": [workspace_data.hours.id]},
    )

    assert result.metadata["facts"] == PRESENTATIONS["delete_fields"]["facts"]
    assert result.return_value == {
        "changed": True,
        "deleted_field_ids": [workspace_data.hours.id],
    }


@pytest.mark.django_db
def test_renaming_a_database_to_its_current_name_reports_no_change(workspace_data):
    result = call_tool(
        agent_tool_type_registry.get("update_database"),
        workspace_data.ctx,
        {"database_id": workspace_data.table.database_id, "name": "Work"},
    )

    assert result.return_value == {
        "updated_database": {
            "id": workspace_data.table.database_id,
            "name": "Work",
        },
        "changed": False,
    }
    assert result.metadata == {"facts": {"database": "Work", "changed": False}}


@pytest.mark.django_db
@pytest.mark.parametrize("hidden", ["other_workspace", "trashed", "other_type"])
def test_database_update_does_not_disclose_or_change_hidden_applications(
    workspace_data, data_fixture, hidden
):
    if hidden == "other_workspace":
        database = data_fixture.create_database_application(name="Private")
    elif hidden == "trashed":
        database = data_fixture.create_database_application(
            workspace=workspace_data.ctx.workspace, name="Private", trashed=True
        )
    else:
        database = data_fixture.create_builder_application(
            workspace=workspace_data.ctx.workspace, name="Private"
        )

    result = call_tool(
        agent_tool_type_registry.get("update_database"),
        workspace_data.ctx,
        {"database_id": database.id, "name": "Projects"},
    )

    assert result.return_value["error"]["code"] == "not_found"
    assert result.input == {"values": {"database_id": database.id, "name": "Projects"}}
    database.refresh_from_db()
    assert database.name == "Private"


@pytest.mark.django_db
def test_agent_form_creation_does_not_notify_user_with_same_id(
    data_fixture, api_client
):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    workspace = table.database.workspace
    identity = Agent.objects.create(id=user.id, workspace=workspace, name="Ops")

    result = call_tool(
        agent_tool_type_registry.get("create_views"),
        ToolContext(user=identity, workspace=workspace),
        {
            "table_id": table.id,
            "views": [
                {
                    "name": "Contact form",
                    "type": "form",
                    "public": True,
                    "receive_notification_on_submit": True,
                    "field_options": [
                        {
                            "field_id": field.id,
                            "name": "Name",
                            "description": "",
                            "required": False,
                            "order": 1,
                        }
                    ],
                }
            ],
        },
    )

    assert "error" not in result.return_value
    form = FormView.objects.get(id=result.return_value["created_views"][0]["id"])
    response = api_client.post(
        reverse("api:database:views:form:submit", kwargs={"slug": form.slug}),
        {field.db_column: "Submitted name"},
        format="json",
    )

    assert response.status_code == 200
    assert not NotificationRecipient.objects.filter(
        recipient=user, notification__type="form_submitted"
    ).exists()
    assert not form.users_to_notify_on_submit.exists()


@pytest.mark.django_db
def test_tool_errors_are_answered_to_the_model(workspace_data, data_fixture):
    def broken(ctx: ToolContext) -> None:
        raise RuntimeError("Private details")

    class BrokenAgentToolType(AgentToolType):
        type = "broken"
        function = broken

    other_table = data_fixture.create_database_table()

    missing = call_tool(
        agent_tool_type_registry.get("list_table_rows"),
        workspace_data.ctx,
        {"table_id": other_table.id},
    )
    assert missing.return_value == {
        "error": {"code": "not_found", "message": "Not found in this workspace."}
    }
    assert (missing.metadata, missing.input) == (
        {"error_code": "not_found"},
        {"values": {"table_id": other_table.id}},
    )
    unexpected = call_tool(BrokenAgentToolType(), workspace_data.ctx, {})
    assert unexpected.return_value == {
        "error": {"code": "failed", "message": "Internal error."}
    }
    assert (unexpected.metadata, unexpected.input) == ({"error_code": "failed"}, {})
    hidden_schema = call_tool(
        agent_tool_type_registry.get("get_table_schema"),
        workspace_data.ctx,
        {"table_ids": [other_table.id]},
    )
    assert (hidden_schema.return_value, hidden_schema.input) == ([], {})


@pytest.mark.django_db
def test_a_request_that_cannot_be_named_keeps_its_ids_and_is_left_to_the_tool(
    workspace_data, data_fixture
):
    def write(ctx: ToolContext, table_id: int) -> str:
        return "done"

    class WriteAgentToolType(TablePreviewAgentToolType):
        type = "write"
        function = write

    hidden_id = data_fixture.create_database_table().id
    hidden = call_tool(
        WriteAgentToolType(), workspace_data.ctx, {"table_id": hidden_id}
    )
    named = call_tool(
        WriteAgentToolType(), workspace_data.ctx, {"table_id": workspace_data.table.id}
    )

    assert (hidden.return_value, hidden.input) == (
        "done",
        {"values": {"table_id": hidden_id}},
    )
    assert named.input == {"values": {"table": "Tasks"}}


@pytest.mark.django_db
def test_a_call_that_fails_after_its_request_was_named_keeps_it(workspace_data):
    def refuse(ctx: ToolContext, table_id: int) -> str:
        raise ToolInputError("Pick another table.")

    class RefuseAgentToolType(TablePreviewAgentToolType):
        type = "refuse"
        function = refuse

    result = call_tool(
        RefuseAgentToolType(), workspace_data.ctx, {"table_id": workspace_data.table.id}
    )

    assert result.return_value["error"]["code"] == "invalid_input"
    assert result.input == {"values": {"table": "Tasks"}}


@pytest.mark.django_db
def test_display_facts_failure_keeps_the_successful_tool_result(workspace_data, logs):
    private_argument = "PRIVATE_FACTS_ARGUMENT_CANARY"
    private_result = "PRIVATE_FACTS_RESULT_CANARY"
    private_error = "PRIVATE_FACTS_ERROR_CANARY"

    def done(ctx: ToolContext, private_value: str) -> str:
        return private_result

    class FactlessAgentToolType(AgentToolType):
        type = "factless"
        function = done

        def get_step_facts(self, ctx, arguments, result):
            raise RuntimeError(private_error)

    result = call_tool(
        FactlessAgentToolType(),
        workspace_data.ctx,
        {"private_value": private_argument},
    )

    assert (result.return_value, result.metadata) == (private_result, {"facts": {}})
    assert [log.record["message"] for log in logs] == [
        "Agent tool factless step facts failed (RuntimeError)"
    ]
    output = "".join(str(entry) for entry in logs)
    assert private_argument not in output
    assert private_result not in output
    assert private_error not in output


@pytest.mark.django_db
def test_returned_errors_never_extract_display_facts(workspace_data, mocker):
    def refused(ctx: ToolContext) -> dict:
        return {"error": "Not allowed"}

    class RefusedAgentToolType(AgentToolType):
        type = "refused"
        function = refused

    tool_type = RefusedAgentToolType()
    facts = mocker.patch.object(tool_type, "get_step_facts")

    result = call_tool(tool_type, workspace_data.ctx, {})

    assert (result.return_value, result.metadata) == ({"error": "Not allowed"}, None)
    facts.assert_not_called()


@pytest.mark.django_db
def test_reused_tables_are_counted_apart_and_used_view_names_are_conflicts(
    workspace_data,
):
    tables = call_tool(
        agent_tool_type_registry.get("create_tables"),
        workspace_data.ctx,
        {
            "database_id": workspace_data.table.database_id,
            "tables": [
                {"name": "Tasks", "primary_field_name": "Name", "fields": []},
                {"name": "Projects", "primary_field_name": "Name", "fields": []},
            ],
        },
    )
    views = call_tool(
        agent_tool_type_registry.get("create_views"),
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "views": [{"type": "grid", "name": workspace_data.view.name}],
        },
    )

    assert tables.metadata["facts"] == {"count": 1, "table": "Projects"}
    assert views.return_value["error"]["code"] == "conflict"


@pytest.mark.django_db
def test_partial_field_creation_counts_only_created_fields(workspace_data):
    tool_type = agent_tool_type_registry.get("create_fields")
    arguments = {
        "table_id": workspace_data.table.id,
        "fields": [
            {"name": "Notes", "type": "text"},
            {"name": "Broken", "type": "formula", "formula": "unknown("},
        ],
    }

    result = call_tool(tool_type, workspace_data.ctx, arguments)

    assert tool_type.get_step_input(arguments) == {"requested_count": 2}
    assert (result.metadata, result.input) == (
        {"facts": {"count": 1}},
        {"values": {"table": "Tasks", "fields": arguments["fields"]}},
    )
    assert len(result.return_value["errors"]) == 1


@pytest.mark.django_db
def test_fields_with_the_same_name_stay_separate_entries(workspace_data, data_fixture):
    notes = data_fixture.create_database_table(
        database=workspace_data.table.database, name="Notes"
    )
    copy = data_fixture.create_number_field(table=notes, name="Hours")

    preview = preview_of(
        "delete_fields",
        workspace_data.ctx,
        {"field_ids": [workspace_data.hours.id, copy.id]},
    )

    assert preview == {
        "values": {
            "fields": [
                {"field": "Hours", "table": "Tasks"},
                {"field": "Hours", "table": "Notes"},
            ]
        }
    }


@pytest.mark.django_db
def test_a_field_that_cannot_be_named_keeps_its_id_and_fails_alone(
    workspace_data, data_fixture
):
    trashed = data_fixture.create_text_field(table=workspace_data.table, trashed=True)
    hidden = data_fixture.create_text_field(name="Elsewhere")

    deleted = call_tool(
        agent_tool_type_registry.get("delete_fields"),
        person_ctx(workspace_data, data_fixture),
        {"field_ids": [workspace_data.hours.id, trashed.id]},
    )
    updated = preview_of(
        "update_fields",
        workspace_data.ctx,
        {"fields": [{"field_id": hidden.id, "name": "Leak"}]},
    )

    workspace_data.hours.refresh_from_db()
    assert workspace_data.hours.trashed
    assert deleted.return_value["deleted_field_ids"] == [workspace_data.hours.id]
    assert [error["item"] for error in deleted.return_value["errors"]] == [trashed.id]
    assert deleted.input == {
        "values": {
            "fields": [{"field": "Hours", "table": "Tasks"}, {"field_id": trashed.id}]
        }
    }
    assert updated == {
        "values": {"fields": [{"field_id": hidden.id, "changes": {"name": "Leak"}}]}
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "name,arguments,values",
    [
        (
            "delete_rows",
            {"table_id": 999999, "row_ids": [1]},
            {"table_id": 999999, "rows": [{"row_id": 1}]},
        ),
        (
            "update_rows",
            {"table_id": 999999, "rows": [{"id": 1, "Name": "Leak"}]},
            {"table_id": 999999, "rows": [{"row_id": 1, "values": {"Name": "••••"}}]},
        ),
        (
            "create_view_filters",
            {"view_filters": [{"view_id": 999999, "filters": []}]},
            {"views": [{"view_id": 999999, "filters": []}]},
        ),
    ],
)
def test_what_a_request_works_on_keeps_its_id_when_it_cannot_be_named(
    workspace_data, name, arguments, values
):
    assert preview_of(name, workspace_data.ctx, arguments) == {"values": values}


@pytest.mark.django_db
def test_filter_fields_are_named_and_unknown_ones_stay_for_the_tool(workspace_data):
    preview = preview_of(
        "create_view_filters",
        workspace_data.ctx,
        {
            "view_filters": [
                {
                    "view_id": workspace_data.view.id,
                    "filters": [
                        {
                            "field_id": workspace_data.hours.id,
                            "type": "number",
                            "operator": "higher_than",
                            "value": 1,
                        },
                        {
                            "field_id": 999999,
                            "type": "number",
                            "operator": "higher_than",
                            "value": 2,
                        },
                    ],
                }
            ]
        },
    )

    assert preview["values"]["views"][0]["filters"] == [
        {"field": "Hours", "type": "number", "operator": "higher_than", "value": 1},
        {"field_id": 999999, "type": "number", "operator": "higher_than", "value": 2},
    ]


@pytest.mark.django_db
def test_long_requests_keep_10_items_at_any_depth_and_their_requested_count(
    workspace_data,
):
    options = [{"value": f"O{index}", "color": "blue"} for index in range(12)]
    arguments = {
        "table_id": workspace_data.table.id,
        "fields": [{"name": "Stage", "type": "single_select", "options": options}]
        + [{"name": f"F{index}", "type": "text"} for index in range(14)],
    }

    preview = preview_of("create_fields", workspace_data.ctx, arguments)

    assert agent_tool_type_registry.get("create_fields").get_step_input(arguments) == {
        "requested_count": 15
    }
    assert preview["truncated"] is True
    assert [field["name"] for field in preview["values"]["fields"]] == ["Stage"] + [
        f"F{index}" for index in range(9)
    ]
    assert preview["values"]["fields"][0]["options"] == options[:10]


@pytest.mark.django_db
def test_a_link_to_a_visible_table_is_named(workspace_data, data_fixture):
    projects = data_fixture.create_database_table(
        database=workspace_data.table.database, name="Projects"
    )

    preview = preview_of(
        "create_fields",
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "fields": [
                {"name": "Project", "type": "link_row", "linked_table": projects.id}
            ],
        },
    )

    assert preview["values"]["fields"] == [
        {"name": "Project", "type": "link_row", "linked_table": "Projects"}
    ]


@pytest.mark.django_db
def test_view_requests_name_their_fields(workspace_data, data_fixture):
    status = data_fixture.create_single_select_field(
        table=workspace_data.table, name="Status"
    )

    preview = preview_of(
        "create_views",
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "views": [
                {"name": "Board", "type": "kanban", "column_field_id": status.id}
            ],
        },
    )

    assert preview == {
        "values": {
            "table": "Tasks",
            "views": [{"name": "Board", "type": "kanban", "column_field": "Status"}],
        }
    }


@pytest.mark.django_db
def test_views_are_created_when_the_identity_may_not_list_fields(
    workspace_data, data_fixture, mocker
):
    status = data_fixture.create_single_select_field(
        table=workspace_data.table, name="Status"
    )
    mocker.patch(
        "baserow.contrib.agent.database_previews.permitted_tables", return_value=[]
    )
    board = {"name": "Board", "type": "kanban", "column_field_id": status.id}

    result = call_tool(
        agent_tool_type_registry.get("create_views"),
        workspace_data.ctx,
        {"table_id": workspace_data.table.id, "views": [board]},
    )

    assert result.input == {"values": {"table": "Tasks", "views": [board]}}


@pytest.mark.django_db
def test_row_writes_show_their_values_with_passwords_masked(
    workspace_data, data_fixture
):
    data_fixture.create_password_field(table=workspace_data.table, name="Secret")

    result = call_tool(
        agent_tool_type_registry.get("create_rows"),
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "rows": [{"Name": "Acme", "Secret": "hunter2"}],
        },
    )

    assert result.input == {
        "values": {"table": "Tasks", "rows": [{"Name": "Acme", "Secret": "••••"}]}
    }


@pytest.mark.django_db
def test_a_failed_row_write_never_stores_a_value_of_a_password_field(
    workspace_data, data_fixture
):
    data_fixture.create_password_field(table=workspace_data.table, name="Secret")

    result = call_tool(
        agent_tool_type_registry.get("create_rows"),
        workspace_data.ctx,
        {"table_id": workspace_data.table.id, "rows": [{"secret": "hunter2"}]},
    )

    assert "error" in result.return_value
    assert result.input == {"values": {"table": "Tasks", "rows": [{"secret": "••••"}]}}
    assert "hunter2" not in json.dumps(result.input)


@pytest.mark.django_db
def test_row_changes_mask_passwords(workspace_data, data_fixture):
    data_fixture.create_password_field(table=workspace_data.table, name="Secret")

    preview = preview_of(
        "update_rows",
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "rows": [{"id": workspace_data.row.id, "Name": "Done", "Secret": "x"}],
        },
    )

    assert preview["values"]["rows"] == [
        {"row": "Draft", "values": {"Name": "Done", "Secret": "••••"}}
    ]


@pytest.mark.django_db
def test_changed_rows_are_named_by_their_primary_value(workspace_data):
    unnamed = workspace_data.table.get_model().objects.create()
    row = workspace_data.row

    update = preview_of(
        "update_rows",
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "rows": [{"id": row.id, "Name": "Done"}, {"id": unnamed.id, "Hours": 2}],
        },
    )
    delete = preview_of(
        "delete_rows",
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "row_ids": [row.id, unnamed.id],
        },
    )

    assert update == {
        "values": {
            "table": "Tasks",
            "rows": [
                {"row": "Draft", "values": {"Name": "Done"}},
                {"row": f"unnamed row {unnamed.id}", "values": {"Hours": 2}},
            ],
        }
    }
    assert delete == {
        "values": {"table": "Tasks", "rows": ["Draft", f"unnamed row {unnamed.id}"]}
    }


@pytest.mark.django_db
def test_a_missing_row_keeps_its_id_and_the_tool_deletes_nothing(workspace_data):
    result = call_tool(
        agent_tool_type_registry.get("delete_rows"),
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "row_ids": [workspace_data.row.id, 999999],
        },
    )

    assert result.return_value["error"]["code"] == "not_found"
    assert result.input == {
        "values": {"table": "Tasks", "rows": ["Draft", {"row_id": 999999}]}
    }
    assert (
        workspace_data.table.get_model()
        .objects.filter(id=workspace_data.row.id)
        .exists()
    )


@pytest.mark.django_db
def test_rows_of_a_table_without_a_primary_field_are_deleted_unnamed(workspace_data):
    workspace_data.table.field_set.update(primary=False)

    result = call_tool(
        agent_tool_type_registry.get("delete_rows"),
        workspace_data.ctx,
        {"table_id": workspace_data.table.id, "row_ids": [workspace_data.row.id]},
    )

    assert "error" not in result.return_value
    assert result.input == {}
    assert not workspace_data.table.get_model().objects.exists()


@pytest.mark.django_db
def test_a_row_write_to_a_table_the_identity_cannot_see_changes_nothing(
    workspace_data, data_fixture
):
    other = data_fixture.create_database_table()
    data_fixture.create_text_field(table=other, name="Name", primary=True)

    result = call_tool(
        agent_tool_type_registry.get("create_rows"),
        workspace_data.ctx,
        {"table_id": other.id, "rows": [{"Name": "Leak"}]},
    )

    assert (result.metadata, result.input) == (
        {"error_code": "not_found"},
        {"values": {"table_id": other.id, "rows": [{"Name": "••••"}]}},
    )
    assert other.get_model().objects.count() == 0


@pytest.mark.django_db
def test_a_row_request_too_large_to_store_keeps_the_rows_that_fit(
    workspace_data, data_fixture
):
    data_fixture.create_text_field(table=workspace_data.table, name="Notes")

    preview = preview_of(
        "create_rows",
        workspace_data.ctx,
        {
            "table_id": workspace_data.table.id,
            "rows": [{"Name": "x" * 1000, "Notes": "y" * 1000} for _ in range(12)],
        },
    )

    assert preview["truncated"] is True
    assert preview["values"]["table"] == "Tasks"
    assert 0 < len(preview["values"]["rows"]) < 10
    assert len(json.dumps(preview["values"])) <= MAX_INPUT_PREVIEW_SIZE


@pytest.mark.django_db
def test_an_unexpected_preview_error_leaves_the_call_unnamed(
    workspace_data, data_fixture, mocker, logs
):
    private_error = "PRIVATE_PREVIEW_ERROR_CANARY"
    tool_type = agent_tool_type_registry.get("delete_fields")
    mocker.patch.object(
        tool_type, "get_step_preview", side_effect=RuntimeError(private_error)
    )

    result = call_tool(
        tool_type,
        person_ctx(workspace_data, data_fixture),
        {"field_ids": [workspace_data.hours.id]},
    )

    workspace_data.hours.refresh_from_db()
    assert (result.metadata, result.input) == ({"facts": {"count": 1}}, {})
    assert workspace_data.hours.trashed
    assert [log.record["message"] for log in logs] == [
        "Agent tool delete_fields preview failed (RuntimeError)"
    ]
    assert private_error not in "".join(str(entry) for entry in logs)


@pytest.mark.django_db
def test_tool_calls_track_identity_usage_with_the_existing_throttle(workspace_data):
    identity = workspace_data.ctx.user
    assert identity.last_active is None

    with freeze_time() as clock:
        result = call_tool(
            agent_tool_type_registry.get("list_views"),
            workspace_data.ctx,
            {"table_id": workspace_data.table.id},
        )
        assert "error" not in result.return_value
        identity.refresh_from_db()
        first_activity = identity.last_active
        assert first_activity is not None

        clock.tick(30)
        result = call_tool(
            agent_tool_type_registry.get("list_views"),
            workspace_data.ctx,
            {"table_id": workspace_data.table.id},
        )
        assert "error" not in result.return_value
        identity.refresh_from_db()
        assert identity.last_active == first_activity


@pytest.mark.django_db
def test_unexpected_tool_errors_do_not_log_private_values(workspace_data, mocker, logs):
    private_search = "PRIVATE_SEARCH_CANARY"
    private_error = "PRIVATE_ERROR_CANARY"
    mocker.patch(
        "baserow.contrib.database.tools.rows.serialize_rows_for_response",
        side_effect=OperationalError(private_error),
    )

    result = call_tool(
        agent_tool_type_registry.get("list_table_rows"),
        workspace_data.ctx,
        {"table_id": workspace_data.table.id, "search": private_search},
    )

    assert result.return_value == {
        "error": {"code": "failed", "message": "Internal error."}
    }
    assert (result.metadata, result.input) == (
        {"error_code": "failed"},
        {"values": {"table": "Tasks"}},
    )
    output = "".join(str(entry) for entry in logs)
    assert "list_table_rows" in output
    assert "OperationalError" in output
    assert private_search not in output
    assert private_error not in output


@pytest.mark.django_db
def test_a_stop_waits_for_the_running_tool(workspace_data):
    started, release = threading.Event(), threading.Event()

    def slow(ctx: ToolContext) -> str:
        started.set()
        release.wait(5)
        return "Changed"

    class SlowAgentToolType(AgentToolType):
        type = "slow"
        function = slow

    async def stop_during_the_call() -> bool:
        call = asyncio.ensure_future(
            SlowAgentToolType().get_tool(workspace_data.ctx).function(ModelRun())
        )
        await asyncio.to_thread(started.wait, 5)
        call.cancel()
        await asyncio.sleep(0.1)
        still_running = not call.done()
        release.set()
        with pytest.raises(asyncio.CancelledError):
            await call
        return still_running

    assert async_to_sync(stop_during_the_call)()
