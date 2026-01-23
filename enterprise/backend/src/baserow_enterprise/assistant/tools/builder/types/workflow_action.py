from typing import Annotated, Literal, Optional

from pydantic import Field

from baserow.core.formula.types import (
    BaserowFormulaObject,
)
from baserow_enterprise.assistant.tools.database.utils import filter_tables
from baserow_enterprise.assistant.types import BaseModel


class WorkflowActionBase(BaseModel):
    """Base for workflow actions."""

    element_ref: Optional[str] = Field(
        default=None,
        description="Reference to the element this action is attached to (use if element was just created)",
    )
    element_id: Optional[int] = Field(
        default=None,
        description="ID of existing element this action is attached to (use for existing elements)",
    )
    event: Literal["click", "submit", "after_login"] = Field(
        default="click", description="Event that triggers the action"
    )


class NotificationActionCreate(WorkflowActionBase):
    """Show a notification to the user."""

    type: Literal["notification"] = "notification"
    title: str = Field(
        ..., description="Notification title formula. Wrap in quotes for static text."
    )
    description: str = Field(
        default="",
        description="Notification message formula. Wrap in quotes for static text.",
    )

    def get_action_type(self) -> str:
        return "notification"

    def to_orm_kwargs(self) -> dict:
        return {
            "title": BaserowFormulaObject.create(self.title),
            "description": BaserowFormulaObject.create(self.description),
        }


class OpenPageActionCreate(WorkflowActionBase):
    """Navigate to another page."""

    type: Literal["open_page"] = "open_page"
    navigate_to_page_id: int = Field(..., description="Target page ID")
    page_parameters: list[dict] = Field(
        default_factory=list, description="List of {name, value} for page params"
    )
    query_parameters: list[dict] = Field(
        default_factory=list, description="List of {name, value} for query params"
    )
    target: Literal["self", "blank"] = Field(default="self")

    def get_action_type(self) -> str:
        return "open_page"

    def to_orm_kwargs(self) -> dict:
        return {
            "navigation_type": "page",
            "navigate_to_page_id": self.navigate_to_page_id,
            "page_parameters": [
                {"name": p["name"], "value": BaserowFormulaObject.create(p["value"])}
                for p in self.page_parameters
            ],
            "query_parameters": [
                {"name": p["name"], "value": BaserowFormulaObject.create(p["value"])}
                for p in self.query_parameters
            ],
            "target": self.target,
        }


class CreateRowActionCreate(WorkflowActionBase):
    """Create a new row in a table."""

    type: Literal["create_row"] = "create_row"
    table_id: int = Field(...)
    field_values: dict[int, str] = Field(
        ...,
        description=(
            "Mapping of field_id to value/formula. "
            "If it's a form action, a common formula is `get('form_data.123') to get form data for the element with ID 123.`"
        ),
    )

    def get_action_type(self) -> str:
        return "create_row"

    def get_service_type(self) -> str:
        return "local_baserow_upsert_row"

    def to_service_kwargs(self, user, workspace) -> dict:
        table = filter_tables(user, workspace).filter(id=self.table_id).first()
        return {
            "table": table,
        }

    def get_field_mappings(self) -> list[dict]:
        """Get field mappings for the service."""

        return [
            {"field_id": field_id, "value": BaserowFormulaObject.create(value)}
            for field_id, value in self.field_values.items()
        ]


class UpdateRowActionCreate(WorkflowActionBase):
    """Update an existing row."""

    type: Literal["update_row"] = "update_row"
    table_id: int = Field(...)
    row_id: str = Field(..., description="Row ID formula")
    field_values: dict[int, str] = Field(
        ...,
        description=(
            "Mapping of field_id to value/formula. "
            "If it's a form action, a common formula is `get('form_data.123') to get form data for the element with ID 123.` "
            "For the row ID, you can use formulas like `get('page_parameter.id')`, with id being the page parameter name."
        ),
    )

    def get_action_type(self) -> str:
        return "update_row"

    def get_service_type(self) -> str:
        return "local_baserow_upsert_row"

    def to_service_kwargs(self, user, workspace) -> dict:
        table = filter_tables(user, workspace).filter(id=self.table_id).first()
        return {
            "table": table,
            "row_id": BaserowFormulaObject.create(self.row_id),
        }

    def get_field_mappings(self) -> list[dict]:
        """Get field mappings for the service."""

        return [
            {"field_id": field_id, "value": BaserowFormulaObject.create(value)}
            for field_id, value in self.field_values.items()
        ]


class DeleteRowActionCreate(WorkflowActionBase):
    """Delete a row."""

    type: Literal["delete_row"] = "delete_row"
    table_id: int = Field(...)
    row_id: str = Field(..., description="Row ID formula")

    def get_action_type(self) -> str:
        return "delete_row"

    def get_service_type(self) -> str:
        return "local_baserow_delete_row"

    def to_service_kwargs(self, user, workspace) -> dict:
        table = filter_tables(user, workspace).filter(id=self.table_id).first()
        return {
            "table": table,
            "row_id": BaserowFormulaObject.create(self.row_id),
        }


class RefreshDataSourceActionCreate(WorkflowActionBase):
    """Refresh a data source."""

    type: Literal["refresh_data_source"] = "refresh_data_source"
    data_source_id: Optional[int] = Field(
        default=None, description="Data source ID (resolved from data_source_ref)"
    )

    def get_action_type(self) -> str:
        return "refresh_data_source"

    def to_orm_kwargs(self) -> dict:
        return {
            "data_source_id": self.data_source_id,
        }


class LogoutActionCreate(WorkflowActionBase):
    """Logout the current user."""

    type: Literal["logout"] = "logout"

    def get_action_type(self) -> str:
        return "logout"

    def to_orm_kwargs(self) -> dict:
        return {}


AnyWorkflowActionCreate = Annotated[
    NotificationActionCreate
    | OpenPageActionCreate
    | CreateRowActionCreate
    | UpdateRowActionCreate
    | DeleteRowActionCreate
    | RefreshDataSourceActionCreate
    | LogoutActionCreate,
    Field(discriminator="type"),
]


class WorkflowActionItem(BaseModel):
    """Existing workflow action with ID."""

    id: int = Field(..., description="Workflow action ID")
    type: str = Field(..., description="Action type")
    element_id: Optional[int] = Field(default=None, description="Element ID")
    event: str = Field(..., description="Trigger event")

    @classmethod
    def from_orm(cls, action) -> "WorkflowActionItem":
        """Create WorkflowActionItem from ORM BuilderWorkflowAction instance."""

        return cls(
            id=action.id,
            type=action.get_type().type,
            element_id=action.element_id,
            event=action.event,
        )
