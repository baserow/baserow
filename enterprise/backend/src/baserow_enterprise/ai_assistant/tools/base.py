from datetime import datetime
from typing import List, Dict, Any, Literal, Optional, Tuple
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field, create_model
from asgiref.sync import sync_to_async

from baserow.contrib.database.models import Database, Table
from baserow.contrib.database.table.models import GeneratedTableModel
from baserow_enterprise.ai_assistant.utils.types import AssistantState
from django.contrib.auth.models import AbstractUser
from baserow.core.models import Workspace
from langchain_core.runnables import RunnableConfig
from baserow.contrib.database.table.handler import TableHandler
from django.db.models import Q, F
from datetime import date, datetime
from decimal import Decimal
from typing import List, Dict, Any, Literal, Optional, Tuple, Annotated, Type
from langchain_core.tools import BaseTool
from pydantic import BaseModel, Field
from asgiref.sync import sync_to_async

from baserow.contrib.database.models import Database, Table
from baserow.contrib.database.table.models import GeneratedTableModel
from django.contrib.auth.models import AbstractUser
from baserow.core.models import Workspace
from langchain_core.runnables import RunnableConfig
from django.db.models import F


from pydantic import BaseModel, Field, create_model
from baserow.contrib.database.fields.models import Field as BaserowField

EMPTY = object()


class BaserowToolError(BaseModel):
    """Error artifact for table finder tool."""

    status: Literal["error"] = "error"
    args: Dict[str, Any] = Field(default_factory=dict)
    error: str


class BaserowBaseTool(BaseTool):
    response_format: Literal["content_and_artifact"] = "content_and_artifact"

    _user: AbstractUser
    _workspace: Workspace

    def _init_run(self, config: RunnableConfig) -> None:
        """Initialize the tool with user and workspace from the config."""

        configurable = config.get("configurable", {})
        self._user = configurable.get("user")
        self._workspace = configurable.get("workspace")

    def _run(self, *args, config: RunnableConfig, **kwargs) -> Tuple[str, Any]:
        self._init_run(config)
        return self._run_impl(*args, **kwargs)

    async def _arun(self, *args, config: RunnableConfig, **kwargs) -> Tuple[str, Any]:
        self._init_run(config)
        return await sync_to_async(self._run_impl)(*args, **kwargs)

    def _run_impl(self, *args, **kwargs):
        raise NotImplementedError()


def create_field_type(field: BaserowField) -> tuple:
    """Convert Baserow field types to Pydantic field types"""

    if field.read_only:
        return

    baserow_field_type = field.get_type()

    if baserow_field_type.type == "text" or baserow_field_type.type == "long_text":
        return Optional[str], Field(
            description=f"Name: {field.name}. Type: {baserow_field_type.type}.",
            default=EMPTY,
        )

    if baserow_field_type.type == "email":
        return Optional[str], Field(
            description=f"Name: {field.name}. Type: {baserow_field_type.type}.",
            default=EMPTY,
        )

    if baserow_field_type.type == "url":
        return Optional[str], Field(
            description=f"Name: {field.name}. Type: {baserow_field_type.type}.",
            default=EMPTY,
        )

    if baserow_field_type.type == "number":
        kwargs = {"default": EMPTY}
        if not field.number_negative:
            kwargs["ge"] = 0
        return Optional[Decimal], Field(
            description=f"Name: {field.name}. Type: {baserow_field_type.type}.",
            **kwargs,
        )

    if baserow_field_type.type == "boolean":
        return Optional[bool], Field(
            description=f"Name: {field.name}. Type: {baserow_field_type.type}.",
            default=EMPTY,
        )

    if baserow_field_type.type == "date":
        if field.date_include_time:
            return Optional[datetime], Field(
                description=f"Name: {field.name}. Type: {baserow_field_type.type}.",
                default=EMPTY,
            )
        else:
            return Optional[date], Field(description=field.name, default=EMPTY)

    def get_options():
        return [{"ID": f.id, "Value": f.value} for f in field.select_options.all()]

    if baserow_field_type.type == "single_select":
        return (
            Optional[int],
            Field(
                default=EMPTY,
                description=f"Name: {field.name}. Type: {baserow_field_type.type}. Select one ID from: {get_options()}",
            ),
        )

    if baserow_field_type.type == "multiple_select":
        return (
            Optional[list[int]],
            Field(
                default=EMPTY,
                description=f"Name: {field.name}. Type: {baserow_field_type.type}. Select multiple IDs from: {get_options()}",
            ),
        )

    def get_linked_rows(limit=50):
        linked_rows = []
        if field.link_row_table_id:
            linked_rows = list(
                field._related_model.objects.annotate(
                    value=F(field.link_row_table_primary_field.db_column)
                ).values("id", "value")[:limit]
            )
        # format them
        return "\n".join(
            [f"ID: {row['id']}, Value: {row['value']}" for row in linked_rows]
        )

    if baserow_field_type.type == "link_row":
        linked_table_name = field.link_row_table.name
        return (
            Optional[list[int]],
            Field(
                default=EMPTY,
                description=(
                    f"""
                    Name: {field.name}.  Type: {baserow_field_type.type}.
                    Link to table {linked_table_name} (ID {field.link_row_table_id}). 
                    Select a linked row ID from: {get_linked_rows()}
                    """
                ),
            ),
        )

    if baserow_field_type.type == "multiple_collaborators":
        available_collaborators = "".join(
            f"ID: {u.id}, Name: {u.get_full_name()}\n"
            for u in field.table.database.workspace.users.order_by("first_name")
        )
        return (
            Optional[list[int]],
            Field(
                default=EMPTY,
                description=f"Name: {field.name}. Select multiple collaborator IDs from:\n{available_collaborators}",
            ),
        )


def create_row_model(
    table_model: GeneratedTableModel, include_id: bool = False
) -> Type[BaseModel]:
    """Dynamically create a Pydantic model based on table schema"""

    fields = {}

    for field_object in table_model.get_field_objects():
        field = field_object["field"]
        res = create_field_type(field)
        if res is None:
            continue
        field_type, field_info = res
        fields[field.db_column] = (field_type, field_info)

    model_name = f"{table_model.baserow_table.name.replace(' ', '_')}_RowSchema"
    if include_id:
        fields["id"] = (int, Field(description="The unique ID of the row"))
        model_name += "_WithID"

    return create_model(model_name, **fields)
