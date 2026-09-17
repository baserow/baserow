from typing import Iterable

from django.db.models import Exists, OuterRef, Q, QuerySet

from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
)
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


def requires_reconfiguration(field_ref: int | OuterRef) -> Q:
    """
    Whether the button field has a row action that is sure to fail at click
    time because something it references is in the trash or gone (ADR 006
    section 8). Used both to annotate button fields in bulk and to answer for a
    single one, so the two can't drift apart.

    Each check starts from the button's own actions and looks up their services
    by primary key: the service tables are shared with the builder and
    automations, so anything uncorrelated would scan all of them.

    A mapping on a trashed field only counts without an integration: with one,
    the dispatch drops the mapping rather than failing.

    :param field_ref: The button field's id, or `OuterRef("pk")` when
        annotating a button field queryset.
    """

    def has_broken_action(action_model, service_model, broken: Q) -> Exists:
        broken_service = service_model.objects.filter(broken, pk=OuterRef("service_id"))
        return Exists(
            action_model.objects.filter(Exists(broken_service), field_id=field_ref)
        )

    mapping_on_trashed_field = Exists(
        LocalBaserowTableServiceFieldMapping.objects_and_trash.filter(
            service_id=OuterRef("pk"), enabled=True, field__trashed=True
        )
    )
    broken_upsert = _unusable_table() | (
        Q(integration__isnull=True) & mapping_on_trashed_field
    )

    return (
        has_broken_action(
            LocalBaserowCreateRowWorkflowAction, LocalBaserowUpsertRow, broken_upsert
        )
        | has_broken_action(
            LocalBaserowUpdateRowWorkflowAction, LocalBaserowUpsertRow, broken_upsert
        )
        | has_broken_action(
            LocalBaserowDeleteRowWorkflowAction,
            LocalBaserowDeleteRow,
            _unusable_table(),
        )
    )


def button_fields_depending_on(
    *,
    field_ids: Iterable[int] = (),
    table_ids: Iterable[int] = (),
    database_ids: Iterable[int] = (),
) -> QuerySet[ButtonField]:
    """
    The button fields with a row action that maps one of these fields or
    targets one of these tables or a table in one of these databases, so their
    `requires_reconfiguration` may have just changed. Buttons that are
    themselves in a trashed table or database are left out: nobody can see them.
    """

    field_ids, table_ids, database_ids = (
        list(field_ids),
        list(table_ids),
        list(database_ids),
    )
    maps_a_field = Exists(
        LocalBaserowTableServiceFieldMapping.objects_and_trash.filter(
            service_id=OuterRef("pk"), field_id__in=field_ids
        )
    )
    targets = Q(table_id__in=table_ids) | Q(table__database_id__in=database_ids)
    upserts = LocalBaserowUpsertRow.objects.filter(targets | maps_a_field).values("pk")
    deletes = LocalBaserowDeleteRow.objects.filter(targets).values("pk")
    actions = DatabaseWorkflowAction.objects.filter(
        Q(localbaserowcreaterowworkflowaction__service_id__in=upserts)
        | Q(localbaserowupdaterowworkflowaction__service_id__in=upserts)
        | Q(localbaserowdeleterowworkflowaction__service_id__in=deletes)
    )

    return ButtonField.objects.filter(
        workflow_actions__in=actions,
        table__trashed=False,
        table__database__trashed=False,
    ).distinct()
