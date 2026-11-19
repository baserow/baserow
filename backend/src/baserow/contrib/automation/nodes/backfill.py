"""
Keeps the tables of the test run data and the run history stored before the
tables they were built from were kept, so that who may see them no longer
depends on the formulas of today.
"""

from django.db.models import Q

from loguru import logger

# The migrations that add the columns. The backfill runs once, after the
# migrate that applies them, when the code and the schema are those of today.
BACKFILL_AFTER_MIGRATIONS = {
    ("automation", "0046_node_history_read_table_ids"),
    ("core", "0141_service_sample_data_table_ids"),
}


def fill_missing_table_ids() -> int:
    """
    Fills `sample_data_table_ids` of the services of automation nodes that have
    test run data and `read_table_ids` of the node histories, where they are
    missing, from what the formulas of the nodes read now. A later edit of a
    formula, delete of a node or delete of a table then no longer shows that
    data to a user who may not see the tables it was built from.

    :return: The number of workflows that were filled.
    """

    from baserow.contrib.automation.history.models import AutomationNodeHistory
    from baserow.contrib.automation.nodes.access import AutomationNodeAccess
    from baserow.contrib.automation.nodes.models import AutomationNode
    from baserow.contrib.automation.workflows.models import AutomationWorkflow
    from baserow.core.services.models import Service

    workflow_ids = set(
        AutomationNode.objects_and_trash.filter(
            Q(
                service__sample_data__isnull=False,
                service__sample_data_table_ids__isnull=True,
            )
            | Q(node_histories__read_table_ids__isnull=True)
        )
        .values_list("workflow_id", flat=True)
        .distinct()
    )

    filled = 0
    for workflow in AutomationWorkflow.objects_and_trash.filter(
        id__in=workflow_ids
    ).iterator(chunk_size=200):
        try:
            _fill_workflow(
                workflow,
                AutomationNodeAccess(None, include_trashed=True),
                Service,
                AutomationNodeHistory,
            )
            filled += 1
        except Exception:  # noqa: BLE001
            # One workflow that can't be read keeps the formula based check,
            # the others are still filled.
            logger.exception(
                f"Could not fill the table IDs of the workflow {workflow.id}."
            )
    return filled


def _fill_workflow(workflow, access, service_model, history_model):
    for node in access.nodes_of_workflow(workflow).values():
        table_ids = sorted(access.dispatch_table_ids(node))
        service_model.objects.filter(
            id=node.service_id,
            sample_data__isnull=False,
            sample_data_table_ids__isnull=True,
        ).update(sample_data_table_ids=table_ids)
        history_model.objects.filter(
            node_id=node.id, read_table_ids__isnull=True
        ).update(read_table_ids=table_ids)


def fill_missing_table_ids_after_migrate(plan=None, **kwargs):
    """
    A `post_migrate` receiver that fills the table IDs when the migrate applied
    the migrations adding them.
    """

    applied = {
        (migration.app_label, migration.name)
        for migration, backwards in plan or ()
        if not backwards
    }
    if applied & BACKFILL_AFTER_MIGRATIONS:
        filled = fill_missing_table_ids()
        if filled:
            logger.info(f"Filled the table IDs of {filled} automation workflows.")
