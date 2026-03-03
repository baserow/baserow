from dataclasses import dataclass
from itertools import groupby
from typing import TYPE_CHECKING, Annotated, Any, Callable, Literal, Type, Union

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _

from pydantic import (
    ConfigDict,
    Field,
    create_model,
)
from pydantic_ai import Tool

from baserow.contrib.database.fields.actions import CreateFieldActionType
from baserow.contrib.database.fields.field_types import LinkRowFieldType
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import SelectOption as OrmSelectOption
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.actions import (
    CreateRowsActionType,
    DeleteRowsActionType,
    UpdateRowsActionType,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.table.models import (
    FieldObject,
    GeneratedTableModel,
    Table,
)
from baserow.contrib.database.views.actions import CreateViewFilterActionType
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View, ViewFilter
from baserow.core.db import specific_iterator
from baserow.core.models import Workspace
from baserow_enterprise.assistant.tools.database.types.table import (
    BaseTableItem,
    TableItem,
)
from baserow_enterprise.assistant.tools.toolset import inline_refs

from .types import (
    AnyViewFilterItemCreate,
    BaseModel,
    Date,
    Datetime,
    FieldItem,
    FieldItemCreate,
)

if TYPE_CHECKING:
    from baserow_enterprise.assistant.deps import ToolHelpers

NoChange = Literal["__NO_CHANGE__"]


def filter_tables(user: AbstractUser, workspace: Workspace) -> QuerySet[Table]:
    return TableHandler().list_workspace_tables(user, workspace)


def list_tables(
    user: AbstractUser, workspace: Workspace, database_id: int
) -> list[BaseTableItem]:
    tables_qs = filter_tables(user, workspace).filter(database_id=database_id)

    return [BaseTableItem(id=table.id, name=table.name) for table in tables_qs]


def get_tables_schema(
    tables: list[Table],
    full_schema: bool = False,
) -> list[TableItem]:
    """Returns the schema of the specified tables."""

    q = Q(table__in=tables)
    if not full_schema:  # Only the primary fields and relationships
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

    table_items = []
    tables_by_id = {table.id: table for table in tables}
    for table_id, fields_in_table in groupby(fields, lambda f: f.table_id):
        fields_in_table = list(fields_in_table)
        primary_field = next((f for f in fields_in_table if f.primary), None)
        if primary_field is None:
            raise ValueError(f"Table {table_id} has no primary field")
        primary_field_item = FieldItem.from_django_orm(primary_field)

        table = tables_by_id[table_id]
        table_items.append(
            TableItem(
                id=table_id,
                name=table.name,
                primary_field=primary_field_item,
                fields=[
                    FieldItem.from_django_orm(f)
                    for f in fields_in_table
                    if f.id != primary_field.id
                ],
            )
        )

    # Make sure the order is the same as the input
    tables = list(tables)
    table_items.sort(
        key=lambda t: tables.index(next(tb for tb in tables if tb.id == t.id))
    )
    return table_items


def create_fields(
    user: AbstractUser,
    table: Table,
    field_items: list[FieldItemCreate],
    tool_helpers: "ToolHelpers",
    formula_fixer: Callable[[Table, str, str], str | None] | None = None,
) -> tuple[list[FieldItem], list[str], list[dict]]:
    from .types import InvalidFormulaFieldError

    created_fields = []
    formula_errors = []
    field_errors = []

    # Known limitation: formula fields are created last so they can reference
    # fields created earlier in the same batch. Cross-table references to
    # tables being created in the same batch are not supported yet.
    field_items = sorted(field_items, key=lambda f: f.config.type == "formula")

    for field_item in field_items:
        tool_helpers.raise_if_cancelled()
        tool_helpers.update_status(
            _("Creating field %(field_name)s...") % {"field_name": field_item.name}
        )

        try:
            new_field = CreateFieldActionType.do(
                user,
                table,
                field_item.config.type,
                **field_item.to_django_orm_kwargs(table),
            )
            created_fields.append(FieldItem.from_django_orm(new_field))
        except InvalidFormulaFieldError as e:
            fixed = False
            if formula_fixer:
                try:
                    new_formula = formula_fixer(e.table, e.field_name, e.formula)
                    if new_formula:
                        new_field = CreateFieldActionType.do(
                            user,
                            table,
                            "formula",
                            name=e.field_name,
                            formula=new_formula,
                        )
                        created_fields.append(FieldItem.from_django_orm(new_field))
                        fixed = True
                except Exception:
                    pass
            if not fixed:
                formula_errors.append(
                    {
                        "field_name": e.field_name,
                        "formula": e.formula,
                        "error": e.error,
                    }
                )
        except Exception as e:
            field_errors.append(
                f"Error creating field {field_item.name} in table_{table.id}: {e}.\n"
                f"Please retry recreating this field later, if important."
            )
    return created_fields, field_errors, formula_errors


@dataclass
class FieldDefinition:
    type: Type | None = None
    field_def: Any | None = None
    to_django_orm: Callable[[Any], Any] | None = None
    from_django_orm: Callable[[Any], Any] | None = None


def _get_pydantic_field_definition(
    field_object: FieldObject,
) -> FieldDefinition:
    """
    Returns the Pydantic field type and definition for the given field object.
    """

    orm_field = field_object["field"]
    orm_field_type = field_object["type"]

    match orm_field_type.type:
        case "text":
            return FieldDefinition(
                str | None,
                Field(..., description="Single-line text", title=orm_field.name),
                lambda v: v if v is not None else "",
                lambda v: v if v is not None else "",
            )

        case "long_text":
            return FieldDefinition(
                str | None,
                Field(..., description="Multi-line text", title=orm_field.name),
                lambda v: v if v is not None else "",
                lambda v: v if v is not None else "",
            )
        case "number":
            return FieldDefinition(
                float | None,
                Field(..., description="Number or None", title=orm_field.name),
            )
        case "boolean":
            return FieldDefinition(
                bool, Field(..., description="Boolean", title=orm_field.name)
            )
        case "date":
            if orm_field.date_include_time:
                return FieldDefinition(
                    Datetime | None,
                    Field(..., description="Datetime or None", title=orm_field.name),
                    lambda v: v.to_django_orm() if v else None,
                    lambda v: Datetime.from_django_orm(v) if v is not None else None,
                )
            else:
                return FieldDefinition(
                    Date | None,
                    Field(..., description="Date or None", title=orm_field.name),
                    lambda v: v.to_django_orm() if v else None,
                    lambda v: Date.from_django_orm(v) if v is not None else None,
                )
        case "single_select":
            choices = [option.value for option in orm_field.select_options.all()]

            if not choices:
                return FieldDefinition()  # Unsupported: no options defined

            return FieldDefinition(
                Literal[*choices] | None,
                Field(
                    ...,
                    description=f"One of: {', '.join(choices)} or None",
                    title=orm_field.name,
                ),
                lambda v: v if v in choices else None,
                lambda v: v.value if isinstance(v, OrmSelectOption) else v,
            )
        case "multiple_select":
            choices = [option.value for option in orm_field.select_options.all()]

            if not choices:
                return FieldDefinition()  # Unsupported: no options defined

            return FieldDefinition(
                list[Literal[*choices]],
                Field(
                    ...,
                    description=f"List of any of: {', '.join(choices)} or empty list",
                    title=orm_field.name,
                ),
                lambda v: [opt for opt in v if opt in choices],
                lambda v: [opt.value for opt in v.all()] if v is not None else None,
            )
        case "link_row":
            linked_model = orm_field.link_row_table.get_model()
            linked_primary_key = linked_model.get_primary_field()

            # If there's no primary key, we can't safely work with this field
            if linked_primary_key is None:
                return FieldDefinition()  # Unsupported field type

            # Avoid null or empty values
            linked_pk = linked_primary_key.db_column
            examples = list(
                linked_model.objects.exclude(
                    Q(**{f"{linked_pk}__isnull": True})
                    | Q(**{f"{linked_pk}__exact": ""})
                ).values_list("id", linked_pk)[:10]
            )

            def to_django_orm(value):
                if isinstance(value, str) or isinstance(value, int):
                    value = [value]
                if value is not None:
                    try:
                        return LinkRowFieldType().prepare_value_for_db(orm_field, value)
                    except ValidationError:
                        pass
                return []

            def from_django_orm(value):
                values = [str(v) for v in value.all()]
                if orm_field.link_row_multiple_relationships:
                    return values
                else:
                    return values[0] if values else None

            # Known limitation: assumes the primary field is representable as str.
            if orm_field.link_row_multiple_relationships:
                desc = "List of values (as strings) or IDs (as integers) from the linked table or empty list."
                field_type = list[str | int] | None
            else:
                desc = "Single value (as string) or ID (as integer) from the linked table or empty list."
                field_type = str | int | None
            if examples:
                desc += (
                    " "
                    + f"Examples: {', '.join([f'{{id:{v[0]}, value: `{v[1]}`}}' for v in examples])}, .."
                )
            return FieldDefinition(
                field_type,
                Field(..., description=desc, title=orm_field.name),
                to_django_orm,
                from_django_orm,
            )

        case _:
            return FieldDefinition()  # Unsupported field type


def get_create_row_model(table: Table, field_ids: list[int] | None = None) -> BaseModel:
    """
    Dynamically creates a Pydantic model for the given table based on its fields, to be
    used for row creation and validation.
    """

    model_name = f"Table{table.id}Row"

    field_definitions = {}
    field_conversions = {}

    table_model = table.get_model()
    for field_object in table_model.get_field_objects():
        field_definition = _get_pydantic_field_definition(field_object)
        if field_definition.type is None:
            continue  # Skip unsupported field types
        if field_ids is not None and field_object["field"].id not in field_ids:
            continue  # Skip fields not in the specified list

        field = field_object["field"]
        field_definitions[field.name] = (
            field_definition.type,
            field_definition.field_def,
        )
        field_conversions[field.name] = (
            field.db_column,
            field_definition.to_django_orm,
            field_definition.from_django_orm,
        )

    class TableRowModel(BaseModel):
        model_config = ConfigDict(
            extra="forbid",
        )

        def to_django_orm(self) -> dict[str, Any]:
            orm_data = {}
            for key, value in self.__dict__.items():
                if key == "id":
                    orm_data["id"] = value
                    continue

                if key not in field_conversions or value == "__NO_CHANGE__":
                    continue

                orm_key, to_django_orm, _ = field_conversions[key]
                if to_django_orm:
                    orm_data[orm_key] = to_django_orm(value)
                else:
                    orm_data[orm_key] = value
            return orm_data

        @classmethod
        def from_django_orm(
            cls, orm_row: GeneratedTableModel, field_ids: list[int] | None = None
        ) -> "TableRowModel":
            init_data = {"id": orm_row.id}
            for field_object in orm_row.get_field_objects():
                field = field_object["field"]
                if field.name not in field_conversions:
                    continue
                if field_ids is not None and field.id not in field_ids:
                    continue
                db_column, _, from_django_orm = field_conversions[field.name]
                value = getattr(orm_row, db_column)
                if from_django_orm:
                    init_data[field.name] = from_django_orm(value)
                else:
                    init_data[field.name] = value
            return cls(**init_data)

    return create_model(
        model_name,
        __module__=__name__,
        __base__=TableRowModel,
        **field_definitions,
    )


def get_update_row_model(table) -> BaseModel:
    """Creates an update model where all fields can be NoChange."""

    create_model_class = get_create_row_model(table)

    # Build update fields - all fields become Union[OriginalType, NoChange]
    update_fields = {}

    for field_name, field_info in create_model_class.model_fields.items():
        original_type = field_info.annotation

        update_fields[field_name] = (
            Union[NoChange, original_type],
            Field(
                ...,
                description=f"Use '__NO_CHANGE__' to keep current value. To update, use a {field_info.description}",
            ),
        )

    update_fields["id"] = (int, Field(..., description="The ID of the row to update"))

    # Create the update model
    UpdateRowModel = create_model(
        f"UpdateTable{table.id}Row",
        __base__=create_model_class,
        **update_fields,
    )

    return UpdateRowModel


def get_view(user, workspace, view_id: int):
    return ViewHandler().get_view_as_user(
        user,
        view_id,
        base_queryset=View.objects.filter(table__database__workspace=workspace),
    )


def get_link_row_hints(row_model: type[BaseModel]) -> str:
    """
    Extract link_row field hints from a row model's field descriptions.

    The descriptions are already populated by ``_get_pydantic_field_definition``
    with example values — this just collects the ones that contain "Examples:".
    """

    hints: list[str] = []
    for name, info in row_model.model_fields.items():
        desc = info.description or ""
        if "linked table" in desc and "Examples:" in desc:
            hints.append(f"{name} ({info.title}): {desc}")

    if not hints:
        return ""
    return " LINK_ROW fields: " + "; ".join(hints) + "."


def get_table_rows_tools(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers", table: Table
):
    row_model_for_create = get_create_row_model(table)
    row_model_for_update = get_update_row_model(table)
    link_row_hints = get_link_row_hints(row_model_for_create)

    def _create_rows(
        rows: list[row_model_for_create],
        thought: Annotated[str, "Brief reasoning for calling this tool."],
    ) -> dict[str, Any]:
        """
        Create new rows in the specified table.
        """

        if not rows:
            return {"created_row_ids": []}

        tool_helpers.update_status(
            _("Creating rows in %(table_name)s ") % {"table_name": table.name}
        )

        validated_rows = [row.to_django_orm() for row in rows]

        with transaction.atomic():
            orm_rows = CreateRowsActionType.do(user, table, validated_rows)

        return {"created_row_ids": [r.id for r in orm_rows]}

    create_rows_tool = Tool(
        _create_rows,
        name=f"create_rows_in_table_{table.id}",
        description=(
            f"WHEN: Creating new rows in '{table.name}' (ID: {table.id}). "
            f"WHAT: Inserts up to 20 rows with field values matching the table schema. "
            f"RETURNS: Created row IDs. "
            f"DO NOT USE: For other tables — each table has its own create tool. "
            f"HOW: Fill every field and every relationship with valid data when possible."
            f"{link_row_hints}"
        ),
        max_retries=2,
    )
    create_rows_tool.function_schema.json_schema = inline_refs(
        create_rows_tool.function_schema.json_schema
    )

    def _update_rows(
        rows: list[row_model_for_update],
        thought: Annotated[str, "Brief reasoning for calling this tool."],
    ) -> dict[str, Any]:
        """
        Update existing rows in the specified table.
        """

        if not rows:
            return {"updated_row_ids": []}

        tool_helpers.update_status(
            _("Updating rows in %(table_name)s ") % {"table_name": table.name}
        )

        validated_rows = [row.to_django_orm() for row in rows]

        with transaction.atomic():
            orm_rows = UpdateRowsActionType.do(user, table, validated_rows).updated_rows

        return {"updated_row_ids": [r.id for r in orm_rows]}

    update_rows_tool = Tool(
        _update_rows,
        name=f"update_rows_in_table_{table.id}",
        description=(
            f"WHEN: Updating existing rows in '{table.name}' (ID: {table.id}) by row ID. "
            f"WHAT: Updates specified fields on up to 20 rows. Use '__NO_CHANGE__' to keep a field unchanged. "
            f"RETURNS: Updated row IDs. "
            f"DO NOT USE: For other tables — each table has its own update tool."
            f"{link_row_hints}"
        ),
        max_retries=2,
    )
    update_rows_tool.function_schema.json_schema = inline_refs(
        update_rows_tool.function_schema.json_schema
    )

    def _delete_rows(
        row_ids: list[int],
        thought: Annotated[str, "Brief reasoning for calling this tool."],
    ) -> dict[str, Any]:
        """
        Delete rows in the specified table.
        """

        if not row_ids:
            return {"deleted_row_ids": []}

        tool_helpers.update_status(
            _("Deleting rows in %(table_name)s ") % {"table_name": table.name}
        )

        with transaction.atomic():
            DeleteRowsActionType.do(user, table, row_ids)

        return {"deleted_row_ids": row_ids}

    delete_rows_tool = Tool(
        _delete_rows,
        name=f"delete_rows_in_table_{table.id}",
        description=(
            f"WHEN: Deleting rows from '{table.name}' (ID: {table.id}) by row ID. "
            f"WHAT: Permanently removes up to 20 specified rows. "
            f"RETURNS: Deleted row IDs. "
            f"DO NOT USE: For other tables — each table has its own delete tool."
        ),
    )

    return {
        "create": create_rows_tool,
        "update": update_rows_tool,
        "delete": delete_rows_tool,
    }


def create_view_filter(
    user: AbstractUser,
    orm_view: View,
    table_fields: dict[int, Any],
    view_filter_item: AnyViewFilterItemCreate,
) -> ViewFilter:
    """
    Creates a view filter from the given view filter item.
    """

    field = table_fields.get(view_filter_item.field_id)
    if field is None:
        raise ValueError("Field not found for filter")
    field_type = field_type_registry.get_by_model(field.specific_class)
    if field_type.type != view_filter_item.config.type:
        raise ValueError("Field type mismatch for filter")

    filter_type = view_filter_item.config.get_django_orm_type(field)
    filter_value = view_filter_item.config.get_django_orm_value(
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
