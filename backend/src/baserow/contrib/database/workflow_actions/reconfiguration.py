from typing import Iterable

from django.db.models import Exists, OuterRef, Q, QuerySet

from baserow.contrib.database.fields.models import ButtonField, LinkRowField
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
from baserow.core.services.registries import service_type_registry

ROW_ACTION_MODELS = [
    LocalBaserowCreateRowWorkflowAction,
    LocalBaserowUpdateRowWorkflowAction,
    LocalBaserowDeleteRowWorkflowAction,
]


def _unusable_integration_by_action_model() -> dict[
    type[DatabaseWorkflowServiceAction], Q
]:
    """
    For each action model that can carry an integration, which of its services
    the dispatch refuses for their integration: a trashed one, and none when
    the service type needs one. Every other type has an integration refused on
    save, import and click (ADR 006 section 5).
    """

    unusable = {}
    for action_type in database_workflow_action_type_registry.get_all():
        if not action_type.allowed_integration_types:
            continue
        service_type = service_type_registry.get(action_type.service_type)
        condition = Q(integration__trashed=True)
        # Asked of a new service, as the query can't ask each one.
        if service_type.requires_integration(service_type.model_class()):
            condition |= Q(integration__isnull=True)
        unusable[action_type.model_class] = condition
    return unusable


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
    always counts, and so does none on an action whose service needs one.

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
    for action_model, unusable in _unusable_integration_by_action_model().items():
        broken |= has_broken_action(action_model, Service, unusable)
    return broken


def button_fields_depending_on(
    *,
    field_ids: Iterable[int] = (),
    link_row_table_ids: Iterable[int] = (),
    table_ids: Iterable[int] = (),
    database_ids: Iterable[int] = (),
    integration_ids: Iterable[int] = (),
) -> QuerySet[ButtonField]:
    """
    The button fields with a row action that maps one of these fields or a link
    field to one of `link_row_table_ids`, or targets one of these tables or a
    table in one of these databases, or an action using one of these
    integrations, so their `requires_reconfiguration` may have just changed.
    Buttons that are themselves in a trashed table or database are left out:
    nobody can see them.

    Every table and application created runs this, and usually nothing points
    at it, so one query first checks whether any service does. The services
    then stay a subquery: a table can be the target of many builder and
    automation services.
    """

    field_ids, link_row_table_ids, table_ids, database_ids, integration_ids = (
        list(field_ids),
        list(link_row_table_ids),
        list(table_ids),
        list(database_ids),
        list(integration_ids),
    )
    targets = Q()
    if table_ids:
        targets |= Q(table_id__in=table_ids)
    if database_ids:
        targets |= Q(table__database_id__in=database_ids)

    mapped_fields = Q()
    if field_ids:
        mapped_fields |= Q(field_id__in=field_ids)
    if link_row_table_ids:
        mapped_fields |= Q(
            field_id__in=LinkRowField.objects_and_trash.filter(
                link_row_table_id__in=link_row_table_ids
            ).values("pk")
        )

    # Each service lookup, with the action models whose services it can match.
    lookups = []
    if mapped_fields:
        lookups.append(
            (
                LocalBaserowTableServiceFieldMapping.objects_and_trash.filter(
                    mapped_fields
                ).values("service_id"),
                ROW_ACTION_MODELS,
            )
        )
    if targets:
        for service_model in [LocalBaserowUpsertRow, LocalBaserowDeleteRow]:
            lookups.append(
                (service_model.objects.filter(targets).values("pk"), ROW_ACTION_MODELS)
            )
    if integration_ids:
        lookups.append(
            (
                Service.objects.filter(integration_id__in=integration_ids).values("pk"),
                list(_unusable_integration_by_action_model()),
            )
        )
    if not lookups:
        return ButtonField.objects.none()

    services = [service_ids for service_ids, _ in lookups]
    if not services[0].union(*services[1:]).exists():
        return ButtonField.objects.none()

    uses_a_service = Q()
    for service_ids, action_models in lookups:
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
