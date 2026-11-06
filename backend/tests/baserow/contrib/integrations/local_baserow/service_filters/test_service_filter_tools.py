"""
Tests for the service filter tools shared by Kuma and MCP, and for the target types
of the builder, dashboards and automations they rely on.
"""

import json
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.builder.data_sources.models import DataSource
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableServiceFilter,
)
from baserow.contrib.integrations.local_baserow.service_filters.exceptions import (
    ServiceFilterTargetDoesNotExist,
    ServiceFilterTargetNotSupported,
)
from baserow.contrib.integrations.local_baserow.service_filters.handler import (
    prepare_service_filters,
    resolve_service_filter_target,
    save_service_filter_operations,
)
from baserow.contrib.integrations.local_baserow.service_filters.registries import (
    service_filter_target_type_registry,
)
from baserow.contrib.integrations.local_baserow.service_filters.state import (
    FilterOperation,
)
from baserow.contrib.integrations.local_baserow.service_filters.tools import (
    list_filterable_data_sources,
    list_service_filters,
    update_service_filters,
)
from baserow.core.action.handler import ActionHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.groups import (
    AREA_DATA_SOURCES,
    GROUP_DATA_SOURCES_EDIT,
    GROUP_DATA_SOURCES_READ,
    mcp_tool_group_registry,
)
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.tools import ToolContext

SESSION_ID = "8c0f5e7a-0d43-4c5c-9b0e-0f1b7a3c2d11"


@dataclass
class Workspace:
    user: Any
    workspace: Any
    table: Any
    name: Any
    amount: Any
    done_option: Any
    data_source: Any
    dashboard_data_source: Any
    trigger: Any
    node: Any
    other_node: Any


@pytest.fixture
def seeded(data_fixture) -> Workspace:
    user = data_fixture.create_user(session_id=SESSION_ID)
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database, name="Tasks")
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    status = data_fixture.create_single_select_field(table=table, name="Status")
    done_option = data_fixture.create_select_option(field=status, value="Done")
    amount = data_fixture.create_number_field(table=table, name="Amount")

    builder = data_fixture.create_builder_application(
        workspace=workspace, name="Portal"
    )
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
    # Without a table, there is nothing to filter.
    data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=page, name="Empty", integration=integration
    )

    dashboard = data_fixture.create_dashboard_application(
        workspace=workspace, name="KPIs"
    )
    dashboard_data_source = (
        data_fixture.create_dashboard_local_baserow_aggregate_rows_data_source(
            dashboard=dashboard, table=table
        )
    )
    data_fixture.create_summary_widget(
        dashboard=dashboard, title="Task count", data_source=dashboard_data_source
    )

    automation = data_fixture.create_automation_application(
        workspace=workspace, name="Ops"
    )
    workflow = data_fixture.create_automation_workflow(
        user=user, automation=automation, name="Flow", create_trigger=False
    )
    trigger = data_fixture.create_local_baserow_rows_created_trigger_node(
        user=user, workflow=workflow, service_kwargs={"table": table}
    )
    node = data_fixture.create_local_baserow_get_row_action_node(
        user=user, workflow=workflow, service_kwargs={"table": table}, label="Get"
    )
    other_node = data_fixture.create_local_baserow_get_row_action_node(
        user=user, workflow=workflow, service_kwargs={"table": table}, label="Later"
    )
    # Creating rows can't be filtered.
    data_fixture.create_local_baserow_create_row_action_node(
        user=user, workflow=workflow
    )

    return Workspace(
        user,
        workspace,
        table,
        name,
        amount,
        done_option,
        data_source,
        dashboard_data_source,
        trigger,
        node,
        other_node,
    )


def ctx(seeded: Workspace, user=None) -> ToolContext:
    return ToolContext(user=user or seeded.user, workspace=seeded.workspace)


def filters_of(service) -> list[tuple]:
    return [
        (f.field_id, f.type, f.value["formula"], f.value["mode"])
        for f in LocalBaserowTableServiceFilter.objects.filter(
            service=service
        ).order_by("order")
    ]


def add(field_id, type, value, value_is_formula=False, group=None) -> dict:
    return {
        "op": "add_filter",
        "field_id": field_id,
        "type": type,
        "value": value,
        "value_is_formula": value_is_formula,
        "group": group,
    }


@contextmanager
def rejected(text: str):
    """Expects the call to be rejected with a message containing the text."""

    with pytest.raises(DjangoValidationError) as exc:
        yield
    assert text in " ".join(exc.value.messages)


def ops(*operations: dict) -> list[FilterOperation]:
    """The operations as the clients pass them, validated."""

    return [FilterOperation(**operation) for operation in operations]


@pytest.mark.django_db
def test_list_filterable_data_sources(seeded, data_fixture):
    # Not listed: another workspace's data sources, and summary widgets which
    # have no filters.
    other_builder = data_fixture.create_builder_application(
        workspace=data_fixture.create_workspace()
    )
    data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=data_fixture.create_builder_page(builder=other_builder),
        table=seeded.table,
    )

    result = list_filterable_data_sources(ctx(seeded))

    items = {(item["kind"], item["name"]): item for item in result["data_sources"]}
    assert set(items) == {
        ("builder_data_source", "Tasks"),
        ("automation_node", "Get"),
        ("automation_node", "Later"),
    }
    assert items[("builder_data_source", "Tasks")] == {
        "kind": "builder_data_source",
        "id": seeded.data_source.id,
        "name": "Tasks",
        "application": {
            "id": seeded.data_source.page.builder_id,
            "name": "Portal",
            "type": "builder",
        },
        "location": "Task",
        "service_type": "local_baserow_list_rows",
        "table_id": seeded.table.id,
        "filter_count": 0,
    }
    assert items[("automation_node", "Get")]["location"] == "Flow"
    assert result["total"] == 3
    assert result["has_more"] is False

    only_automation = list_filterable_data_sources(
        ctx(seeded), application_id=seeded.node.workflow.automation_id
    )
    assert {item["kind"] for item in only_automation["data_sources"]} == {
        "automation_node"
    }

    with pytest.raises(ApplicationDoesNotExist):
        list_filterable_data_sources(ctx(seeded), application_id=0)


@pytest.mark.django_db
def test_list_service_filters_describes_what_can_be_changed(seeded):
    result = list_service_filters(
        ctx(seeded), "builder_data_source", seeded.data_source.id
    )

    fields = {field["name"]: field for field in result["table"]["fields"]}
    assert set(fields) >= {"Name", "Status", "Amount"}
    status = fields["Status"]
    assert status["select_options"] == [{"id": seeded.done_option.id, "value": "Done"}]
    assert "single_select_equal" in result["filter_type_sets"][status["filter_types"]]
    assert "page_parameter" in result["formula_values"]
    assert result["supports_filter_groups"] is True
    assert result["filters"] == [] and result["filter_type"] == "AND"


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_update_service_filters_saves_and_can_be_undone(seeded):
    result = update_service_filters(
        ctx(seeded),
        "builder_data_source",
        seeded.data_source.id,
        ops(
            add(seeded.name.id, "equal", "get('page_parameter.id')", True),
            add(seeded.amount.id, "higher_than", "10"),
        ),
    )

    assert result["changed"] is True
    assert [f["field_name"] for f in result["filters"]] == ["Name", "Amount"]
    assert filters_of(seeded.data_source.service) == [
        (seeded.name.id, "equal", "get('page_parameter.id')", "advanced"),
        (seeded.amount.id, "higher_than", "10", "raw"),
    ]

    ActionHandler.undo(
        seeded.user,
        [action_type_registry.get("update_data_source").scope(seeded.data_source.page)],
        SESSION_ID,
    )
    assert filters_of(seeded.data_source.service) == []


@pytest.mark.django_db
def test_update_service_filters_rejects_invalid_operations(seeded):
    with pytest.raises(DjangoValidationError) as exc:
        update_service_filters(
            ctx(seeded),
            "builder_data_source",
            seeded.data_source.id,
            ops(
                add(seeded.amount.id, "contains_word", "1"),
                add(seeded.name.id, "equal", "get('form_data.1')", True),
                add(seeded.name.id, "equal", "get('page_parameter.slug')", True),
            ),
        )

    messages = " ".join(exc.value.messages)
    assert "'contains_word' can't be used on field 'Amount'" in messages
    assert "can't read 'form_data'" in messages
    assert "'slug' is not a parameter of the page" in messages
    # Nothing is saved when one operation is invalid.
    assert filters_of(seeded.data_source.service) == []

    with rejected("is not a kind"):
        update_service_filters(ctx(seeded), "nope", 1, ops(add(1, "equal", "x")))

    empty = DataSource.objects.get(page=seeded.data_source.page, name="Empty")
    with rejected("Select a table"):
        update_service_filters(
            ctx(seeded), "builder_data_source", empty.id, ops(add(1, "equal", "x"))
        )


@pytest.mark.django_db
def test_update_service_filters_stays_in_the_workspace(seeded, data_fixture):
    other_workspace = data_fixture.create_workspace(user=seeded.user)
    with pytest.raises(ServiceFilterTargetDoesNotExist):
        update_service_filters(
            ToolContext(user=seeded.user, workspace=other_workspace),
            "builder_data_source",
            seeded.data_source.id,
            ops(add(seeded.amount.id, "higher_than", "1")),
        )

    stranger = data_fixture.create_user()
    with pytest.raises(PermissionException):
        update_service_filters(
            ctx(seeded, user=stranger),
            "builder_data_source",
            seeded.data_source.id,
            ops(add(seeded.amount.id, "higher_than", "1")),
        )


@pytest.mark.django_db
def test_summary_widget_filters_cannot_be_changed(seeded):
    # The summary widget's form doesn't show filters. The charts' filters are
    # tested with the premium charts.
    with rejected("Summary widgets don't have filters"):
        list_service_filters(
            ctx(seeded), "dashboard_data_source", seeded.dashboard_data_source.id
        )
    with rejected("Summary widgets don't have filters"):
        update_service_filters(
            ctx(seeded),
            "dashboard_data_source",
            seeded.dashboard_data_source.id,
            ops(add(seeded.amount.id, "higher_than", "1")),
        )
    assert filters_of(seeded.dashboard_data_source.service) == []


@pytest.mark.django_db
def test_published_copies_are_not_found(seeded, data_fixture):
    # Publishing copies the application without a workspace.
    published_builder = data_fixture.create_builder_application(workspace=None)
    published_data_source = (
        data_fixture.create_builder_local_baserow_list_rows_data_source(
            page=data_fixture.create_builder_page(builder=published_builder),
            table=seeded.table,
        )
    )
    published_workflow = data_fixture.create_automation_workflow(
        user=seeded.user,
        automation=data_fixture.create_automation_application(workspace=None),
        create_trigger=False,
    )
    data_fixture.create_local_baserow_rows_created_trigger_node(
        user=seeded.user,
        workflow=published_workflow,
        service_kwargs={"table": seeded.table},
    )
    published_node = data_fixture.create_local_baserow_get_row_action_node(
        user=seeded.user,
        workflow=published_workflow,
        service_kwargs={"table": seeded.table},
    )

    for kind, target_id in (
        ("builder_data_source", published_data_source.id),
        ("automation_node", published_node.id),
    ):
        with pytest.raises(ServiceFilterTargetDoesNotExist):
            list_service_filters(ctx(seeded), kind, target_id)


@pytest.mark.django_db
def test_filters_saved_meanwhile_are_kept(seeded):
    target = resolve_service_filter_target(
        ctx(seeded), "builder_data_source", seeded.data_source.id
    )
    prepared = prepare_service_filters(ctx(seeded), target)
    # Saved by someone else after the filters were read, e.g. while an agent
    # worked out the operations.
    target.service.service_filters.create(
        field=seeded.amount,
        type="higher_than",
        value={"formula": "10", "mode": "raw"},
        order=0,
    )

    changed, state = save_service_filter_operations(
        ctx(seeded), prepared, ops(add(seeded.name.id, "equal", "Bob"))
    )

    assert changed is True
    assert filters_of(seeded.data_source.service) == [
        (seeded.amount.id, "higher_than", "10", "raw"),
        (seeded.name.id, "equal", "Bob", "raw"),
    ]
    assert [f.field_id for f in state.filters] == [seeded.amount.id, seeded.name.id]


@pytest.mark.django_db
def test_automation_filters_only_read_previous_nodes(seeded):
    trigger_value = f"get('previous_node.{seeded.trigger.id}.0.field_{seeded.name.id}')"
    result = update_service_filters(
        ctx(seeded),
        "automation_node",
        seeded.node.id,
        ops(add(seeded.name.id, "equal", trigger_value, True)),
    )
    assert result["changed"] is True

    later_value = f"get('previous_node.{seeded.other_node.id}.field_{seeded.name.id}')"
    with rejected("doesn't run before this node"):
        update_service_filters(
            ctx(seeded),
            "automation_node",
            seeded.node.id,
            ops(add(seeded.name.id, "equal", later_value, True)),
        )

    with rejected("is not an output of node"):
        update_service_filters(
            ctx(seeded),
            "automation_node",
            seeded.node.id,
            ops(
                add(
                    seeded.name.id,
                    "equal",
                    f"get('previous_node.{seeded.trigger.id}.0.field_0')",
                    True,
                )
            ),
        )


def test_every_target_type_belongs_to_an_application_type():
    from baserow.core.registries import application_type_registry

    for target_type in service_filter_target_type_registry.get_all():
        assert application_type_registry.get(target_type.application_type)


def test_data_source_mcp_tool_groups():
    groups = {tool.name: tool.group for tool in mcp_tool_registry.get_all()}
    assert groups["list_filterable_data_sources"] == GROUP_DATA_SOURCES_READ
    assert groups["list_service_filters"] == GROUP_DATA_SOURCES_READ
    assert groups["update_service_filters"] == GROUP_DATA_SOURCES_EDIT
    for group in (GROUP_DATA_SOURCES_READ, GROUP_DATA_SOURCES_EDIT):
        assert mcp_tool_group_registry.get(group).area == AREA_DATA_SOURCES


def _session(endpoint, callback):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await callback(client)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


@pytest.mark.django_db
def test_update_service_filters_over_mcp(data_fixture, seeded):
    endpoint = data_fixture.create_mcp_endpoint(
        user=seeded.user,
        workspace=seeded.workspace,
        allowed_tools=["update_service_filters"],
    )

    async def callback(client):
        listed = await client.list_tools()
        saved = await client.call_tool(
            "update_service_filters",
            {
                "kind": "builder_data_source",
                "id": seeded.data_source.id,
                "operations": [add(seeded.amount.id, "higher_than", "10")],
            },
        )
        rejected = await client.call_tool(
            "update_service_filters",
            {
                "kind": "builder_data_source",
                "id": seeded.data_source.id,
                "operations": [add(seeded.amount.id, "contains_word", "10")],
            },
        )
        return listed, saved, rejected

    listed, saved, rejected = _session(endpoint, callback)

    tool = next(t for t in listed.tools if t.name == "update_service_filters")
    assert tool.annotations.destructiveHint is True
    assert set(tool.inputSchema["properties"]) == {"kind", "id", "operations"}
    assert "## Values" in tool.description
    assert saved.isError is False
    assert json.loads(saved.content[0].text)["changed"] is True
    assert rejected.isError is True
    assert "can't be used on field 'Amount'" in rejected.content[0].text
    assert filters_of(seeded.data_source.service) == [
        (seeded.amount.id, "higher_than", "10", "raw")
    ]


@pytest.mark.django_db
@pytest.mark.undo_redo
def test_table_picked_for_a_data_source_without_one_is_saved_with_the_filters(
    seeded, data_fixture
):
    # The table is picked in the editor, but not saved yet.
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=seeded.data_source.page,
        integration=seeded.data_source.service.integration,
    )
    target = resolve_service_filter_target(
        ctx(seeded), "builder_data_source", data_source.id, table_id=seeded.table.id
    )
    assert target.saves_table is True
    prepared = prepare_service_filters(ctx(seeded), target)
    assert seeded.amount.id in prepared.fields

    changed, _ = save_service_filter_operations(
        ctx(seeded), prepared, ops(add(seeded.amount.id, "higher_than", "10"))
    )

    service = data_source.service.specific
    service.refresh_from_db()
    assert changed is True
    assert service.table_id == seeded.table.id
    assert filters_of(service) == [(seeded.amount.id, "higher_than", "10", "raw")]

    # One change: undoing it removes the table and the filters.
    ActionHandler.undo(
        seeded.user,
        [action_type_registry.get("update_data_source").scope(data_source.page)],
        SESSION_ID,
    )
    service.refresh_from_db()
    assert service.table_id is None
    assert filters_of(service) == []


@pytest.mark.django_db
def test_table_picked_in_the_editor_is_checked(seeded, data_fixture):
    data_source = data_fixture.create_builder_local_baserow_list_rows_data_source(
        page=seeded.data_source.page,
        integration=seeded.data_source.service.integration,
    )
    other_table = data_fixture.create_database_table(user=seeded.user)
    with pytest.raises(ServiceFilterTargetNotSupported, match="does not exist"):
        resolve_service_filter_target(
            ctx(seeded), "builder_data_source", data_source.id, table_id=other_table.id
        )

    # A data source with a saved table keeps it: another one must be saved first,
    # as changing the table drops the filters.
    another_table = data_fixture.create_database_table(database=seeded.table.database)
    with pytest.raises(ServiceFilterTargetNotSupported, match="Save the new table"):
        resolve_service_filter_target(
            ctx(seeded),
            "builder_data_source",
            seeded.data_source.id,
            table_id=another_table.id,
        )
    same = resolve_service_filter_target(
        ctx(seeded),
        "builder_data_source",
        seeded.data_source.id,
        table_id=seeded.table.id,
    )
    assert same.saves_table is False and same.table.id == seeded.table.id
