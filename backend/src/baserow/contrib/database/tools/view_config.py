"""
Tools that change how a view shows its rows, shared by the clients that act for a
user: sorts, hidden fields, row colours, and deleting views and filters.
"""

from typing import Annotated, Any, Callable, Literal
from uuid import uuid4

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import BaseModel, ConfigDict, Field, model_validator

from baserow.contrib.database.fields.exceptions import FieldDoesNotExist
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.tools.views import (
    ViewFilterItemCreate,
    field_options_of,
    get_view,
    resolve_view_filter,
)
from baserow.contrib.database.views.actions import (
    CreateDecorationActionType,
    CreateViewSortActionType,
    DeleteDecorationActionType,
    DeleteViewActionType,
    DeleteViewFilterActionType,
    DeleteViewSortActionType,
    UpdateViewFieldOptionsActionType,
    UpdateViewSortActionType,
)
from baserow.contrib.database.views.exceptions import (
    ViewDecorationNotSupported,
    ViewSortFieldNotSupported,
    ViewSortNotSupported,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import (
    View,
    ViewDecoration,
    ViewFilter,
    ViewSort,
)
from baserow.contrib.database.views.operations import (
    CreateViewDecorationOperationType,
)
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.handler import CoreHandler
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError, item_error_message


class ViewSortItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: int = Field(..., description="The ID of the field to sort on.")
    order: Literal["ASC", "DESC"] = Field(
        "ASC", description="ASC for A to Z and oldest first, DESC for the reverse."
    )


class FieldVisibility(BaseModel):
    model_config = ConfigDict(extra="forbid")

    field_id: int = Field(..., description="The ID of the field.")
    hidden: bool = Field(..., description="True to hide the field in the view.")


class ConditionalColour(BaseModel):
    model_config = ConfigDict(extra="forbid")

    color: str = Field(
        ...,
        # A row takes its colour from a CSS class per palette name.
        pattern=r"^((light|dark|darker)-)?"
        r"(blue|green|cyan|orange|yellow|red|brown|purple|pink|gray)$",
        description=(
            "One of blue, green, cyan, orange, yellow, red, brown, purple, pink or "
            "gray, optionally prefixed by light-, dark- or darker-."
        ),
    )
    filters: list[ViewFilterItemCreate] = Field(
        ...,
        description=(
            "The conditions a row must meet to get the colour, in the format of view "
            "filters. Empty to match every row."
        ),
    )
    operator: Literal["AND", "OR"] = Field(
        "AND", description="AND when a row must meet every condition, OR for any."
    )


class RowColour(BaseModel):
    model_config = ConfigDict(extra="forbid")

    style: Literal["left_border_color", "background_color"] = Field(
        ..., description="Colour the left border of a row, or its background."
    )
    by: Literal["single_select_color", "conditional_color"] = Field(
        ...,
        description=(
            "single_select_color takes the colour of a select option and needs "
            "field_id. conditional_color takes the first colour whose conditions the "
            "row meets and needs colours."
        ),
    )
    field_id: int | None = Field(None, description="The ID of a single select field.")
    colours: list[ConditionalColour] | None = Field(
        None, description="The colours and their conditions, first match wins."
    )

    @model_validator(mode="after")
    def _has_the_input_of_its_kind(self):
        if self.by == "single_select_color":
            if self.field_id is None or self.colours is not None:
                raise ValueError("single_select_color needs field_id and no colours.")
        elif not self.colours or self.field_id is not None:
            raise ValueError("conditional_color needs colours and no field_id.")
        return self


def _fields_of(view: View) -> dict[int, Any]:
    return {field.id: field for field in view.table.field_set.all()}


def _get_field(fields: dict[int, Any], field_id: int) -> Any:
    if field_id not in fields:
        raise FieldDoesNotExist(f"The field {field_id} isn't in the view's table.")
    return fields[field_id]


def _sort_item(sort: ViewSort) -> dict[str, Any]:
    return {"id": sort.id, "field_id": sort.field_id, "order": sort.order}


def set_view_sorts(
    ctx: ToolContext,
    view_id: Annotated[int, Field(description="The ID of the view.")],
    sorts: Annotated[
        list[ViewSortItem],
        Field(description="The new sorts, most important first. Empty removes them."),
    ],
) -> dict[str, Any]:
    """
    Replace the sorts of a view: the view ends up sorted by exactly this list. When
    anything can't be applied, like a field outside the view's table, the view stays
    as it was. A form view takes no sorts.
    """

    view = get_view(ctx, view_id)
    ctx.update_status(_("Sorting %(view_name)s...") % {"view_name": view.name})

    field_ids = [sort.field_id for sort in sorts]
    if len(set(field_ids)) != len(field_ids):
        raise ToolInputError("A view can only be sorted once by the same field.")
    fields = _fields_of(view)
    for field_id in field_ids:
        _get_field(fields, field_id)

    existing = list(ViewSort.objects.filter(view=view).order_by("priority", "id"))
    # A new sort goes after the others. Those at the start that already match are
    # kept, the others are recreated to end up in the order of the list.
    keep = 0
    while (
        keep < min(len(existing), len(sorts))
        and existing[keep].field_id == sorts[keep].field_id
    ):
        keep += 1

    # A sort recreated to move it keeps its type, like sorting by option order.
    sort_types = {sort.field_id: sort.type for sort in existing[keep:]}
    result = []
    try:
        with transaction.atomic():
            for sort in existing[keep:]:
                DeleteViewSortActionType.do(ctx.user, sort)
            for sort, item in zip(existing[:keep], sorts):
                if sort.order != item.order:
                    sort = UpdateViewSortActionType.do(ctx.user, sort, order=item.order)
                result.append(_sort_item(sort))
            for item in sorts[keep:]:
                sort = CreateViewSortActionType.do(
                    ctx.user,
                    view,
                    fields[item.field_id],
                    item.order,
                    sort_type=sort_types.get(item.field_id),
                )
                result.append(_sort_item(sort))
    except ViewSortNotSupported as exc:
        raise ToolInputError("This type of view takes no sorts.") from exc
    except ViewSortFieldNotSupported as exc:
        raise ToolInputError("A view can't be sorted by one of these fields.") from exc

    return {"sorts": result}


def set_field_visibility(
    ctx: ToolContext,
    view_id: Annotated[int, Field(description="The ID of the view.")],
    fields: Annotated[
        list[FieldVisibility],
        Field(min_length=1, description="The fields to hide or show."),
    ],
) -> dict[str, Any]:
    """
    Hide or show fields in a view. A field outside the view's table, or the primary
    field of a grid view, which can't be hidden, is reported in errors and the others
    are still changed. A form view has no hidden fields.
    """

    if not fields:
        raise DjangoValidationError("fields must hold at least one field.")

    view = get_view(ctx, view_id)
    ctx.update_status(_("Updating %(view_name)s...") % {"view_name": view.name})

    if field_options_of(view).hidden_field is None:
        raise ToolInputError("This type of view has no hidden fields.")

    is_grid = view_type_registry.get_by_model(view.specific_class).type == "grid"
    table_fields = _fields_of(view)
    options = {}
    errors = []
    for index, item in enumerate(fields):
        try:
            field = _get_field(table_fields, item.field_id)
            if is_grid and field.primary and item.hidden:
                raise ToolInputError(
                    "The primary field of a grid view can't be hidden."
                )
        except (FieldDoesNotExist, ToolInputError) as exc:
            errors.append(
                {
                    "index": index,
                    "field_id": item.field_id,
                    "error": item_error_message(exc),
                }
            )
        else:
            options[item.field_id] = {"hidden": item.hidden}

    if options:
        with transaction.atomic():
            UpdateViewFieldOptionsActionType.do(ctx.user, view.specific, options)

    return {"updated_fields": list(options), "errors": errors}


def _delete_each(
    ids: list[int], id_name: str, result_key: str, delete: Callable[[int], None]
) -> dict[str, Any]:
    """Deletes each id in its own savepoint, reporting the ones that fail."""

    if not ids:
        raise DjangoValidationError(f"{id_name}s must hold at least one ID.")

    deleted = []
    errors = []
    for index, item_id in enumerate(ids):
        try:
            with transaction.atomic():
                delete(item_id)
        except Exception as exc:
            errors.append(
                {"index": index, id_name: item_id, "error": item_error_message(exc)}
            )
        else:
            deleted.append(item_id)
    return {result_key: deleted, "errors": errors}


def delete_views(
    ctx: ToolContext,
    view_ids: Annotated[
        list[int], Field(description="The IDs of the views to delete.")
    ],
) -> dict[str, Any]:
    """
    Move views to the trash, from where they can be restored. A view that fails is
    reported in errors and the others are still deleted.
    """

    def delete(view_id: int) -> None:
        DeleteViewActionType.do(ctx.user, get_view(ctx, view_id))

    ctx.update_status(_("Deleting views..."))
    return _delete_each(view_ids, "view_id", "deleted_views", delete)


def delete_view_filters(
    ctx: ToolContext,
    filter_ids: Annotated[
        list[int],
        Field(
            description="The IDs of the filters to delete, as list_views shows them."
        ),
    ],
) -> dict[str, Any]:
    """
    Delete filters from views. A filter that fails is reported in errors and the
    others are still deleted.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    filters = ViewFilter.objects.filter(view__table__in=tables)

    def delete(filter_id: int) -> None:
        DeleteViewFilterActionType.do(
            ctx.user,
            ViewHandler().get_filter(ctx.user, filter_id, base_queryset=filters),
        )

    ctx.update_status(_("Deleting filters..."))
    return _delete_each(filter_ids, "filter_id", "deleted_filters", delete)


def _colour_filter(item: ViewFilterItemCreate, fields, timezone) -> dict[str, Any]:
    field, filter_type, filter_value = resolve_view_filter(fields, item, timezone)
    return {
        "id": uuid4().hex,
        "field": field.id,
        "type": filter_type,
        "value": filter_value,
    }


def _colour_conf(ctx: ToolContext, view: View, colour: RowColour) -> dict[str, Any]:
    fields = _fields_of(view)

    if colour.by == "single_select_color":
        field = _get_field(fields, colour.field_id)
        field_type = field_type_registry.get_by_model(field.specific_class).type
        if field_type != "single_select":
            raise ToolInputError(f"The field '{field.name}' isn't a single select.")
        return {"field_id": field.id}

    try:
        return {
            "colors": [
                {
                    "id": uuid4().hex,
                    "color": item.color,
                    "operator": item.operator,
                    "filters": [
                        _colour_filter(view_filter, fields, ctx.timezone)
                        for view_filter in item.filters
                    ],
                }
                for item in colour.colours
            ]
        }
    except ValueError as exc:
        raise ToolInputError(str(exc)) from exc


def set_row_colours(
    ctx: ToolContext,
    view_id: Annotated[int, Field(description="The ID of the view.")],
    colour: Annotated[RowColour, Field(description="How to colour the rows.")],
) -> dict[str, Any]:
    """
    Colour the rows of a view, by a single select field or by conditions. A form view
    has no rows to colour. Adds to the colours the view already has, which list_views
    shows. Needs a premium licence.
    """

    view = get_view(ctx, view_id)
    ctx.update_status(_("Colouring %(view_name)s...") % {"view_name": view.name})
    # Before reading the fields, as an error about a field names it.
    CoreHandler().check_permissions(
        ctx.user,
        CreateViewDecorationOperationType.type,
        workspace=ctx.workspace,
        context=view,
    )

    try:
        with transaction.atomic():
            decoration = CreateDecorationActionType.do(
                view, colour.style, colour.by, _colour_conf(ctx, view, colour), ctx.user
            )
    except ViewDecorationNotSupported as exc:
        raise ToolInputError("This type of view can't colour its rows.") from exc

    return {"decoration_id": decoration.id}


def delete_row_colours(
    ctx: ToolContext,
    decoration_ids: Annotated[
        list[int],
        Field(description="The IDs of the row colours to delete, as list_views shows."),
    ],
) -> dict[str, Any]:
    """
    Remove row colours from views. A colour that fails is reported in errors and the
    others are still removed.
    """

    tables = TableHandler().list_workspace_tables(ctx.user, ctx.workspace)
    decorations = ViewDecoration.objects.filter(
        view__table__in=tables, view__trashed=False
    )

    def delete(decoration_id: int) -> None:
        DeleteDecorationActionType.do(
            ViewHandler().get_decoration(
                ctx.user, decoration_id, base_queryset=decorations
            ),
            ctx.user,
        )

    ctx.update_status(_("Removing row colours..."))
    return _delete_each(decoration_ids, "decoration_id", "deleted_row_colours", delete)
