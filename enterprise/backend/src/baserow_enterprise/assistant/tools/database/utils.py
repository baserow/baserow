from dataclasses import dataclass
from itertools import groupby
from typing import TYPE_CHECKING, Any, Callable, Literal, Type, Union

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Q, QuerySet
from django.utils.translation import gettext as _

import udspy
from pydantic import ConfigDict, Field, create_model
from udspy.utils import minimize_schema, resolve_json_schema_reference

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

from .types import (
    AnyFieldItem,
    AnyFieldItemCreate,
    AnyViewFilterItemCreate,
    BaseModel,
    Date,
    Datetime,
    field_item_registry,
)

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers

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
    for table_id, fields_in_table in groupby(fields, lambda f: f.table_id):
        fields_in_table = list(fields_in_table)
        table = next(t for t in tables if t.id == table_id)
        primary_field = next(f for f in fields if f.primary)
        primary_field_item = field_item_registry.from_django_orm(primary_field)

        table_items.append(
            TableItem(
                id=table.id,
                name=table.name,
                primary_field=primary_field_item,
                fields=[
                    field_item_registry.from_django_orm(f)
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
    field_items: list[AnyFieldItemCreate],
    tool_helpers: "ToolHelpers",
) -> list[AnyFieldItem]:
    created_fields = []
    for field_item in field_items:
        tool_helpers.update_status(
            _("Creating field %(field_name)s...") % {"field_name": field_item.name}
        )

        new_field = CreateFieldActionType.do(
            user,
            table,
            field_item.type,
            **field_item.to_django_orm_kwargs(table),
        )
        created_fields.append(field_item_registry.from_django_orm(new_field))
    return created_fields


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
            linked_values = list(
                linked_model.objects.exclude(
                    Q(**{f"{linked_pk}__isnull": True})
                    | Q(**{f"{linked_pk}__exact": ""})
                ).values_list(linked_pk, flat=True)[:10]
            )
            examples = f"Examples: {', '.join([str(v) for v in linked_values])}"

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

            # TODO: verify this can work with every possible primary field type
            if orm_field.link_row_multiple_relationships:
                desc = "List of values (as strings) or IDs (as integers) from the linked table or empty list."
                field_type = list[str | int] | None
            else:
                desc = "Single value (as string) or ID (as integer) from the linked table or empty list."
                field_type = str | int | None
            if examples:
                desc += " " + examples
            return FieldDefinition(
                field_type,
                Field(None, description=desc, title=orm_field.name),
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


def get_view(user, view_id: int):
    return ViewHandler().get_view_as_user(user, view_id)


def get_table_rows_tools(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers", table: Table
):
    row_model_for_create = get_create_row_model(table)
    row_model_for_update = get_update_row_model(table)
    row_model_for_response = create_model(
        f"ResponseTable{table.id}Row",
        id=(int, ...),
        __base__=row_model_for_create,
    )

    def _create_rows(
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Create new rows in the specified table.
        """

        nonlocal user, workspace, tool_helpers, row_model_for_create, row_model_for_response

        if not rows:
            return []

        tool_helpers.update_status(
            _("Creating rows in %(table_name)s ") % {"table_name": table.name}
        )

        with transaction.atomic():
            orm_rows = CreateRowsActionType.do(
                user,
                table,
                [row_model_for_create(**row).to_django_orm() for row in rows],
            )

        return {"created_row_ids": [r.id for r in orm_rows]}

    create_row_model_schema = minimize_schema(
        resolve_json_schema_reference(row_model_for_create.model_json_schema())
    )
    create_rows_tool = udspy.Tool(
        func=_create_rows,
        name=f"create_rows_in_table_{table.id}",
        description=f"Creates new rows in the table {table.name} (ID: {table.id}). Max 20 rows at a time.",
        args={
            "rows": {
                "items": create_row_model_schema,
                "type": "array",
                "maxItems": 20,
            }
        },
    )

    def _update_rows(
        rows: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Update existing rows in the specified table.
        """

        nonlocal user, workspace, tool_helpers, row_model_for_update

        if not rows:
            return []

        tool_helpers.update_status(
            _("Updating rows in %(table_name)s ") % {"table_name": table.name}
        )

        with transaction.atomic():
            orm_rows = UpdateRowsActionType.do(
                user,
                table,
                [row_model_for_update(**row).to_django_orm() for row in rows],
            ).updated_rows

        return {"updated_row_ids": [r.id for r in orm_rows]}

    update_row_model_schema = minimize_schema(
        resolve_json_schema_reference(row_model_for_update.model_json_schema())
    )
    update_rows_tool = udspy.Tool(
        func=_update_rows,
        name=f"update_rows_in_table_{table.id}",
        description=f"Updates existing rows in the table {table.name} (ID: {table.id}), identified by their row IDs. Max 20 at a time.",
        args={
            "rows": {
                "items": update_row_model_schema,
                "type": "array",
                "maxItems": 20,
            }
        },
    )

    def _delete_rows(row_ids: list[int]) -> str:
        """
        Delete rows in the specified table.
        """

        nonlocal user, workspace, tool_helpers

        if not row_ids:
            return

        tool_helpers.update_status(
            _("Deleting rows in %(table_name)s ") % {"table_name": table.name}
        )

        with transaction.atomic():
            DeleteRowsActionType.do(user, table, row_ids)

        return {"deleted_row_ids": row_ids}

    delete_rows_tool = udspy.Tool(
        func=_delete_rows,
        name=f"delete_rows_in_table_{table.id}",
        description=f"Deletes rows in the table {table.name} (ID: {table.id}). Max 20 at a time.",
        args={
            "row_ids": {
                "items": {"type": "integer"},
                "type": "array",
                "maxItems": 20,
            }
        },
    )

    return {
        "create": create_rows_tool,
        "update": update_rows_tool,
        "delete": delete_rows_tool,
    }


def create_view_filter(
    user: AbstractUser,
    orm_view: View,
    table_fields: list[Field],
    view_filter_item: AnyViewFilterItemCreate,
) -> ViewFilter:
    """
    Creates a view filter from the given view filter item.
    """

    field = table_fields.get(view_filter_item.field_id)
    if field is None:
        raise ValueError("Field not found for filter")
    field_type = field_type_registry.get_by_model(field.specific_class)
    if field_type.type != view_filter_item.type:
        raise ValueError("Field type mismatch for filter")

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
