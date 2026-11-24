"""
Service filter tools shared by the clients that act for a user, see
``baserow.core.tools``.
"""

import inspect
from collections import defaultdict
from typing import Annotated, Any

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db.models import Count

from pydantic import Field

from baserow.contrib.integrations.local_baserow.models import (
    LocalBaserowTableService,
    LocalBaserowTableServiceFilter,
)
from baserow.core.db import specific_iterator
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.services.models import Service
from baserow.core.tools import ToolContext, tool_execution
from baserow.core.tools.applications import MAX_PAGE_SIZE, visible_applications

from .exceptions import ServiceFilterTargetNotSupported
from .guides import FILTERS_COMBINE_GUIDE, OPERATIONS_GUIDE, VALUES_GUIDE
from .handler import (
    describe_filter_state,
    describe_table,
    is_filterable_service,
    prepare_service_filters,
    resolve_service_filter_target,
    save_service_filter_operations,
)
from .registries import service_filter_target_type_registry
from .state import FilterOperation, ServiceFilterValidationError

KIND_DESCRIPTION = (
    "What owns the filters: 'builder_data_source' for an application's data source, "
    "'dashboard_data_source' for a dashboard chart's data source, or "
    "'automation_node' for an automation node. list_filterable_data_sources gives "
    "the kind and id of each."
)


def _resolve(ctx: ToolContext, kind: str, id: int, for_update: bool):
    """
    :raises DjangoValidationError: When the kind is unknown or its service can't be
        filtered.
    """

    if kind not in service_filter_target_type_registry.get_types():
        kinds = ", ".join(service_filter_target_type_registry.get_types())
        raise DjangoValidationError(f"'{kind}' is not a kind. Use one of: {kinds}.")
    try:
        return resolve_service_filter_target(ctx, kind, id, for_update=for_update)
    except ServiceFilterTargetNotSupported as exc:
        raise DjangoValidationError(str(exc)) from exc


@tool_execution
def list_filterable_data_sources(
    ctx: ToolContext,
    application_id: Annotated[
        int | None,
        Field(
            description="Only list the ones of this application, builder, dashboard "
            "or automation. null lists those of every application."
        ),
    ] = None,
    page: Annotated[int, Field(ge=1, description="The page to return.")] = 1,
    size: Annotated[
        int,
        Field(ge=1, le=MAX_PAGE_SIZE, description="The number of items a page."),
    ] = 20,
) -> dict[str, Any]:
    """
    List the data sources and automation nodes reading rows from a table, whose
    filters can be read and changed: the data sources of applications and dashboards,
    and the automation nodes listing, getting or aggregating rows. Each has its
    kind, id, name, application, location (page, dashboard or workflow), service
    type, table id and number of filters. Returns one page, the total count, and
    whether more pages follow.
    """

    target_types = {
        target_type.application_type: target_type
        for target_type in service_filter_target_type_registry.get_all()
    }
    applications = visible_applications(ctx, list(target_types))
    if application_id is not None:
        applications = applications.filter(id=application_id)
        if not applications.exists():
            raise ApplicationDoesNotExist(application_id)

    applications = specific_iterator(applications.select_related("workspace"))
    applications_by_type = defaultdict(list)
    for application in applications:
        applications_by_type[application.get_type().type].append(application)

    owners_by_application = defaultdict(list)
    for application_type, batch in applications_by_type.items():
        target_type = target_types[application_type]
        owners = list(target_type.list_owners(ctx.user, batch))
        services = {
            service.id: service
            for service in specific_iterator(
                [owner.service for owner in owners if owner.service_id],
                base_model=Service,
                per_content_type_queryset_hook=lambda model, queryset: (
                    queryset.select_related("table")
                    if issubclass(model, LocalBaserowTableService)
                    else queryset
                ),
            )
        }
        for owner in owners:
            service = services.get(owner.service_id)
            if (
                not is_filterable_service(service)
                or target_type.get_filters_unsupported_reason(owner, service)
                is not None
            ):
                continue
            owners_by_application[target_type.get_application_id(owner)].append(
                (target_type, owner, service)
            )

    # Keep sidebar and per-application ordering, but load response metadata and
    # count filters only for the requested page.
    candidates = [
        (application, *candidate)
        for application in applications
        for candidate in owners_by_application[application.id]
    ]
    offset = (page - 1) * size
    selected = candidates[offset : offset + size]
    filter_counts = dict(
        LocalBaserowTableServiceFilter.objects.filter(
            service_id__in=[service.id for _, _, _, service in selected]
        )
        .values("service_id")
        .annotate(count=Count("id"))
        .values_list("service_id", "count")
    )
    items = [
        {
            "kind": target_type.type,
            "id": owner.id,
            "name": target_type.get_name(owner),
            "application": {
                "id": application.id,
                "name": application.name,
                "type": target_type.application_type,
            },
            "location": target_type.get_location(owner),
            "service_type": service.get_type().type,
            "table_id": service.table_id,
            "filter_count": filter_counts.get(service.id, 0),
        }
        for application, target_type, owner, service in selected
    ]
    return {
        "data_sources": items,
        "total": len(candidates),
        "page": page,
        "has_more": offset + size < len(candidates),
    }


@tool_execution
def list_service_filters(
    ctx: ToolContext,
    kind: Annotated[str, Field(description=KIND_DESCRIPTION)],
    id: Annotated[int, Field(description="The id of the data source or node.")],
) -> dict[str, Any]:
    """
    List the filters of a data source or automation node reading rows from a table,
    with what is needed to change them: its table's fields with the filter types
    each accepts and their select options, which data its formula values can read,
    and whether it supports filter groups.
    """

    target = _resolve(ctx, kind, id, for_update=False)
    prepared = prepare_service_filters(ctx, target)
    table, filter_type_sets = describe_table(prepared)
    return {
        "kind": target.kind,
        "id": target.owner.id,
        "name": target.name,
        "table": table,
        "filter_type_sets": filter_type_sets,
        "formula_values": target.target_type.describe_formula_values(),
        "supports_filter_groups": target.target_type.supports_filter_groups,
        **describe_filter_state(prepared.state, prepared.fields),
    }


@tool_execution
def update_service_filters(
    ctx: ToolContext,
    kind: Annotated[str, Field(description=KIND_DESCRIPTION)],
    id: Annotated[int, Field(description="The id of the data source or node.")],
    operations: Annotated[
        list[FilterOperation],
        Field(
            min_length=1,
            description="The changes to make, in order. They're all made, or none "
            "is when one is invalid.",
        ),
    ],
) -> dict[str, Any]:
    """
    Add, update and delete the filters and filter groups of a data source or
    automation node reading rows from a table, and save them. Call
    list_service_filters first for the field ids, filter types, select option ids
    and current filter ids. The filters are saved like a change made in the editor,
    and open editors show them. Returns whether the filters changed, and the
    resulting filters.
    """

    target = _resolve(ctx, kind, id, for_update=True)
    prepared = prepare_service_filters(ctx, target)
    try:
        changed, state = save_service_filter_operations(ctx, prepared, operations)
    except ServiceFilterValidationError as exc:
        raise DjangoValidationError(exc.errors) from exc
    return {"changed": changed, **describe_filter_state(state, prepared.fields)}


# The rules are shared with the prompts built on these tools, so they're appended
# rather than repeated in the docstring.
update_service_filters.__doc__ = "\n\n".join(
    (
        inspect.cleandoc(update_service_filters.__doc__),
        FILTERS_COMBINE_GUIDE,
        OPERATIONS_GUIDE,
        VALUES_GUIDE,
    )
)
