from dataclasses import dataclass
from typing import Any

from django.db import transaction

from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.table.operations import ReadDatabaseTableOperationType
from baserow.contrib.integrations.local_baserow.mixins import (
    LocalBaserowTableServiceFilterableMixin,
)
from baserow.core.db import specific_iterator
from baserow.core.exceptions import InstanceTypeDoesNotExist
from baserow.core.formula.types import BASEROW_FORMULA_MODE_RAW
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.services.handler import ServiceHandler
from baserow.core.tools import ToolContext

from .exceptions import ServiceFilterTargetDoesNotExist, ServiceFilterTargetNotSupported
from .registries import ServiceFilterTargetType, service_filter_target_type_registry
from .state import (
    FilterOperation,
    FilterState,
    FilterValidationContext,
    ServiceFilterValidationError,
    apply_operations,
    get_compatible_filter_types,
)

# Large select fields would flood a client's context; they rarely need all options.
MAX_SELECT_OPTIONS = 200


@dataclass
class ServiceFilterTarget:
    """An object owning a filterable Local Baserow service, checked for a user."""

    target_type: ServiceFilterTargetType
    owner: Any
    service: Any
    workspace: Workspace
    table: Table
    """The table the filters apply to."""
    saves_table: bool = False
    """
    Whether the table was picked in the editor for a service without one, and is
    saved with the filters.
    """

    @property
    def kind(self) -> str:
        return self.target_type.type

    @property
    def name(self) -> str:
        return self.target_type.get_name(self.owner)


@dataclass
class PreparedServiceFilters:
    """The current filters of a target and everything needed to change them."""

    target: ServiceFilterTarget
    fields: dict[int, Any]
    select_options: dict[int, dict[int, str]]
    state: FilterState
    validation: FilterValidationContext


def get_target_type(kind: str) -> ServiceFilterTargetType:
    """
    :raises ServiceFilterTargetDoesNotExist: When the kind is unknown.
    """

    try:
        return service_filter_target_type_registry.get(kind)
    except InstanceTypeDoesNotExist as exc:
        raise ServiceFilterTargetDoesNotExist() from exc


def is_filterable_service(service: Any) -> bool:
    """Whether the service reads rows from a table and can be filtered."""

    return (
        service is not None
        and isinstance(service.get_type(), LocalBaserowTableServiceFilterableMixin)
        and service.table_id is not None
        and not service.table.trashed
    )


def _get_table_to_save(ctx: ToolContext, table_id: int) -> Table:
    """
    Returns the table picked for a service without one, which the user must be able
    to read in the context's workspace.

    :raises ServiceFilterTargetNotSupported: When it can't be found there.
    :raises PermissionException: When the user may not read it.
    """

    try:
        table = TableHandler().get_table(table_id)
    except TableDoesNotExist as exc:
        raise ServiceFilterTargetNotSupported(
            f"The table with ID {table_id} does not exist."
        ) from exc
    if table.database.workspace_id != ctx.workspace.id or table.database.trashed:
        raise ServiceFilterTargetNotSupported(
            f"The table with ID {table_id} does not exist."
        )
    CoreHandler().check_permissions(
        ctx.user,
        ReadDatabaseTableOperationType.type,
        workspace=ctx.workspace,
        context=table,
    )
    return table


def resolve_service_filter_target(
    ctx: ToolContext,
    kind: str,
    target_id: int,
    for_update: bool = True,
    table_id: int | None = None,
) -> ServiceFilterTarget:
    """
    Finds the object owning the service whose filters must be read or changed in
    the context's workspace, and checks the user may do so.

    :param ctx: Who acts, and the workspace the object must belong to.
    :param kind: The type of the object, e.g. `builder_data_source`.
    :param target_id: Its ID.
    :param for_update: Whether the user must be able to change it, or only read it.
    :param table_id: The table picked in the editor. When the service has no table
        yet, the filters apply to it and it's saved with them.
    :raises ServiceFilterTargetDoesNotExist: When it can't be found in the workspace.
    :raises ServiceFilterTargetNotSupported: When its service can't be filtered.
    :raises PermissionException: When the user may not read or change it.
    """

    target_type = get_target_type(kind)
    owner = target_type.get_owner(target_id)
    workspace = target_type.get_workspace(owner)
    if workspace.id != ctx.workspace.id:
        raise ServiceFilterTargetDoesNotExist()

    CoreHandler().check_permissions(
        ctx.user,
        (
            target_type.update_operation_type
            if for_update
            else target_type.read_operation_type
        ),
        workspace=workspace,
        context=owner,
    )

    service = owner.service.specific if owner.service is not None else None
    if service is None or not isinstance(
        service.get_type(), LocalBaserowTableServiceFilterableMixin
    ):
        raise ServiceFilterTargetNotSupported(
            "Only data sources reading rows from a Baserow table can be filtered."
        )
    reason = target_type.get_filters_unsupported_reason(owner, service)
    if reason is not None:
        raise ServiceFilterTargetNotSupported(reason)

    if table_id is not None and service.table_id is None:
        table = _get_table_to_save(ctx, table_id)
        return ServiceFilterTarget(
            target_type, owner, service, workspace, table, saves_table=True
        )
    if table_id is not None and table_id != service.table_id:
        # Changing the table drops the filters, so it must be saved on its own.
        raise ServiceFilterTargetNotSupported(
            "Save the new table before changing its filters."
        )
    if service.table_id is None or service.table.trashed:
        raise ServiceFilterTargetNotSupported("Select a table before adding filters.")

    return ServiceFilterTarget(target_type, owner, service, workspace, service.table)


def _load_fields(table) -> list:
    return list(
        specific_iterator(
            FieldHandler()
            .get_base_fields_queryset()
            .filter(table=table)
            .order_by("-primary", "order", "id")
        )
    )


def _load_select_options(field) -> dict[int, str]:
    if not hasattr(field, "select_options"):
        return {}
    return {option.id: option.value for option in field.select_options.all()}


def prepare_service_filters(
    ctx: ToolContext, target: ServiceFilterTarget
) -> PreparedServiceFilters:
    """
    Loads the target's filters, its table's fields and what its formula values may
    read, so changes can be validated without touching the database again.
    """

    fields = _load_fields(target.table)
    select_options = {
        field.id: options
        for field in fields
        if (options := _load_select_options(field))
    }
    validation = FilterValidationContext(
        fields={field.id: field for field in fields},
        compatible_types={
            field.id: get_compatible_filter_types(field) for field in fields
        },
        select_options=select_options,
        check_formula=target.target_type.get_formula_check(ctx.user, target.owner),
        allow_filter_groups=target.target_type.supports_filter_groups,
    )
    return PreparedServiceFilters(
        target=target,
        fields=validation.fields,
        select_options=select_options,
        state=FilterState.from_service(target.service),
        validation=validation,
    )


def save_service_filter_operations(
    ctx: ToolContext,
    prepared: PreparedServiceFilters,
    operations: list[FilterOperation],
) -> tuple[bool, FilterState]:
    """
    Applies the operations to the target's current filters and, when they changed,
    saves them through the target's undoable update action.

    :raises ServiceFilterValidationError: With every problem in the operations.
    :return: Whether the filters changed, and the resulting filters.
    """

    target = prepared.target
    with transaction.atomic():
        # The filters may have changed since they were prepared, e.g. while an agent
        # worked out the operations. The saved filters replace them all, so lock the
        # service like the editors' updates do and apply the operations to the
        # filters as they are now, keeping the changes saved meanwhile.
        ServiceHandler().get_service_for_update(target.service.id)
        target.service.refresh_from_db(fields=["filter_type", "table"])
        values = {}
        if target.saves_table:
            if target.service.table_id is None:
                values["table_id"] = target.table.id
            elif target.service.table_id != target.table.id:
                raise ServiceFilterValidationError(
                    ["The table was changed while the filters were worked out."]
                )
        current_state = FilterState.from_service(target.service)
        new_state = apply_operations(current_state, operations, prepared.validation)
        if new_state == current_state:
            return False, current_state

        target.target_type.persist(
            ctx.user,
            target.owner,
            target.service.get_type(),
            {**values, **new_state.to_service_values()},
        )
    target.service.refresh_from_db(fields=["filter_type", "table"])
    return True, FilterState.from_service(target.service)


def describe_filter_state(
    state: FilterState, fields: dict[int, Any] | None = None
) -> dict[str, Any]:
    """
    The filters as clients read them: the top level filter type, the groups and
    the filters, without the filters on trashed fields which are kept as they are.
    """

    def describe_value(value: dict) -> dict[str, Any]:
        return {
            "value": value["formula"],
            "value_is_formula": value["mode"] != BASEROW_FORMULA_MODE_RAW,
        }

    def describe_field(field_id: int) -> dict[str, Any]:
        field = (fields or {}).get(field_id)
        return {"field_name": field.name} if field is not None else {}

    return {
        "filter_type": state.filter_type,
        "groups": [
            {
                "id": group.id,
                "filter_type": group.filter_type,
                "parent_group": group.parent_group,
            }
            for group in state.groups
        ],
        "filters": [
            {
                "id": f.id,
                "field_id": f.field_id,
                **describe_field(f.field_id),
                "type": f.type,
                **describe_value(f.value),
                "group": f.group,
            }
            for f in state.filters
            if not f.hidden
        ],
    }


def describe_table(
    prepared: PreparedServiceFilters,
) -> tuple[dict[str, Any], dict[str, list[str]]]:
    """
    Describes the fields of the target's table with the filter types each accepts
    and their select options. Fields accepting the same filter types share one set,
    to keep the description small.

    :return: The table, and the sets of filter types its fields refer to.
    """

    filter_type_sets: dict[str, list[str]] = {}
    set_names: dict[tuple[str, ...], str] = {}
    described_fields = []
    for field in prepared.fields.values():
        compatible = tuple(prepared.validation.compatible_types.get(field.id, []))
        if not compatible:
            continue
        set_name = set_names.setdefault(compatible, f"set_{len(set_names) + 1}")
        filter_type_sets[set_name] = list(compatible)
        described = {
            "id": field.id,
            "name": field.name,
            "type": field_type_registry.get_by_model(field.specific_class).type,
            "filter_types": set_name,
        }
        if field.primary:
            described["primary"] = True
        options = prepared.select_options.get(field.id)
        if options:
            described["select_options"] = [
                {"id": option_id, "value": value}
                for option_id, value in list(options.items())[:MAX_SELECT_OPTIONS]
            ]
        described_fields.append(described)

    table = prepared.target.table
    return (
        {"id": table.id, "name": table.name, "fields": described_fields},
        filter_type_sets,
    )
