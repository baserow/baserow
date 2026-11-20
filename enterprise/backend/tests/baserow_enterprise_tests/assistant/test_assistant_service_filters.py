"""
Tests for Kuma's service filter requests: the prompt, the agent's retries, and how
its answer is saved. Applying and validating the operations is tested with the
shared service filter tools in core.
"""

from dataclasses import dataclass
from typing import Any

import pytest
from pydantic_ai.messages import ModelResponse, RetryPromptPart, ToolCallPart
from pydantic_ai.models.function import FunctionModel

from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFilter,
    LocalBaserowTableServiceFilterGroup,
)
from baserow.contrib.integrations.local_baserow.service_filters.exceptions import (
    ServiceFilterTargetDoesNotExist,
    ServiceFilterTargetNotSupported,
)
from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterOperation,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import PermissionException
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.tools import ToolContext
from baserow.core.trash.handler import TrashHandler
from baserow_enterprise.assistant import model_profiles
from baserow_enterprise.assistant.exceptions import ServiceFilterGenerationFailed
from baserow_enterprise.assistant.service_filters import handler as kuma_handler
from baserow_enterprise.assistant.service_filters import run_service_filter_request
from baserow_enterprise.assistant.service_filters.agent import ServiceFilterChanges
from baserow_premium.integrations.local_baserow.models import (
    LocalBaserowGroupedAggregateRows,
)

# ---------------------------------------------------------------------------
# Fixtures and helpers
# ---------------------------------------------------------------------------

SESSION_ID = "c5f5a3a8-8b7e-4f1e-9f50-2f0a2b6d9e11"


@dataclass
class BuilderSetup:
    user: Any
    workspace: Any
    table: Any
    name: Any
    status: Any
    amount: Any
    due: Any
    done_option: Any
    todo_option: Any
    data_source: Any


@pytest.fixture
def builder_setup(data_fixture) -> BuilderSetup:
    user = data_fixture.create_user(session_id=SESSION_ID)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    status = data_fixture.create_single_select_field(table=table, name="Status")
    done_option = data_fixture.create_select_option(field=status, value="Done")
    todo_option = data_fixture.create_select_option(field=status, value="Todo")
    amount = data_fixture.create_number_field(table=table, name="Amount")
    due = data_fixture.create_date_field(table=table, name="Due")

    builder = data_fixture.create_builder_application(workspace=workspace)
    page = data_fixture.create_builder_page(
        builder=builder,
        name="Task",
        path="/task/:id",
        path_params=[{"name": "id", "type": "numeric"}],
    )
    integration = data_fixture.create_local_baserow_integration(
        application=builder, user=user
    )
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, name="Tasks", table=table, integration=integration
    )
    return BuilderSetup(
        user,
        workspace,
        table,
        name,
        status,
        amount,
        due,
        done_option,
        todo_option,
        data_source,
    )


def raw(value: str) -> dict:
    return dict(BaserowFormulaObject.create(formula=value, mode="raw"))


def fake_profile(monkeypatch, answers: list[dict]):
    """
    Makes Kuma's model answer with each of the given final results in turn, and
    records the prompts it received.
    """

    received = []
    remaining = list(answers)

    def respond(messages, info):
        received.append(messages)
        return ModelResponse(
            parts=[
                ToolCallPart(
                    tool_name="final_result",
                    args=remaining.pop(0),
                    tool_call_id=f"result_{len(received)}",
                )
            ]
        )

    monkeypatch.setattr(
        model_profiles, "RetryingModel", lambda model_string: FunctionModel(respond)
    )
    profile = model_profiles.ResolvedAssistantModelProfile(
        model_string="openai:gpt-4.1-mini",
        source="explicit",
        workspace=None,
        database_model=None,
    )
    return profile, received


def persisted_filters(service) -> list[tuple]:
    return [
        (f.field_id, f.type, f.value["formula"], f.value["mode"], f.group_id)
        for f in LocalBaserowTableServiceFilter.objects.filter(
            service=service
        ).order_by("order")
    ]


# ---------------------------------------------------------------------------
# run_service_filter_request
# ---------------------------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_page_parameter_filter_is_saved_and_undoable(builder_setup, monkeypatch):
    s = builder_setup
    service = s.data_source.service.specific
    service.service_filters.create(
        field=s.amount, type="higher_than", value=raw("5"), order=0
    )
    profile, received = fake_profile(
        monkeypatch,
        [
            {
                "operations": [
                    {
                        "op": "add_filter",
                        "field_id": s.name.id,
                        "type": "equal",
                        "value": "get('page_parameter.id')",
                        "value_is_formula": True,
                    }
                ],
                "summary": "Added a filter on Name using the ID page parameter.",
            }
        ],
    )

    result = run_service_filter_request(
        ToolContext(s.user, s.workspace),
        "builder_data_source",
        s.data_source.id,
        "Create a filter on the `Name` field, the value is the `ID` page parameter",
        model_profile=profile,
    )

    assert result.changed is True
    assert result.summary == "Added a filter on Name using the ID page parameter."
    assert persisted_filters(service) == [
        (s.amount.id, "higher_than", "5", "raw", None),
        (s.name.id, "equal", "get('page_parameter.id')", "advanced", None),
    ]

    # The prompt describes the table, the current filters and the page parameter.
    prompt = received[0][0].parts[-1].content
    assert "Tasks" in prompt and str(s.done_option.id) in prompt
    assert '"page_parameter"' in prompt
    assert "higher_than" in prompt

    ActionHandler.undo(
        s.user,
        [action_type_registry.get("update_data_source").scope(s.data_source.page)],
        SESSION_ID,
    )
    assert persisted_filters(service) == [
        (s.amount.id, "higher_than", "5", "raw", None),
    ]


@pytest.mark.django_db
def test_invalid_answer_is_sent_back_to_the_agent(builder_setup, monkeypatch):
    s = builder_setup
    profile, received = fake_profile(
        monkeypatch,
        [
            {
                "operations": [
                    {
                        "op": "add_filter",
                        "field_id": s.status.id,
                        "type": "single_select_equal",
                        "value": "Done",
                    }
                ],
                "summary": "Added a filter.",
            },
            {
                "operations": [
                    {
                        "op": "add_filter",
                        "field_id": s.status.id,
                        "type": "single_select_equal",
                        "value": str(s.done_option.id),
                    }
                ],
                "summary": "Only showing done tasks.",
            },
        ],
    )

    result = run_service_filter_request(
        ToolContext(s.user, s.workspace),
        "builder_data_source",
        s.data_source.id,
        "only done tasks",
        model_profile=profile,
    )

    assert result.changed is True
    retry = [
        part for part in received[1][-1].parts if isinstance(part, RetryPromptPart)
    ]
    assert "invalid select option id(s)" in str(retry[0].content)
    assert persisted_filters(s.data_source.service) == [
        (s.status.id, "single_select_equal", str(s.done_option.id), "raw", None),
    ]


@pytest.mark.django_db
def test_agent_giving_up_raises_generation_failed(builder_setup, monkeypatch):
    s = builder_setup
    invalid = {
        "operations": [{"op": "delete_filter", "filter_id": "404"}],
        "summary": "Removed it.",
    }
    profile, _ = fake_profile(monkeypatch, [invalid] * 10)

    with pytest.raises(ServiceFilterGenerationFailed):
        run_service_filter_request(
            ToolContext(s.user, s.workspace),
            "builder_data_source",
            s.data_source.id,
            "remove the filter",
            model_profile=profile,
        )


@pytest.mark.django_db
def test_changes_no_longer_applying_raise_generation_failed(builder_setup, monkeypatch):
    s = builder_setup
    service = s.data_source.service.specific
    amount_filter = service.service_filters.create(
        field=s.amount, type="higher_than", value=raw("5"), order=0
    )

    def agent_while_the_filter_is_deleted(prompt, deps, model_profile):
        # Someone deletes the filter while Kuma works out how to change it.
        amount_filter.delete()
        return ServiceFilterChanges(
            operations=[
                FilterOperation(
                    op="update_filter", filter_id=str(amount_filter.id), value="10"
                )
            ],
            summary="Raised the Amount filter to 10.",
        )

    monkeypatch.setattr(
        kuma_handler, "run_service_filter_agent", agent_while_the_filter_is_deleted
    )

    with pytest.raises(ServiceFilterGenerationFailed):
        run_service_filter_request(
            ToolContext(s.user, s.workspace),
            "builder_data_source",
            s.data_source.id,
            "Amount above 10",
            model_profile=None,
        )
    assert persisted_filters(service) == []


@pytest.mark.django_db
def test_table_picked_in_the_editor_is_described_and_saved(
    builder_setup, data_fixture, monkeypatch
):
    s = builder_setup
    # A new data source: its table is picked in the editor, not saved yet.
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=s.data_source.page, integration=s.data_source.service.integration
    )
    profile, received = fake_profile(
        monkeypatch,
        [
            {
                "operations": [
                    {
                        "op": "add_filter",
                        "field_id": s.amount.id,
                        "type": "higher_than",
                        "value": "10",
                    }
                ],
                "summary": "Only rows with an Amount above 10.",
            }
        ],
    )

    result = run_service_filter_request(
        ToolContext(s.user, s.workspace),
        "builder_data_source",
        data_source.id,
        "Amount above 10",
        model_profile=profile,
        table_id=s.table.id,
    )

    assert result.changed is True
    assert "Amount" in received[0][0].parts[-1].content
    service = data_source.service.specific
    service.refresh_from_db()
    assert service.table_id == s.table.id
    assert persisted_filters(service) == [
        (s.amount.id, "higher_than", "10", "raw", None)
    ]


@pytest.mark.django_db
def test_no_operations_saves_nothing(builder_setup, monkeypatch):
    s = builder_setup
    profile, _ = fake_profile(
        monkeypatch,
        [{"operations": [], "summary": "There is no Priority field."}],
    )

    result = run_service_filter_request(
        ToolContext(s.user, s.workspace),
        "builder_data_source",
        s.data_source.id,
        "only high priority",
        model_profile=profile,
    )

    assert result.changed is False
    assert result.summary == "There is no Priority field."
    assert not Action.objects.filter(type="update_data_source").exists()


@pytest.mark.django_db
def test_groups_are_saved_and_linked(builder_setup, monkeypatch):
    s = builder_setup
    profile, _ = fake_profile(
        monkeypatch,
        [
            {
                "operations": [
                    {"op": "add_group", "group_id": "new_1", "filter_type": "OR"},
                    {
                        "op": "add_filter",
                        "field_id": s.amount.id,
                        "type": "higher_than",
                        "value": "100",
                        "group": "new_1",
                    },
                    {
                        "op": "add_filter",
                        "field_id": s.name.id,
                        "type": "contains",
                        "value": "urgent",
                        "group": "new_1",
                    },
                ],
                "summary": "Showing big or urgent tasks.",
            }
        ],
    )

    run_service_filter_request(
        ToolContext(s.user, s.workspace),
        "builder_data_source",
        s.data_source.id,
        "amount over 100 or name contains urgent",
        model_profile=profile,
    )

    group = LocalBaserowTableServiceFilterGroup.objects.get(
        service=s.data_source.service
    )
    assert group.filter_type == "OR"
    assert [f[4] for f in persisted_filters(s.data_source.service)] == [
        group.id,
        group.id,
    ]


@pytest.mark.django_db
def test_dashboard_data_source_filters_are_saved(data_fixture, monkeypatch):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Deals")
    amount = data_fixture.create_number_field(table=table, name="Amount")
    dashboard = data_fixture.create_dashboard_application(workspace=workspace)
    # Only the charts show filters, not the summary widgets.
    data_source = data_fixture.create_dashboard_data_source(
        dashboard=dashboard,
        service_model_class=LocalBaserowGroupedAggregateRows,
        table=table,
    )
    profile, received = fake_profile(
        monkeypatch,
        [
            {
                "operations": [
                    {
                        "op": "add_filter",
                        "field_id": amount.id,
                        "type": "higher_than",
                        "value": "1000",
                    }
                ],
                "summary": "Only counting deals above 1000.",
            }
        ],
    )

    result = run_service_filter_request(
        ToolContext(user, workspace),
        "dashboard_data_source",
        data_source.id,
        "deals over 1000",
        profile,
    )

    assert result.changed is True
    assert persisted_filters(data_source.service) == [
        (amount.id, "higher_than", "1000", "raw", None)
    ]
    prompt = received[0][0].parts[-1].content
    assert "can't be formulas here" in prompt
    assert "## Filter groups" in prompt


@pytest.mark.django_db
def test_automation_node_filters_can_read_previous_nodes(data_fixture, monkeypatch):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Orders")
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(
        user=user, automation=automation, create_trigger=False
    )
    trigger = data_fixture.create_local_baserow_rows_created_trigger_node(
        user=user, workflow=workflow, service_kwargs={"table": table}
    )
    node = data_fixture.create_local_baserow_get_row_action_node(
        user=user, workflow=workflow, service_kwargs={"table": table}
    )
    formula = f"get('previous_node.{trigger.id}.0.field_{name.id}')"
    profile, received = fake_profile(
        monkeypatch,
        [
            {
                "operations": [
                    {
                        "op": "add_filter",
                        "field_id": name.id,
                        "type": "equal",
                        "value": formula,
                        "value_is_formula": True,
                    }
                ],
                "summary": "Getting the row with the created row's name.",
            }
        ],
    )

    result = run_service_filter_request(
        ToolContext(user, workspace),
        "automation_node",
        node.id,
        "name equals the created row's name",
        profile,
    )

    assert result.changed is True
    assert persisted_filters(node.service) == [
        (name.id, "equal", formula, "advanced", None)
    ]
    assert "previous_node" in received[0][0].parts[-1].content


@pytest.mark.django_db
def test_request_checks_the_target(builder_setup, data_fixture):
    s = builder_setup
    profile = None

    other_user = data_fixture.create_user()
    with pytest.raises(PermissionException):
        run_service_filter_request(
            ToolContext(other_user, s.workspace),
            "builder_data_source",
            s.data_source.id,
            "x",
            profile,
        )

    other_workspace = data_fixture.create_workspace(user=s.user)
    with pytest.raises(ServiceFilterTargetDoesNotExist):
        run_service_filter_request(
            ToolContext(s.user, other_workspace),
            "builder_data_source",
            s.data_source.id,
            "x",
            profile,
        )

    with pytest.raises(ServiceFilterTargetDoesNotExist):
        run_service_filter_request(
            ToolContext(s.user, s.workspace), "builder_data_source", 0, "x", profile
        )

    with pytest.raises(ServiceFilterTargetDoesNotExist):
        run_service_filter_request(
            ToolContext(s.user, s.workspace), "unknown", s.data_source.id, "x", profile
        )

    without_table = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=s.data_source.page
    )
    with pytest.raises(ServiceFilterTargetNotSupported):
        run_service_filter_request(
            ToolContext(s.user, s.workspace),
            "builder_data_source",
            without_table.id,
            "x",
            profile,
        )

    TrashHandler.trash(
        s.user, s.workspace, s.data_source.page.builder, s.data_source.page.builder
    )
    with pytest.raises(ServiceFilterTargetDoesNotExist):
        run_service_filter_request(
            ToolContext(s.user, s.workspace),
            "builder_data_source",
            s.data_source.id,
            "x",
            profile,
        )


@pytest.mark.django_db
def test_request_refuses_services_without_filters(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    automation = data_fixture.create_automation_application(workspace=workspace)
    workflow = data_fixture.create_automation_workflow(user=user, automation=automation)
    node = data_fixture.create_local_baserow_create_row_action_node(
        user=user, workflow=workflow
    )

    with pytest.raises(ServiceFilterTargetNotSupported):
        run_service_filter_request(
            ToolContext(user, workspace), "automation_node", node.id, "x", None
        )
