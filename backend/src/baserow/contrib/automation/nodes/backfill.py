"""
Keeps the tables of the test run data and the run history stored before the
tables they were built from were kept, so that who may see them no longer
depends on the formulas of today.
"""

from typing import Optional

from django.db.models import Q

from loguru import logger

# The migration that adds the last of the columns, after the one on services.
BACKFILL_AFTER_MIGRATION = ("automation", "0046_node_history_read_table_ids")

# Filling starts after the backends of the previous version stopped, so what they
# stored meanwhile gets the tables too.
BACKFILL_COUNTDOWN = 5 * 60

BACKFILL_BATCH_SIZE = 100


def _workflows_to_fill():
    from baserow.contrib.automation.history.models import AutomationNodeHistory
    from baserow.contrib.automation.nodes.models import AutomationNode
    from baserow.contrib.automation.workflows.models import AutomationWorkflow

    with_samples = AutomationNode.objects_and_trash.filter(
        service__sample_data__isnull=False,
        service__sample_data_table_ids__isnull=True,
    ).values("workflow_id")
    with_histories = AutomationNodeHistory.objects.filter(
        read_table_ids__isnull=True
    ).values("node__workflow_id")
    return AutomationWorkflow.objects_and_trash.filter(
        Q(id__in=with_samples) | Q(id__in=with_histories)
    )


def fill_missing_table_ids_batch(
    after_id: int = 0, limit: int = BACKFILL_BATCH_SIZE
) -> Optional[int]:
    """
    Fills `sample_data_table_ids` of the services of automation nodes that have
    test run data and `read_table_ids` of the node histories, where they are
    missing, from what the formulas of the nodes read now, for the next workflows
    after the given ID. A later edit of a formula, delete of a node or delete of
    a table then no longer shows that data to a user who may not see the tables
    it was built from.

    :return: The ID of the last workflow of the batch, or None when there were
        none left.
    """

    from baserow.contrib.automation.history.models import AutomationNodeHistory
    from baserow.contrib.automation.nodes.access import AutomationNodeAccess
    from baserow.core.services.models import Service

    workflows = list(
        _workflows_to_fill().filter(id__gt=after_id).order_by("id")[:limit]
    )
    for workflow in workflows:
        access = AutomationNodeAccess(None, include_trashed=True)
        try:
            nodes = list(access.nodes_of_workflow(workflow).values())
            table_ids = {
                node.id: sorted(access.dispatch_table_ids(node)) for node in nodes
            }
        except Exception:  # noqa: BLE001
            # A workflow that can't be read keeps the formula based check, the
            # others are still filled.
            logger.exception(
                f"Could not fill the table IDs of the workflow {workflow.id}."
            )
            continue
        for node in nodes:
            Service.objects.filter(
                id=node.service_id,
                sample_data__isnull=False,
                sample_data_table_ids__isnull=True,
            ).update(sample_data_table_ids=table_ids[node.id])
            AutomationNodeHistory.objects.filter(
                node_id=node.id, read_table_ids__isnull=True
            ).update(read_table_ids=table_ids[node.id])
    return workflows[-1].id if workflows else None


def fill_missing_table_ids_after_migrate(plan=None, **kwargs):
    """
    A `post_migrate` receiver that queues the filling of the table IDs when the
    migrate applied the migrations adding them.
    """

    from baserow.contrib.automation.nodes.tasks import fill_missing_table_ids_task

    applied = {
        (migration.app_label, migration.name)
        for migration, backwards in plan or ()
        if not backwards
    }
    if BACKFILL_AFTER_MIGRATION in applied:
        fill_missing_table_ids_task.apply_async(countdown=BACKFILL_COUNTDOWN)
