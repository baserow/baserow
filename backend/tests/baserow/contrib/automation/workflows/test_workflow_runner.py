import pytest

from baserow.contrib.automation.automation_dispatch_context import (
    AutomationDispatchContext,
)
from baserow.contrib.automation.workflows.runner import AutomationWorkflowRunner


@pytest.mark.django_db
def test_run_workflow_with_create_row_action(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    integration = data_fixture.create_local_baserow_integration(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    trigger_table = data_fixture.create_database_table(database=database)
    action_table = data_fixture.create_database_table(database=database)
    action_table_field = data_fixture.create_text_field(table=action_table)
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_rows_created_service(
            table=trigger_table,
            integration=integration,
        ),
    )
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

    AutomationWorkflowRunner().run(workflow, AutomationDispatchContext(workflow, {}))

    row = action_table_model.objects.first()
    assert getattr(row, action_table_field.db_column) == "Horse"


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
    workflow = data_fixture.create_automation_workflow(user=user)
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_rows_created_service(
            table=trigger_table,
            integration=integration,
        ),
    )
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
    AutomationWorkflowRunner().run(workflow, AutomationDispatchContext(workflow, {}))

    action_table_row.refresh_from_db()
    assert getattr(action_table_row, action_table_field.db_column) == "Badger"


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
    workflow = data_fixture.create_automation_workflow(user=user, published=True)
    data_fixture.create_local_baserow_rows_created_trigger_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_rows_created_service(
            table=trigger_table,
            integration=integration,
        ),
    )
    data_fixture.create_local_baserow_delete_row_action_node(
        workflow=workflow,
        service=data_fixture.create_local_baserow_delete_row_service(
            table=action_table,
            integration=integration,
            row_id=action_table_row.id,
        ),
    )

    assert action_table.get_model().objects.all().count() == 1

    AutomationWorkflowRunner().run(workflow, AutomationDispatchContext(workflow, {}))

    assert action_table.get_model().objects.all().count() == 0
