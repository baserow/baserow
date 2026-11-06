from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from pydantic_ai.messages import (
    FunctionToolCallEvent,
    FunctionToolResultEvent,
    RetryPromptPart,
    ToolCallPart,
    ToolReturnPart,
)

from baserow.contrib.agent.constants import (
    STEP_RESOURCE_LIMIT,
    STEP_RESOURCE_NAME_MAX_LENGTH,
    STEP_TARGET_MAX_LENGTH,
)
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.contrib.agent.replies import AgentResponder


def responder():
    request = SimpleNamespace(allowed_tool_names=agent_tool_type_registry.get_types())
    return AgentResponder(request, Mock(), Mock(), {})


def returned(tool, content, outcome="success"):
    return FunctionToolResultEvent(
        ToolReturnPart(tool, content, "provider-call", outcome=outcome)
    )


def discovered_resources():
    return {
        ("database", 1): "Company",
        ("table", 2): "Projects",
        ("table", 3): "Customers",
        ("field", 4): "Title",
        ("field", 5): "Notes",
        ("view", 6): "Board",
    }


@pytest.mark.parametrize(
    "name,arguments,target",
    [
        ("list_tables", {"database_id": 1}, "Company"),
        ("get_table_schema", {"table_ids": [2, 3, 2]}, "Projects, Customers"),
        ("list_table_rows", {"table_id": 2}, "Projects"),
        ("list_views", {"table_id": 2}, "Projects"),
        ("create_tables", {"database_id": 1}, "Company"),
        ("create_fields", {"table_id": 2}, "Projects"),
        ("update_fields", {"fields": [{"field_id": 4, "name": "Renamed"}]}, "Title"),
        ("delete_fields", {"field_ids": [4, 5]}, "Title, Notes"),
        ("create_views", {"table_id": 2}, "Projects"),
        ("create_view_filters", {"view_filters": [{"view_id": 6}]}, "Board"),
        ("create_rows", {"table_id": 2}, "Projects"),
        ("update_rows", {"table_id": 2}, "Projects"),
        ("delete_rows", {"table_id": 2}, "Projects"),
    ],
)
def test_database_tool_targets_use_only_previously_disclosed_names(
    name, arguments, target
):
    tool = agent_tool_type_registry.get(name)

    assert tool.get_step_target(arguments, discovered_resources()) == target
    assert tool.get_step_target(arguments, {}) is None
    assert tool.get_step_target({}, discovered_resources()) is None


@pytest.mark.parametrize("ids", [[2, 999], [2, "3"], [True], []])
def test_partly_known_or_invalid_batch_targets_stay_generic(ids):
    tool = agent_tool_type_registry.get("get_table_schema")

    assert tool.get_step_target({"table_ids": ids}, discovered_resources()) is None


def test_discovery_names_flow_to_later_calls_without_raw_result_data():
    reply = responder()
    reply._on_event(
        returned(
            "list_tables",
            [
                {
                    "id": 2,
                    "name": "Projects",
                    "database_id": 1,
                    "database_name": "Company",
                }
            ],
        )
    )
    reply._on_event(
        returned(
            "get_table_schema",
            [
                {
                    "id": 2,
                    "name": "Projects",
                    "fields": [
                        {"id": 4, "name": "Title", "formula": "PRIVATE_FORMULA"},
                        {
                            "id": 5,
                            "name": "Customer",
                            "link_row_table_id": 3,
                            "link_row_table_name": "Customers",
                        },
                    ],
                }
            ],
        )
    )
    reply._on_event(returned("list_views", {"views": [{"id": 6, "name": "Board"}]}))

    for tool, arguments, target in [
        ("create_tables", {"database_id": 1}, "Company"),
        ("list_table_rows", {"table_id": 3}, "Customers"),
        ("delete_fields", {"field_ids": [4]}, "Title"),
        ("create_view_filters", {"view_filters": [{"view_id": 6}]}, "Board"),
    ]:
        assert reply._describe_call(tool, arguments)["input"]["target"] == target
    assert "PRIVATE_FORMULA" not in str(reply._step_resources)
    assert (
        "target"
        not in reply._describe_call(
            "list_table_rows", {"table_id": 999, "name": "Model guessed name"}
        )["input"]
    )
    assert (
        "target"
        not in responder()._describe_call("list_table_rows", {"table_id": 3})["input"]
    )


@pytest.mark.parametrize(
    "tool,result,next_tool,arguments,target",
    [
        (
            "create_tables",
            {
                "created_tables": [{"id": 2, "name": "Projects", "fields": []}],
                "reused_tables": [],
            },
            "list_table_rows",
            {"table_id": 2},
            "Projects",
        ),
        (
            "create_fields",
            {"created_fields": [{"id": 4, "name": "Title"}]},
            "delete_fields",
            {"field_ids": [4]},
            "Title",
        ),
        (
            "update_fields",
            {"updated_fields": [{"id": 4, "name": "New title"}]},
            "delete_fields",
            {"field_ids": [4]},
            "New title",
        ),
        (
            "create_views",
            {"created_views": [{"id": 6, "name": "Board"}]},
            "create_view_filters",
            {"view_filters": [{"view_id": 6}]},
            "Board",
        ),
    ],
)
def test_successful_mutations_disclose_names_for_followup_calls(
    tool, result, next_tool, arguments, target
):
    reply = responder()

    reply._on_event(returned(tool, result))

    assert reply._describe_call(next_tool, arguments)["input"]["target"] == target


@pytest.mark.parametrize(
    "event",
    [
        returned("list_tables", {"error": "Private error"}),
        returned("list_tables", [], outcome="denied"),
        returned("list_tables", [], outcome="failed"),
        returned("list_tables", [], outcome="interrupted"),
        returned("unknown_tool", []),
        FunctionToolResultEvent(RetryPromptPart("Private retry", tool_call_id="retry")),
    ],
)
def test_failed_and_unknown_tools_cannot_disclose_resource_names(event, mocker):
    reply = responder()
    extract = mocker.spy(
        agent_tool_type_registry.get("list_tables"), "get_step_resources"
    )

    reply._on_event(event)

    extract.assert_not_called()
    assert reply._step_resources == {}


def test_name_catalog_and_targets_are_bounded_and_reject_invalid_names(mocker):
    reply = responder()
    values = {("table", i): f"Table {i}" for i in range(1, STEP_RESOURCE_LIMIT + 2)}
    values.update(
        {
            ("table", 9991): "\ud800",
            ("table", 9992): "Bad\x00name",
            ("table", 9993): "",
            ("table", 9994): object(),
            ("table", 9995): "x" * 2000,
            ("table", 9996): "y" * 2000,
            ("table", 9997): "z" * 2000,
        }
    )
    mocker.patch.object(
        agent_tool_type_registry.get("list_tables"),
        "get_step_resources",
        return_value=values,
    )

    reply._on_event(returned("list_tables", []))

    assert len(reply._step_resources) == STEP_RESOURCE_LIMIT
    assert ("table", 1) not in reply._step_resources
    assert all(
        len(name) <= STEP_RESOURCE_NAME_MAX_LENGTH
        for name in reply._step_resources.values()
    )
    target = reply._describe_call(
        "get_table_schema", {"table_ids": [9995, 9996, 9997]}
    )["input"]["target"]
    assert len(target) == STEP_TARGET_MAX_LENGTH
    assert target.endswith("…")
    assert not any(("table", i) in reply._step_resources for i in range(9991, 9995))


def test_target_errors_keep_the_input_summary(mocker, logs):
    reply = responder()
    mocker.patch.object(
        agent_tool_type_registry.get("create_rows"),
        "get_step_target",
        side_effect=RuntimeError("PRIVATE_TARGET_ERROR"),
    )

    summary = reply._describe_call(
        "create_rows", {"table_id": 2, "rows": [{"Name": "Plan"}]}
    )["input"]

    assert summary == {
        "requested_count": 1,
        "values": {"table_id": 2, "rows": [{"Name": "Plan"}]},
    }
    assert [log.record["message"] for log in logs] == [
        "Agent tool create_rows step target failed (RuntimeError)"
    ]


def test_resource_extraction_errors_keep_the_step(mocker, logs):
    reply = responder()
    mocker.patch.object(
        agent_tool_type_registry.get("list_tables"),
        "get_step_resources",
        side_effect=RuntimeError("PRIVATE_RESOURCE_ERROR"),
    )
    reply._on_event(
        FunctionToolCallEvent(ToolCallPart("list_tables", {}, "provider-call"))
    )

    reply._on_event(returned("list_tables", []))

    assert reply._steps.finish()[0]["status"] == "done"
    assert reply._step_resources == {}
    assert [log.record["message"] for log in logs] == [
        "Agent tool list_tables step resources failed (RuntimeError)"
    ]


def test_known_target_is_retained_for_live_failed_and_stopped_steps():
    reply = responder()
    reply._on_event(returned("list_views", {"views": [{"id": 6, "name": "Board"}]}))
    arguments = {"view_filters": [{"view_id": 6}]}
    reply._on_event(
        FunctionToolCallEvent(ToolCallPart("create_view_filters", arguments, "failed"))
    )
    reply._on_event(
        FunctionToolResultEvent(
            ToolReturnPart("create_view_filters", {"error": "Denied"}, "failed")
        )
    )
    reply._on_event(
        FunctionToolCallEvent(ToolCallPart("create_view_filters", arguments, "stopped"))
    )

    steps = reply._steps.finish()

    assert [step["status"] for step in steps] == ["failed", "stopped"]
    assert all(step["input"]["target"] == "Board" for step in steps)
    emitted = [entry.args[1] for entry in reply._journal.emit.call_args_list]
    assert all(step["input"]["target"] == "Board" for step in emitted)
