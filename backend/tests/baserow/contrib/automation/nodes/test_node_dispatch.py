import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.nodes.handler import AutomationNodeHandler
from baserow.contrib.automation.workflows.constants import WorkflowState
from baserow.contrib.database.rows.handler import RowHandler


@pytest.mark.django_db
def test_run_workflow_with_create_row_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trigger_table = data_fixture.create_database_table(database=database)
    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    trigger_service = trigger.service.specific
    trigger_service.table = trigger_table
    trigger_service.integration = integration
    trigger_service.save()
    action_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_upsert_row_service(
            table=action_table,
            integration=integration,
        ),
    )
    action_node.service.field_mappings.create(field=action_table_field, value="'Horse'")

    action_table_model = action_table.get_model()
    assert action_table_model.objects.count() == 0

    dispatch_context = AutomationDispatchContext(workflow, {})
    AutomationNodeHandler().dispatch_node(workflow.get_trigger(), dispatch_context)

    row = action_table_model.objects.first()
    assert getattr(row, action_table_field.db_column) == "Horse"
    assert dispatch_context.dispatch_history == [trigger.id, action_node.id]


@pytest.mark.django_db(transaction=True)
def test_run_workflow_with_create_row_action_and_advanced_formula(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    trigger_table, trigger_table_fields, _ = data_fixture.build_table(
        user=user,
        columns=[
            ("Food", "text"),
            ("Spiciness", "number"),
        ],
        rows=[
            ["Paneer Tikka", 5],
            ["Gobi Manchurian", 8],
        ],
    )

    action_table, action_table_fields, action_rows = data_fixture.build_table(
        database=database,
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )
    workflow = data_fixture.create_automation_workflow(user, state="live")
    trigger = workflow.get_trigger()
    trigger_service = trigger.service.specific
    trigger_service.table = trigger_table
    trigger_service.integration = integration
    trigger_service.save()
    action_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_upsert_row_service(
            table=action_table,
            integration=integration,
        ),
    )
    action_node.service.field_mappings.create(
        field=action_table_fields[0],
        value=f"concat('The comparaison is ', "
        f"get('previous_node.{trigger.id}.0.{trigger_table_fields[1].db_column}') > 7)",
    )

    action_table_model = action_table.get_model()
    assert action_table_model.objects.count() == 0

    # Triggers a row creation
    RowHandler().create_rows(
        user=user,
        table=trigger_table,
        model=trigger_table.get_model(),
        rows_values=[
            {
                trigger_table_fields[0].db_column: "Spice",
                trigger_table_fields[1].db_column: "4.14",
            },
        ],
        skip_search_update=True,
    )

    row = action_table_model.objects.first()
    assert getattr(row, action_table_fields[0].db_column) == "The comparaison is false"


@pytest.mark.django_db
def test_run_workflow_with_update_row_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trigger_table = data_fixture.create_database_table(database=database)
    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)
    action_table_row = action_table.get_model().objects.create(
        **{f"field_{action_table_field.id}": "Horse"}
    )
    workflow = data_fixture.create_automation_workflow(user)
    trigger = workflow.get_trigger()
    trigger_service = trigger.service.specific
    trigger_service.table = trigger_table
    trigger_service.integration = integration
    trigger_service.save()
    action_node = data_fixture.create_local_baserow_update_row_action_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_upsert_row_service(
            table=action_table,
            integration=integration,
            row_id=action_table_row.id,
        ),
    )
    action_node.service.field_mappings.create(
        field=action_table_field, value="'Badger'"
    )

    dispatch_context = AutomationDispatchContext(workflow, {})
    AutomationNodeHandler().dispatch_node(workflow.get_trigger(), dispatch_context)

    action_table_row.refresh_from_db()
    assert getattr(action_table_row, action_table_field.db_column) == "Badger"
    assert dispatch_context.dispatch_history == [trigger.id, action_node.id]


@pytest.mark.django_db
def test_run_workflow_with_delete_row_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trigger_table = data_fixture.create_database_table(database=database)
    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)
    action_table_row = action_table.get_model().objects.create(
        **{f"field_{action_table_field.id}": "Mouse"}
    )
    workflow = data_fixture.create_automation_workflow(
        user=user, state=WorkflowState.LIVE
    )
    trigger = workflow.get_trigger()
    trigger_service = trigger.service.specific
    trigger_service.table = trigger_table
    trigger_service.integration = integration
    trigger_service.save()
    action_node = data_fixture.create_local_baserow_delete_row_action_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_delete_row_service(
            table=action_table,
            integration=integration,
            row_id=action_table_row.id,
        ),
    )

    assert action_table.get_model().objects.all().count() == 1

    dispatch_context = AutomationDispatchContext(workflow, {})
    AutomationNodeHandler().dispatch_node(workflow.get_trigger(), dispatch_context)

    assert action_table.get_model().objects.all().count() == 0
    assert dispatch_context.dispatch_history == [trigger.id, action_node.id]


@pytest.mark.django_db
def test_run_workflow_with_router_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trigger_table = data_fixture.create_database_table(database=database)
    workflow = data_fixture.create_automation_workflow(
        user=user,
        state=WorkflowState.LIVE,
        trigger_service_kwargs={"table": trigger_table, "integration": integration},
    )

    trigger = workflow.get_trigger()

    router_node = data_fixture.create_core_router_action_node(
        workflow=workflow,
    )

    data_fixture.create_core_router_service_edge(
        service=router_node.service, label="Edge 1", condition="'false'"
    )

    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)
    action_table_row = action_table.get_model().objects.create(
        **{f"field_{action_table_field.id}": "Horse"}
    )
    edge2 = data_fixture.create_core_router_service_edge(
        service=router_node.service,
        label="Edge 2",
        condition="'true'",
        skip_output_node=True,
    )
    edge2_output_node = data_fixture.create_local_baserow_update_row_action_node(
        workflow=workflow,
        reference_node=router_node,
        position="south",
        output=edge2.uid,
        service_kwargs={
            "table": action_table,
            "integration": integration,
            "row_id": action_table_row.id,
        },
    )
    edge2_output_node.service.field_mappings.create(
        field=action_table_field, value="'Badger'"
    )

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["router"]}},
            "router": {
                "next": {
                    "Edge 1": ["Edge 1 output node"],
                    "Edge 2": ["local_baserow_update_row"],
                }
            },
            "Edge 1 output node": {},
            "local_baserow_update_row": {},
        }
    )

    dispatch_context = AutomationDispatchContext(workflow, {})
    AutomationNodeHandler().dispatch_node(workflow.get_trigger(), dispatch_context)

    action_table_row.refresh_from_db()
    assert getattr(action_table_row, action_table_field.db_column) == "Badger"
    assert dispatch_context.dispatch_history == [
        trigger.id,
        router_node.id,
        edge2_output_node.id,
    ]


@pytest.fixture
def iterator_graph_fixture(data_fixture):
    """
    Fixture that creates the following graph:
    rows_created -> iterator [ -> create_row -> create_row3 ] -> create_row2

    trigger sample data are
    [
        {"field_1": "value 1", "field_2": "other 1"},
        {"field_1": "value 2", "field_2": "other 2"},
    ]
    """

    user = data_fixture.create_user()

    trigger_table, trigger_table_fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )

    action_table, action_table_fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )
    action2_table, action2_table_fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )
    action3_table, action3_table_fields, _ = data_fixture.build_table(
        user=user,
        columns=[("Name", "text")],
        rows=[],
    )

    integration = data_fixture.create_local_baserow_integration(user=user)

    workflow = data_fixture.create_automation_workflow(
        user=user,
        state=WorkflowState.LIVE,
        trigger_type="local_baserow_rows_created",
        trigger_service_kwargs={
            "table": trigger_table,
            "integration": integration,
            "sample_data": {
                "data": {
                    "results": [
                        {"field_1": "value 1", "field_2": "other 1"},
                        {"field_1": "value 2", "field_2": "other 2"},
                    ]
                }
            },
        },
    )

    trigger = workflow.get_trigger()

    iterator_node = data_fixture.create_core_iterator_action_node(
        workflow=workflow,
        reference_node=trigger,
        position="south",
        output="",
        service_kwargs={
            "source": f'get("previous_node.{trigger.id}")',
            "integration": integration,
        },
    )

    action_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        reference_node=iterator_node,
        position="child",
        output="",
        label="First action",
        service_kwargs={"table": action_table, "integration": integration},
    )
    action_node.service.specific.field_mappings.create(
        field=action_table_fields[0],
        value=f'get("current_iteration.{iterator_node.id}.item.field_1")',
    )

    action2_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        reference_node=iterator_node,
        position="south",
        output="",
        label="After iterator",
        service_kwargs={"table": action2_table, "integration": integration},
    )
    action2_node.service.specific.field_mappings.create(
        field=action2_table_fields[0],
        value=f'get("previous_node.{iterator_node.id}.*.field_1")',
    )

    action3_node = data_fixture.create_local_baserow_create_row_action_node(
        workflow=workflow,
        reference_node=action_node,
        position="south",
        output="",
        label="Second action",
        service_kwargs={"table": action3_table, "integration": integration},
    )
    action3_node.service.specific.field_mappings.create(
        field=action3_table_fields[0],
        value=f'get("current_iteration.{iterator_node.id}.item.field_2")',
    )

    return {
        "workflow": workflow,
        "action_node": action_node,
        "action_table": action_table,
        "action_table_fields": action_table_fields,
        "action2_table": action2_table,
        "action2_table_fields": action2_table_fields,
        "action3_table": action3_table,
        "action3_table_fields": action3_table_fields,
    }


@pytest.mark.django_db
def test_run_workflow_with_iterator_action(iterator_graph_fixture):
    workflow = iterator_graph_fixture["workflow"]
    action_table = iterator_graph_fixture["action_table"]
    action_table_fields = iterator_graph_fixture["action_table_fields"]
    action2_table = iterator_graph_fixture["action2_table"]
    action2_table_fields = iterator_graph_fixture["action2_table_fields"]
    action3_table = iterator_graph_fixture["action3_table"]
    action3_table_fields = iterator_graph_fixture["action3_table_fields"]

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["iterator"]}},
            "iterator": {
                "children": ["First action"],
                "next": {"": ["After iterator"]},
            },
            "First action": {"next": {"": ["Second action"]}},
            "Second action": {},
            "After iterator": {},
        }
    )

    dispatch_context = AutomationDispatchContext(
        workflow,
        {
            "results": [
                {"field_1": "value 1", "field_2": "other 1"},
                {"field_1": "value 2", "field_2": "other 2"},
            ]
        },
    )

    AutomationNodeHandler().dispatch_node(workflow.get_trigger(), dispatch_context)

    # At this point all node should have been executed
    rows = list(action_table.get_model().objects.all())
    assert len(rows) == 2

    assert getattr(rows[0], action_table_fields[0].db_column) == "value 1"
    assert getattr(rows[1], action_table_fields[0].db_column) == "value 2"

    rows2 = list(action2_table.get_model().objects.all())
    assert len(rows2) == 1
    assert getattr(rows2[0], action2_table_fields[0].db_column) == "value 1,value 2"

    rows3 = list(action3_table.get_model().objects.all())
    assert len(rows3) == 2

    assert getattr(rows3[0], action3_table_fields[0].db_column) == "other 1"
    assert getattr(rows3[1], action3_table_fields[0].db_column) == "other 2"


@pytest.mark.django_db
def test_run_workflow_with_iterator_action_simulate(iterator_graph_fixture):
    workflow = iterator_graph_fixture["workflow"]
    action_node = iterator_graph_fixture["action_node"]
    action_table = iterator_graph_fixture["action_table"]
    action_table_fields = iterator_graph_fixture["action_table_fields"]
    action2_table = iterator_graph_fixture["action2_table"]
    action3_table = iterator_graph_fixture["action3_table"]

    workflow.assert_reference(
        {
            "0": "local_baserow_rows_created",
            "local_baserow_rows_created": {"next": {"": ["iterator"]}},
            "iterator": {
                "children": ["First action"],
                "next": {"": ["After iterator"]},
            },
            "First action": {"next": {"": ["Second action"]}},
            "Second action": {},
            "After iterator": {},
        }
    )

    dispatch_context = AutomationDispatchContext(
        workflow,
        simulate_until_node=action_node,
    )
    AutomationNodeHandler().dispatch_node(workflow.get_trigger(), dispatch_context)

    # At this point only nodes until the action_node should have been executed
    rows = list(action_table.get_model().objects.all())
    assert len(rows) == 1

    assert getattr(rows[0], action_table_fields[0].db_column) == "value 1"

    rows2 = list(action2_table.get_model().objects.all())
    assert len(rows2) == 0

    rows3 = list(action3_table.get_model().objects.all())
    assert len(rows3) == 0
