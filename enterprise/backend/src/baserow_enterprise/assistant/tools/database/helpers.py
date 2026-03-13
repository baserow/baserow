from itertools import groupby
from typing import TYPE_CHECKING, Any, Callable

from django.contrib.auth.models import AbstractUser
from django.db.models import Q
from django.utils.translation import gettext as _

from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.mcp.services import filter_tables
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.actions import CreateViewFilterActionType
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View, ViewFilter
from baserow.core.db import specific_iterator
from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.database.types.table import TableItem

from .types import (
    AnyViewFilterItemCreate,
    FieldItem,
    FieldItemCreate,
    FieldItemUpdate,
    InvalidFormulaFieldError,
)

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers


def get_table(user: AbstractUser, workspace: Workspace, table_id: int) -> Table:
    """Get a single table by ID, raising ToolInputError if not found."""

    from baserow_enterprise.assistant.tools.builder.helpers import ToolInputError

    try:
        return filter_tables(user, workspace).get(id=table_id)
    except Table.DoesNotExist:
        raise ToolInputError(
            f"Table with ID {table_id} not found. "
            "Use get_tables_schema to find valid table IDs."
        )


def get_tables_schema(
    tables: list[Table],
    full_schema: bool = False,
) -> list[TableItem]:
    """
    Build serialised schema descriptions for the given tables.

    :param tables: Tables to describe.
    :param full_schema: If True include all fields, otherwise only primary
        fields and relationships.
    :returns: List of table descriptions, in the same order as the input tables.
    """

    q = Q(table__in=tables)
    if not full_schema:
        q &= Q(linkrowfield__isnull=False) | Q(primary=True)

    base_field_queryset = FieldHandler().get_base_fields_queryset()
    fields = specific_iterator(
        base_field_queryset.filter(q).order_by("table_id", "order"),
        per_content_type_queryset_hook=(
            lambda field, queryset: field_type_registry.get_by_model(
                field
            ).enhance_field_queryset(queryset, field)
        ),
    )

    table_items: list[TableItem] = []
    tables_by_id = {table.id: table for table in tables}
    for table_id, fields_in_table in groupby(fields, lambda f: f.table_id):
        table_items.append(_get_table_schema(tables_by_id, table_id, fields_in_table))

    # Preserve the input order
    input_order = {t.id: i for i, t in enumerate(tables)}
    table_items.sort(key=lambda t: input_order[t.id])
    return table_items


def _get_table_schema(
    tables_by_id: dict[int, Table], table_id: int, fields_in_table: list[Field]
) -> TableItem:
    """
    Build a TableItem schema description for a single table given its fields.

    :param tables_by_id: Mapping of table ID → table instance for all tables.
    :param table_id: ID of the table to describe.
    :param fields_in_table: Iterable of field instances belonging to the table.
    :returns: TableItem describing the table and its fields.
    """

    fields_in_table = list(fields_in_table)
    primary_field = next((f for f in fields_in_table if f.primary), None)
    if primary_field is None:
        raise ValueError(f"Table {table_id} has no primary field")
    primary_field_item = FieldItem.from_django_orm(primary_field)

    table = tables_by_id[table_id]

    return TableItem(
        id=table_id,
        name=table.name,
        primary_field=primary_field_item,
        fields=[
            FieldItem.from_django_orm(f)
            for f in fields_in_table
            if f.id != primary_field.id
        ],
    )


def create_fields(
    user: AbstractUser,
    table: Table,
    field_items: list[FieldItemCreate],
    tool_helpers: "ToolHelpers",
    formula_fixer: Callable[[Table, str, str], str | None] | None = None,
) -> tuple[list[FieldItem], list[str], list[dict]]:
    """
    Create fields in a table, handling formula errors with optional auto-fix.

    Fields are sorted so that dependencies are satisfied: regular fields first,
    then link_row, lookup, and formula last.

    :param user: The acting user.
    :param table: Target table.
    :param field_items: Field definitions to create.
    :param tool_helpers: Provides status updates and cancellation.
    :param formula_fixer: Optional callback ``(table, name, formula) -> fixed``
        invoked when a formula field fails validation.
    :returns: Tuple of (created fields, field error messages, formula error dicts).
    """

    from .types import InvalidFormulaFieldError
    from .types.fields import FIELD_ORDER

    created_fields: list[FieldItem] = []
    formula_errors: list[dict] = []
    field_errors: list[str] = []

    # Creation order: regular → link_row → lookup → formula.
    # link_row before lookup so auto-created links exist for lookups.
    # formula last so they can reference fields created earlier.
    field_items = sorted(field_items, key=lambda f: FIELD_ORDER.get(f.type, 0))

    for field_item in field_items:
        tool_helpers.raise_if_cancelled()
        tool_helpers.update_status(
            _("Creating field %(field_name)s...") % {"field_name": field_item.name}
        )

        try:
            new_field = CreateFieldActionType.do(
                user,
                table,
                field_item.type,
                **field_item.to_django_orm_kwargs(table, user=user),
            )
            created_fields.append(FieldItem.from_django_orm(new_field))
        except InvalidFormulaFieldError as exc:
            _fix_formula_field(
                user, table, formula_fixer, created_fields, formula_errors, exc
            )
        except Exception as e:
            field_errors.append(
                f"Error creating field {field_item.name} in table_{table.id}: {e}.\n"
                f"Please retry recreating this field later, if important."
            )
    return created_fields, field_errors, formula_errors


def _fix_formula_field(
    user: AbstractUser,
    table: Table,
    formula_fixer: Callable[[Table, str, str], str | None] | None,
    created_fields: list[FieldItem],
    formula_errors: list[dict],
    exc: InvalidFormulaFieldError,
):
    """
    Attempt to fix an invalid formula field using the provided formula_fixer callback.
    If successful, creates the field with the fixed formula. Otherwise, records the error.

    :param user: The acting user.
    :param table: The table the field belongs to.
    :param formula_fixer: Callback to attempt formula fixing.
    :param created_fields: List to append successfully created fields to.
    :param formula_errors: List to append error details to if fixing fails.
    :param exc: The exception containing details about the invalid formula.
    """

    fixed = False
    if formula_fixer:
        try:
            new_formula = formula_fixer(exc.table, exc.field_name, exc.formula)
            if new_formula:
                new_field = CreateFieldActionType.do(
                    user,
                    table,
                    "formula",
                    name=exc.field_name,
                    formula=new_formula,
                )
                created_fields.append(FieldItem.from_django_orm(new_field))
                fixed = True
        except Exception:
            pass
    if not fixed:
        formula_errors.append(
            {
                "field_name": exc.field_name,
                "formula": exc.formula,
                "error": exc.error,
            }
        )


def get_view(user: AbstractUser, workspace: Workspace, view_id: int) -> View:
    """
    Fetch a view scoped to the user's workspace.

    :param user: The acting user.
    :param workspace: Workspace the view must belong to.
    :param view_id: ID of the view to retrieve.
    """

    return ViewHandler().get_view_as_user(
        user,
        view_id,
        base_queryset=View.objects.filter(table__database__workspace=workspace),
    )


def create_view_filter(
    user: AbstractUser,
    orm_view: View,
    table_fields: dict[int, Any],
    view_filter_item: AnyViewFilterItemCreate,
) -> ViewFilter:
    """
    Create a single view filter after validating the field type matches.

    :param user: The acting user.
    :param orm_view: The view to add the filter to.
    :param table_fields: Mapping of field ID → field instance for the table.
    :param view_filter_item: The filter definition to create.
    :raises ValueError: If the field is not found or its type doesn't match.
    """

    field = table_fields.get(view_filter_item.field_id)
    if field is None:
        raise ValueError(
            f"Field {view_filter_item.field_id} not found for filter. "
            f"Available field IDs: {sorted(table_fields.keys())}"
        )
    field_type = field_type_registry.get_by_model(field.specific_class)
    if field_type.type != view_filter_item.type:
        raise ValueError(
            f"Field '{field.name}' (id={field.id}) is type '{field_type.type}', "
            f"but filter declared type '{view_filter_item.type}'"
        )

    filter_type = view_filter_item.get_django_orm_type(field)
    filter_value = view_filter_item.get_django_orm_value(
        field, timezone=user.profile.timezone
    )

    return CreateViewFilterActionType.do(
        user,
        orm_view,
        field,
        filter_type,
        filter_value,
        filter_group_id=None,
    )


def update_field(
    user: AbstractUser,
    workspace: Workspace,
    field_update: "FieldItemUpdate",
    formula_fixer: Callable[[Table, str, str], str | None] | None = None,
) -> FieldItem:
    """
    Update an existing field.

    :param user: The acting user.
    :param workspace: Workspace the field must belong to.
    :param field_update: The update definition.
    :param formula_fixer: Optional callback for fixing invalid formulas.
    :returns: Updated field as FieldItem.
    """

    base_field = FieldHandler().get_field(field_update.field_id)
    field = base_field.specific

    # Verify workspace access
    filter_tables(user, workspace).filter(id=base_field.table_id).get()
    field_type = field_type_registry.get_by_model(field).type
    kwargs = field_update.to_update_kwargs(field_type)

    if not kwargs:
        return FieldItem.from_django_orm(field)

    # Validate formula before updating
    if "formula" in kwargs and kwargs["formula"]:
        from baserow.contrib.database.fields.models import FormulaField
        from baserow.core.formula.parser.exceptions import BaserowFormulaException

        try:
            tmp = FormulaField(
                formula=kwargs["formula"],
                table=field.table,
                name=kwargs.get("name", field.name),
                order=0,
            )
            tmp.recalculate_internal_fields(raise_if_invalid=True)
        except BaserowFormulaException as e:
            if formula_fixer:
                fixed = formula_fixer(
                    field.table,
                    kwargs.get("name", field.name),
                    kwargs["formula"],
                )
                if fixed:
                    kwargs["formula"] = fixed
                else:
                    raise InvalidFormulaFieldError(
                        kwargs.get("name", field.name),
                        kwargs["formula"],
                        field.table,
                        str(e),
                    )
            else:
                raise InvalidFormulaFieldError(
                    kwargs.get("name", field.name),
                    kwargs["formula"],
                    field.table,
                    str(e),
                )

    UpdateFieldActionType.do(user, field, **kwargs)
    # Re-fetch the specific field to get the updated state
    updated_field = FieldHandler().get_field(field_update.field_id).specific
    return FieldItem.from_django_orm(updated_field)


def delete_field(
    user: AbstractUser,
    workspace: Workspace,
    field_id: int,
) -> None:
    """
    Delete (soft-delete / trash) a field.

    :param user: The acting user.
    :param workspace: Workspace the field must belong to.
    :param field_id: ID of the field to delete.
    """

    base_field = FieldHandler().get_field(field_id)
    # Verify workspace access
    filter_tables(user, workspace).filter(id=base_field.table_id).get()
    DeleteFieldActionType.do(user, base_field.specific)
