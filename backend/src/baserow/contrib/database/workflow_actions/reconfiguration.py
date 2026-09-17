from typing import Iterable

from django.db.models import Exists, OuterRef, Q, QuerySet

from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.workflow_actions.models import (
    DatabaseWorkflowAction,
    DatabaseWorkflowServiceAction,
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowDeleteRow,
    LocalBaserowTableServiceFieldMapping,
    LocalBaserowUpsertRow,
)
from baserow.core.services.models import Service

ROW_ACTION_MODELS = [
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
]


def _integration_action_models() -> list[type[DatabaseWorkflowServiceAction]]:
    """
    The action models that can carry an integration. Every other type has one
    refused on save, import and click (ADR 006 section 5).
    """

    return [
        action_type.model_class
        for action_type in database_workflow_action_type_registry.get_all()
        if action_type.allowed_integration_types
    ]


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
    the dispatch drops the mapping rather than failing. A trashed integration
    always counts, as the dispatch refuses it.

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

    broken = (
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
    for action_model in _integration_action_models():
        broken |= has_broken_action(action_model, Service, Q(integration__trashed=True))
    return broken


def button_fields_depending_on(
    *,
    field_ids: Iterable[int] = (),
    table_ids: Iterable[int] = (),
    database_ids: Iterable[int] = (),
    integration_ids: Iterable[int] = (),
) -> QuerySet[ButtonField]:
    """
    The button fields with a row action that maps one of these fields or
    targets one of these tables or a table in one of these databases, or an
    action using one of these integrations, so their
    `requires_reconfiguration` may have just changed. Buttons that are
    themselves in a trashed table or database are left out: nobody can see them.

    Every table and application created runs this, and usually nothing points
    at it, so the matching services are found first and the buttons only
    looked up when there are some.
    """

    field_ids, table_ids, database_ids, integration_ids = (
        list(field_ids),
        list(table_ids),
        list(database_ids),
        list(integration_ids),
    )
    targets = Q()
    if table_ids:
        targets |= Q(table_id__in=table_ids)
    if database_ids:
        targets |= Q(table__database_id__in=database_ids)

    lookups = []
    if field_ids:
        lookups.append(
            LocalBaserowTableServiceFieldMapping.objects_and_trash.filter(
                field_id__in=field_ids
            ).values_list("service_id", flat=True)
        )
    if targets:
        for service_model in [LocalBaserowUpsertRow, LocalBaserowDeleteRow]:
            lookups.append(
                service_model.objects.filter(targets).values_list("pk", flat=True)
            )
    action_models = []
    if field_ids or targets:
        action_models += ROW_ACTION_MODELS
    if integration_ids:
        lookups.append(
            Service.objects.filter(integration_id__in=integration_ids).values_list(
                "pk", flat=True
            )
        )
        action_models += _integration_action_models()
    if not lookups:
        return ButtonField.objects.none()

    service_ids = list(lookups[0].union(*lookups[1:]))
    if not service_ids:
        return ButtonField.objects.none()

    uses_a_service = Q()
    for action_model in action_models:
        uses_a_service |= Q(
            **{f"{action_model._meta.model_name}__service_id__in": service_ids}
        )
    actions = DatabaseWorkflowAction.objects.filter(uses_a_service)

    return ButtonField.objects.filter(
        workflow_actions__in=actions,
        table__trashed=False,
        table__database__trashed=False,
    ).distinct()
