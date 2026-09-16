from django.db.models import Exists, OuterRef, Q, QuerySet

from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowDeleteRow,
    LocalBaserowTableServiceFieldMapping,
    LocalBaserowUpsertRow,
)


def _unusable_table() -> Q:
    """
    A row service whose table is gone, trashed, or in a trashed database. The
    dispatch refuses all three (`resolve_service_formulas`).
    """

    return (
        Q(table__isnull=True)
        | Q(table__trashed=True)
        | Q(table__database__trashed=True)
    )


def workflow_actions_requiring_reconfiguration() -> QuerySet[DatabaseWorkflowAction]:
    """
    The row actions that are sure to fail at click time because something they
    reference is in the trash or gone (ADR 006 section 8). Used both to
    annotate button fields in bulk and to answer for a single one, so the two
    can't drift apart.

    A mapping on a trashed field only counts without an integration: with one,
    the dispatch drops the mapping rather than failing.
    """

    mapping_on_trashed_field = Exists(
        LocalBaserowTableServiceFieldMapping.objects_and_trash.filter(
            service_id=OuterRef("pk"), enabled=True, field__trashed=True
        )
    )
    broken_upserts = LocalBaserowUpsertRow.objects.filter(
        _unusable_table() | (Q(integration__isnull=True) & mapping_on_trashed_field)
    ).values("pk")
    broken_deletes = LocalBaserowDeleteRow.objects.filter(_unusable_table()).values(
        "pk"
    )

    return DatabaseWorkflowAction.objects.filter(
        Q(localbaserowcreaterowworkflowaction__service_id__in=broken_upserts)
        | Q(localbaserowupdaterowworkflowaction__service_id__in=broken_upserts)
        | Q(localbaserowdeleterowworkflowaction__service_id__in=broken_deletes)
    )
