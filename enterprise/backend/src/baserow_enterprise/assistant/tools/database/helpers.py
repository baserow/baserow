from typing import Callable

from django.contrib.auth.models import AbstractUser
from django.db import transaction

from baserow.contrib.database.fields.actions import CreateFieldActionType
from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.mcp.services import filter_tables
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools import fields as shared_fields
from baserow.contrib.database.tools.tables import (
    get_tables_schema,  # noqa: F401
    permitted_tables,
)
from baserow.contrib.database.tools.views import create_view_filter  # noqa: F401
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.core.models import Workspace
from baserow.core.tools import ToolContext
from baserow_enterprise.assistant.tools.shared import (
    ToolInputError,
    raise_if_permission_denied,
)

from .types import (
    FieldItem,
    FieldItemUpdate,
    InvalidFormulaFieldError,
)


def get_table(user: AbstractUser, workspace: Workspace, table_id: int) -> Table:
    """
    Get a single table by ID.

    :param user: The acting user.
    :param workspace: The workspace the table must belong to.
    :param table_id: The ID of the table to fetch.
    :returns: The matching table.
    :raises ToolInputError: When the table is not visible in the workspace.
    """

    try:
        return filter_tables(user, workspace).get(id=table_id)
    except Table.DoesNotExist:
        raise ToolInputError(
            f"Table with ID {table_id} not found. "
            "Use get_tables_schema to find valid table IDs."
        )


def readable_database_tables(
    user: AbstractUser, workspace: Workspace, database_id: int
) -> list[Table]:
    """
    The database's tables whose fields the user may list, so the formula agents only
    see fields the user can.

    :param user: The acting user.
    :param workspace: The workspace the database is in.
    :param database_id: The database whose tables are returned.
    :returns: The tables, in sidebar order.
    """

    return permitted_tables(
        ToolContext(user=user, workspace=workspace),
        filter_tables(user, workspace).filter(database_id=database_id),
        ListFieldsOperationType.type,
    )


FormulaFixer = Callable[[Table, str, str], str | None]


def has_formula(error: dict) -> bool:
    """
    Whether a formula error has a formula to repair. Without one the fixer would
    have to invent what the field computes.
    """

    return bool((error.get("formula") or "").strip())


def create_repaired_formula_fields(
    user: AbstractUser,
    table: Table,
    formula_fixer: FormulaFixer,
    formula_errors: list[dict],
    raise_if_cancelled: Callable[[], None],
) -> tuple[list[FieldItem], list[dict]]:
    """
    Ask the formula fixer to repair each invalid formula the shared create step
    returned, and create the formula fields it repairs. Call it outside a
    transaction, because the fixer calls a model.

    :param user: The acting user.
    :param table: The table the fields belong to.
    :param formula_fixer: Callback ``(table, name, formula) -> fixed formula``.
    :param formula_errors: The invalid formulas from the shared create step.
    :param raise_if_cancelled: Raises when the user cancelled the request.
    :returns: The created fields, and the formula errors that remain.
    """

    created: list[FieldItem] = []
    remaining: list[dict] = []
    for error in formula_errors:
        if not has_formula(error):
            remaining.append(error)
            continue
        raise_if_cancelled()
        try:
            formula = formula_fixer(table, error["field_name"], error["formula"])
            raise_if_cancelled()
            if formula:
                with transaction.atomic():
                    new_field = CreateFieldActionType.do(
                        user,
                        table,
                        "formula",
                        name=error["field_name"],
                        formula=formula,
                    )
                created.append(FieldItem.from_django_orm(new_field))
                continue
        except Exception as exc:
            # The savepoint rolled back a field its cached model may still have.
            shared_fields.forget_cached_table_models()
            raise_if_permission_denied(exc)
        remaining.append(error)
    return created, remaining


def _failed_updates(
    field_updates: list[FieldItemUpdate], formula_errors: list[dict]
) -> list[tuple[dict, FieldItemUpdate, set[str]]]:
    """
    Pairs each formula error with the update that raised it, with the properties
    a later update of the same field sets. A property set to None is left
    unchanged, so it doesn't count.
    """

    pairs = []
    for error in formula_errors:
        index = error["index"]
        later = set().union(
            *(
                {
                    name
                    for name, value in update.model_dump(exclude_unset=True).items()
                    if value is not None
                }
                - {"field_id"}
                for update in field_updates[index + 1 :]
                if update.field_id == error["field_id"]
            )
        )
        pairs.append((error, field_updates[index], later))
    return pairs


def apply_repaired_formula_updates(
    tool_context: ToolContext,
    formula_fixer: FormulaFixer,
    field_updates: list[FieldItemUpdate],
    formula_errors: list[dict],
    raise_if_cancelled: Callable[[], None],
) -> tuple[list[FieldItem], bool, list[str]]:
    """
    Ask the formula fixer to repair each invalid formula the shared update step
    returned, and apply those updates with the repaired formula. Call it outside a
    transaction, because the fixer calls a model.

    :param tool_context: Who acts and where status goes.
    :param formula_fixer: Callback ``(table, name, formula) -> fixed formula``.
    :param field_updates: The updates the shared step received.
    :param formula_errors: The invalid formulas from the shared update step.
    :param raise_if_cancelled: Raises when the user cancelled the request.
    :returns: The updated fields, whether any changed, and an error message for
        each update that could not be repaired.
    """

    updated: list[FieldItem] = []
    changed = False
    errors: list[str] = []
    for error, failed, later in _failed_updates(field_updates, formula_errors):
        field_id = error["field_id"]
        # The update rolled back as a whole. Its other properties are applied with
        # the repaired formula, except those a later update of the field set.
        values = failed.model_dump(exclude_unset=True, exclude=later)
        if "formula" in later:
            # A later update replaced the formula, so it isn't repaired.
            values.pop("formula", None)
            if values.keys() == {"field_id"}:
                continue
        elif not has_formula(error):
            errors.append(f"Error updating field {field_id}: {error['error']}")
            continue
        raise_if_cancelled()
        try:
            if "formula" in values:
                table = filter_tables(tool_context.user, tool_context.workspace).get(
                    id=error["table_id"]
                )
                formula = formula_fixer(table, error["field_name"], error["formula"])
                raise_if_cancelled()
                if not formula:
                    raise InvalidFormulaFieldError(
                        error["field_name"], error["formula"], table, error["error"]
                    )
                values["formula"] = formula
            update = FieldItemUpdate(**values)
            with transaction.atomic():
                field_item, field_changed = shared_fields.update_field(
                    tool_context, update
                )
            updated.append(field_item)
            changed = changed or field_changed
        except Exception as exc:
            shared_fields.forget_cached_table_models()
            raise_if_permission_denied(exc)
            errors.append(f"Error updating field {field_id}: {exc}")
    return updated, changed, errors


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
