import pytest


@pytest.mark.once_per_day_in_ci
def test_0013_apply_previous_node_ids_forwards(migrator):
    migrate_from = [
        ("automation", "0012_get_list_aggregate_rows_nodes"),
        ("integrations", "0016_coresmtpemailservice_smtpintegration"),
    ]
    migrate_to = [
        ("automation", "0013_apply_previous_node_ids"),
    ]

    old_state = migrator.migrate(migrate_from)

    ContentType = old_state.apps.get_model("contenttypes", "ContentType")
    Workspace = old_state.apps.get_model("core", "Workspace")
    Automation = old_state.apps.get_model("automation", "Automation")
    AutomationWorkflow = old_state.apps.get_model("automation", "AutomationWorkflow")
    LocalBaserowGetRowActionNode = old_state.apps.get_model(
        "automation", "LocalBaserowGetRowActionNode"
    )
    LocalBaserowRowsCreated = old_state.apps.get_model(
        "integrations", "LocalBaserowRowsCreated"
    )
    LocalBaserowGetRow = old_state.apps.get_model("integrations", "LocalBaserowGetRow")
    LocalBaserowRowsCreatedTriggerNode = old_state.apps.get_model(
        "automation", "LocalBaserowRowsCreatedTriggerNode"
    )

    workspace = Workspace.objects.create(name="Workspace")
    automation = Automation.objects.create(
        order=1,
        name="Automation",
        workspace=workspace,
        content_type=ContentType.objects.get(
            app_label="automation", model="automation"
        ),
    )
    workflow = AutomationWorkflow.objects.create(
        order=1,
        name="Workflow",
        automation=automation,
    )
    trigger = LocalBaserowRowsCreatedTriggerNode.objects.create(
        order=1,
        previous_node_id=None,
        workflow=workflow,
        service=LocalBaserowRowsCreated.objects.create(
            content_type=ContentType.objects.get_for_model(LocalBaserowRowsCreated)
        ),
        content_type=ContentType.objects.get_for_model(
            LocalBaserowRowsCreatedTriggerNode
        ),
    )
    assert trigger.previous_node_id is None
    node1 = LocalBaserowGetRowActionNode.objects.create(
        order=2,
        previous_node_id=None,
        workflow=workflow,
        service=LocalBaserowGetRow.objects.create(
            content_type=ContentType.objects.get_for_model(LocalBaserowGetRow)
        ),
        content_type=ContentType.objects.get_for_model(LocalBaserowGetRowActionNode),
    )
    assert node1.previous_node_id is None
    node2 = LocalBaserowGetRowActionNode.objects.create(
        order=3,
        previous_node_id=None,
        workflow=workflow,
        service=LocalBaserowGetRow.objects.create(
            content_type=ContentType.objects.get_for_model(LocalBaserowGetRow)
        ),
        content_type=ContentType.objects.get_for_model(LocalBaserowGetRowActionNode),
    )
    assert node2.previous_node_id is None
    node3 = LocalBaserowGetRowActionNode.objects.create(
        order=4,
        previous_node_id=None,
        workflow=workflow,
        service=LocalBaserowGetRow.objects.create(
            content_type=ContentType.objects.get_for_model(LocalBaserowGetRow)
        ),
        content_type=ContentType.objects.get_for_model(LocalBaserowGetRowActionNode),
    )
    assert node3.previous_node_id is None

    new_state = migrator.migrate(migrate_to)

    AutomationNode = new_state.apps.get_model("automation", "AutomationNode")

    trigger = AutomationNode.objects.get(id=trigger.id)
    assert trigger.previous_node_id is None

    node1 = AutomationNode.objects.get(id=node1.id)
    assert node1.previous_node_id == trigger.id

    node2 = AutomationNode.objects.get(id=node2.id)
    assert node2.previous_node_id == node1.id

    node3 = AutomationNode.objects.get(id=node3.id)
    assert node3.previous_node_id == node2.id
