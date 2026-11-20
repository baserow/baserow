"""
Keeps the tables of the test run data and the run history stored before the
tables they were built from were kept, so that who may see them no longer
depends on the formulas of today.

A periodic task fills them, as only the workers of the version that keeps the
tables run it, until a pass finds nothing left. A workflow is also filled before
one of its nodes, or of a workflow it starts, is edited or deleted, so an edit
can't come first, and after it is imported, as an export made before the tables
were kept has none.
"""

import time
from typing import Iterable, Optional

from django.conf import settings
from django.core.cache import cache
from django.db import transaction
from django.db.models import Q

from celery.exceptions import SoftTimeLimitExceeded
from loguru import logger

BACKFILL_BATCH_SIZE = 100

# How long one run of the periodic task fills, the rest is left for the next. A
# batch can still run after it, so it stays well under the task's time limit.
BACKFILL_TIME_LIMIT_SECONDS = max(settings.CELERY_TASK_SOFT_TIME_LIMIT // 2, 30)

# After this many failed runs, a workflow is left to the management command, so
# that it doesn't keep the fill from ever being done.
BACKFILL_MAX_ATTEMPTS = 3

# Set once a pass filled everything, so the task and the edits stop looking.
BACKFILL_DONE_CACHE_KEY = "automation_missing_table_ids_filled"

# Stored when a node, or a node it reads, had a table that no longer exists: who
# was allowed to see the data built from it can't be told any more, and no table
# has this ID, so nobody is shown that data.
MISSING_TABLE_ID = 0


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


def _lost_table(nodes) -> bool:
    """
    Whether one of the nodes has test run data built from a table that no longer
    exists: its table field is empty, as a deleted table leaves it. A node whose
    table was never picked has none.
    """

    for node in nodes:
        service = node.service.specific
        if (
            hasattr(service, "table_id")
            and service.table_id is None
            and service.sample_data is not None
        ):
            return True
    return False


def fill_workflow_table_ids(workflow) -> None:
    """
    Fills `sample_data_table_ids` of the services of the nodes of the workflow
    that have test run data and `read_table_ids` of their node histories, where
    they are missing, from what the formulas of the nodes read now, as the live
    dispatch would have stored them.
    """

    from baserow.contrib.automation.history.models import AutomationNodeHistory
    from baserow.contrib.automation.nodes.access import AutomationNodeAccess
    from baserow.core.services.models import Service

    access = AutomationNodeAccess(None, include_trashed=True)
    nodes = list(access.nodes_of_workflow(workflow).values())
    sample_table_ids, history_table_ids = {}, {}
    for node in nodes:
        lost = (
            {MISSING_TABLE_ID}
            if _lost_table([node, *access.read_nodes(node)])
            else set()
        )
        sample_table_ids[node.id] = sorted(access.sample_table_ids(node) | lost)
        history_table_ids[node.id] = sorted(access.dispatch_table_ids(node) | lost)
    with transaction.atomic():
        for node in nodes:
            Service.objects.filter(
                id=node.service_id,
                sample_data__isnull=False,
                sample_data_table_ids__isnull=True,
            ).update(sample_data_table_ids=sample_table_ids[node.id])
            AutomationNodeHistory.objects.filter(
                node_id=node.id, read_table_ids__isnull=True
            ).update(read_table_ids=history_table_ids[node.id])


def _attempts_cache_key(workflow_id: int) -> str:
    return f"automation_missing_table_ids_attempts_{workflow_id}"


def fill_missing_table_ids_batch(
    after_id: int = 0, limit: int = BACKFILL_BATCH_SIZE, give_up: bool = True
) -> tuple[Optional[int], int]:
    """
    Fills the missing table IDs of the next workflows after the given ID.

    :param give_up: Whether a workflow that failed too often is no longer counted
        as failed, so the fill can be done without it.
    :return: The ID of the last workflow of the batch, or None when there were
        none left, and how many workflows couldn't be filled.
    """

    workflows = list(
        _workflows_to_fill().filter(id__gt=after_id).order_by("id")[:limit]
    )
    failed = 0
    for workflow in workflows:
        try:
            fill_workflow_table_ids(workflow)
        except SoftTimeLimitExceeded:
            raise
        except Exception:  # noqa: BLE001
            # The workflow keeps the formula based check until the next pass, the
            # others are still filled.
            key = _attempts_cache_key(workflow.id)
            cache.add(key, 0, timeout=None)
            attempts = cache.incr(key)
            if give_up and attempts >= BACKFILL_MAX_ATTEMPTS:
                logger.exception(
                    f"Could not fill the table IDs of the workflow {workflow.id} "
                    f"after {attempts} attempts, run the fill_automation_table_ids "
                    "management command once it is fixed."
                )
            else:
                failed += 1
                logger.exception(
                    f"Could not fill the table IDs of the workflow {workflow.id}."
                )
    return (workflows[-1].id if workflows else None), failed


def fill_missing_table_ids(
    time_limit: Optional[float] = None, give_up: bool = True
) -> bool:
    """
    Fills the missing table IDs of every workflow, a batch at a time, and marks
    the fill done when a pass got through all of them.

    :param time_limit: The seconds after which no new batch is started.
    :param give_up: Whether the workflows that failed too often are left out.
    :return: Whether everything was filled.
    """

    if missing_table_ids_filled():
        return True
    started = time.monotonic()
    after_id, failed = 0, 0
    while True:
        after_id, batch_failed = fill_missing_table_ids_batch(after_id, give_up=give_up)
        failed += batch_failed
        if after_id is None:
            break
        if time_limit is not None and time.monotonic() - started > time_limit:
            return False
    if failed:
        logger.warning(
            f"The table IDs of {failed} workflows couldn't be filled, the next run "
            "tries again."
        )
        return False
    cache.set(BACKFILL_DONE_CACHE_KEY, True, timeout=None)
    return True


def missing_table_ids_filled() -> bool:
    return bool(cache.get(BACKFILL_DONE_CACHE_KEY))


def _needs_fill(workflow_id: int) -> bool:
    """
    Whether the workflow has test run data or, until the periodic fill is done,
    run history without the tables kept. Once it is done, only an import brings
    back test run data without them, and run history isn't imported.
    """

    from baserow.contrib.automation.history.models import AutomationNodeHistory
    from baserow.contrib.automation.nodes.models import AutomationNode

    return AutomationNode.objects_and_trash.filter(
        workflow_id=workflow_id,
        service__sample_data__isnull=False,
        service__sample_data_table_ids__isnull=True,
    ).exists() or (
        not missing_table_ids_filled()
        and AutomationNodeHistory.objects.filter(
            node__workflow_id=workflow_id, read_table_ids__isnull=True
        ).exists()
    )


def _starting_workflow_ids(workflow_ids: Iterable[int]) -> set[int]:
    """The workflows with a node that starts one of the given workflows."""

    from baserow.contrib.automation.nodes.models import AutomationNode
    from baserow.contrib.automation.workflows.models import AutomationWorkflow

    started = AutomationWorkflow.objects_and_trash.filter(
        Q(id__in=workflow_ids) | Q(automation__published_from_id__in=workflow_ids)
    ).values("id")
    return set(
        AutomationNode.objects_and_trash.filter(
            service__corestartworkflowservice__workflow_id__in=started
        ).values_list("workflow_id", flat=True)
    )


def fill_workflow_table_ids_before_edit(workflow) -> None:
    """
    Fills the missing table IDs of the workflow, and of the workflows that start
    it, as they count its tables, before one of its nodes is edited or deleted.
    Decided for each workflow, as missing IDs can come back after the periodic
    fill is done, from an import.
    """

    from baserow.contrib.automation.workflows.models import AutomationWorkflow

    to_check, checked = {workflow.id}, set()
    while to_check:
        checked |= to_check
        for workflow_id in to_check:
            if _needs_fill(workflow_id):
                fill_workflow_table_ids(
                    AutomationWorkflow.objects_and_trash.get(id=workflow_id)
                )
        to_check = _starting_workflow_ids(to_check) - checked


def fill_imported_workflows_table_ids(workflows) -> None:
    """Fills the missing table IDs of workflows just imported."""

    for workflow in workflows:
        if _needs_fill(workflow.id):
            fill_workflow_table_ids(workflow)
