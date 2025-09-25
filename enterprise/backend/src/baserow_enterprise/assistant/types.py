from datetime import datetime, timezone
from enum import StrEnum
from operator import add
from typing import (
    Annotated,
    Any,
    Dict,
    List,
    Literal,
    NamedTuple,
    Optional,
    Sequence,
    TypeVar,
)
from langchain_core.tools import InjectedToolCallId
from langgraph.prebuilt import InjectedState
from django.db import transaction

from loguru import logger
from pydantic import BaseModel, ConfigDict, Field

from baserow.api.utils import validate_data
from baserow.contrib.database.api.rows.serializers import (
    get_batch_row_serializer_class,
    get_row_serializer_class,
)
from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.exceptions import FieldWithSameNameAlreadyExists
from baserow.contrib.database.rows.actions import CreateRowsActionType
from baserow.contrib.database.table.actions import (
    CreateTableActionType,
    DeleteTableActionType,
    UpdateTableActionType,
)
from baserow.core.models import Workspace
from baserow_enterprise.assistant.utils.helpers import generate_tool_call_id, uuid4_str
from .models import AssistantChat as AssistantChatModel

from baserow.contrib.database.models import Database, Table

StateType = TypeVar("StateType", bound=BaseModel)
PartialStateType = TypeVar("PartialStateType", bound=BaseModel)


class WorkspaceUIContext(BaseModel):
    id: int
    name: str


class ApplicationUIContext(BaseModel):
    id: int
    name: str
    type: str


class TableUIContext(BaseModel):
    id: int
    name: str


class ViewUIContext(BaseModel):
    id: int
    name: str
    type: str


class UIContext(BaseModel):
    workspace: WorkspaceUIContext
    application: Optional[ApplicationUIContext] = None
    table: Optional[TableUIContext] = None
    view: Optional[ViewUIContext] = None
    timezone: Optional[str] = Field(
        default="UTC", description="The timezone of the user, e.g. 'Europe/Amsterdam'"
    )

    @classmethod
    def from_database(cls, database: Database, timezone: str) -> "UIContext":
        workspace = database.workspace
        return cls(
            workspace=WorkspaceUIContext(id=workspace.id, name=workspace.name),
            application=ApplicationUIContext(
                id=database.id, name=database.name, type="database"
            ),
            table=None,
            view=None,
            timezone=timezone,
        )

    def _format_ui_context(self) -> str:
        workspace = self.workspace

        parts = [
            self._format_ui_context_section(
                "workspace", id=str(workspace.id), name=workspace.name
            )
        ]
        if self.application is not None:
            parts.append(
                self._format_ui_context_section(
                    self.application.type,
                    id=str(self.application.id),
                    name=self.application.name,
                )
            )
        if self.table is not None:
            parts.append(
                self._format_ui_context_section(
                    "table",
                    id=str(self.table.id),
                    name=self.table.name,
                )
            )
        if self.view is not None:
            parts.append(
                self._format_ui_context_section(
                    f"{self.view.type} view",
                    id=str(self.view.id),
                    name=self.view.name,
                )
            )

        return "\n\n".join(parts)

    def _format_ui_context_section(self, title: str, **content: Dict[str, str]) -> str:
        if not content:
            return ""

        sections = [f"<{title.lower()}>"]
        for key, value in content.items():
            sections.append(f"• {key.capitalize()}: {value}")
        sections.append(f"</{title.lower()}>")
        return "\n".join(sections)

    def __str__(self) -> str:
        return self._format_ui_context()


class BaseMessage(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )
    id: str | None = Field(default=None, description="The unique UUID of the message")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=timezone.utc))

    def should_show_in_ui(self) -> bool:
        """
        Determines if the message should be shown in the UI.

        :return: True if the message should be shown in the UI, False otherwise.
        """

        return True


class ASSISTANT_MESSAGE_TYPE(StrEnum):
    HUMAN = "human"
    AI_MESSAGE = "ai/message"
    AI_INTERRUPT = "ai/interrupt"
    AI_THINKING = "ai/thinking"
    AI_ERROR = "ai/error"
    TOOL_CALL = "tool_call"
    TOOL = "tool"
    CHAT_TITLE = "chat/title"
    UI_NAVIGATION = "ui/navigation"


class HumanMessage(BaseMessage):
    id: str = Field(
        default_factory=uuid4_str,
        description="The unique UUID of the message",
    )
    type: Literal["human"] = ASSISTANT_MESSAGE_TYPE.HUMAN.value
    content: str
    ui_context: Optional[UIContext] = Field(
        default=None, description="The UI context when the message was sent"
    )


class ToolCall(BaseMessage):
    id: str = Field(
        default_factory=generate_tool_call_id,
        description="The unique UUID of the message",
    )
    type: Literal["tool_call"] = Field(
        default=ASSISTANT_MESSAGE_TYPE.TOOL_CALL.value,
        description="`type` needed to conform to the OpenAI shape, which is expected by LangChain",
    )
    name: str
    args: dict[str, Any]

    def should_show_in_ui(self) -> bool:
        # Don't show tool call only messages in the UI
        return False


class ToolCallMessage(BaseMessage):
    id: str = Field(
        default_factory=uuid4_str,
        description="The unique UUID of the message",
    )
    type: Literal["tool"] = ASSISTANT_MESSAGE_TYPE.TOOL.value
    content: str
    tool_call_id: str
    artifact: Optional[Any] = None

    def should_show_in_ui(self) -> bool:
        # Don't show tool call only messages in the UI
        return False


class AiMessage(BaseMessage):
    id: str = Field(
        default_factory=uuid4_str,
        description="The unique UUID of the message",
    )
    type: Literal["ai/message"] = ASSISTANT_MESSAGE_TYPE.AI_MESSAGE.value
    content: str = Field(default="", description="The AI message content")
    tool_calls: Optional[list[ToolCall]] = Field(
        default_factory=list,
        description="The list of tool calls made by the AI in this message.",
    )

    sources: Optional[list[str]] = Field(
        default=None,
        description="The list of relevant source URLs referenced in the message.",
    )

    def should_show_in_ui(self) -> bool:
        # Don't show tool call only messages in the UI
        return not bool(self.tool_calls)


class AiInterruptMessage(BaseMessage):
    id: str = Field(
        default_factory=uuid4_str,
        description="The unique UUID of the message",
    )
    type: Literal["interrupt"] = "ai/interrupt"
    content: str = Field(
        description=(
            "The content of the interrupt message, e.g. an approval or clarification. "
            "This is typically used in human-in-the-loop scenarios."
        ),
    )
    tool_call_id: str | None = Field(
        default=None,
        description=(
            "The tool call ID this interrupt is associated with, if any. This can be used "
            "to correlate the interrupt with a specific tool call in the conversation."
        ),
    )


class THINKING_MESSAGES(StrEnum):
    THINKING = "thinking"
    RUNNING = "running"
    ANSWERING = "answering"
    # Knowledge retrieval
    RETRIEVE_KNOWLEDGE = "retrieve_knowledge"
    ANALYZE_KNOWLEDGE = "analyze_knowledge"
    # Database architect
    DESIGN_SCHEMA = "design_schema"
    IMPLEMENT_SCHEMA = "implement_schema"
    # Human in the loop
    WAITING_FOR_INTERRUPT = "waiting_for_human_in_the_loop"

    # For dynamic messages that don't have a translation in the frontend
    CUSTOM = "custom"


class AiThinkingMessage(BaseMessage):
    type: Literal["ai/thinking"] = ASSISTANT_MESSAGE_TYPE.AI_THINKING.value
    code: str = Field(
        default=THINKING_MESSAGES.CUSTOM,
        description="Thinking content. If empty, signals end of thinking.",
    )
    content: str = Field(
        default="",
        description=(
            "A short description of what the AI is thinking about. It can be used to "
            "provide a dynamic message that don't have a translation in the frontend."
        ),
    )


class NavigateToTableArgs(BaseModel):
    type: Literal["table"] = "table"
    database_id: int
    table_id: int
    table_name: str
    view_id: Optional[int] = None
    view_name: Optional[str] = None


class UiNavigationMessage(BaseMessage):
    type: Literal["ui/navigation"] = "ui/navigation"
    content: str = Field(default="", description="Navigation content.")
    args: NavigateToTableArgs


class AiMessageChunk(BaseModel):
    type: Literal["ai/message"] = "ai/message"
    content: str = Field(description="The content of the AI message chunk")


class ChatTitleMessage(BaseMessage):
    type: Literal["chat/title"] = ASSISTANT_MESSAGE_TYPE.CHAT_TITLE.value
    content: str = Field(description="The chat title")


class AI_ERROR_MESSAGE_CODE(StrEnum):
    RECURSION_LIMIT_EXCEEDED = "recursion_limit_exceeded"
    TIMEOUT = "timeout"
    UNKNOWN = "unknown"


class AiErrorMessage(BaseMessage):
    type: Literal["ai/error"] = ASSISTANT_MESSAGE_TYPE.AI_ERROR.value
    code: AI_ERROR_MESSAGE_CODE = Field(description="The type of error that occurred")
    content: str = Field(description="Error message content")


AIMessageUnion = (
    AiMessage
    | ToolCall
    | ToolCallMessage
    | ChatTitleMessage
    | AiErrorMessage
    | AiThinkingMessage
    | AiInterruptMessage
)
AssistantMessageUnion = HumanMessage | AIMessageUnion


def add_and_merge_messages(
    left: Sequence[AssistantMessageUnion], right: Sequence[AssistantMessageUnion]
) -> Sequence[AssistantMessageUnion]:
    """
    Merges two lists of messages, updating existing messages by ID.
    By default, this ensures the state is "append-only", unless the new message has the
    same ID as an existing message. new message has the same ID as an existing message.

    :param left: The base list of messages.
    :param right: The list of messages to merge into the base list.
    :return: A new list of messages with the messages from `right` merged into `left`.
        If a message in `right` has the same ID as a message in `left`, the message from
        `right` will replace the message from `left`.
    """

    # coerce to list
    left = list(left)
    right = list(right)

    # merge
    left_idx_by_id = {m.id: i for i, m in enumerate(left)}
    merged = left.copy()
    for m in right:
        if (existing_idx := left_idx_by_id.get(m.id)) is not None:
            merged[existing_idx] = m
        else:
            merged.append(m)

    return merged


def add_and_merge_sources(
    left: Optional[list[str]], right: Optional[list[str]]
) -> list[str]:
    """
    Adds two sets of sources together, returning an empty set if either is explicitly
    set to None.

    :param left: The base list of sources.
    :param right: The list of sources to add to the base list.
    :return: A new list of sources with the sources from `right` added to `left`.
        If either `left` or `right` is None, an empty list is returned.
    """

    if left is None or right is None:
        return []

    all_items = set()
    result = []
    for item in left + right:
        if item is not None and item not in all_items:
            all_items.add(item)
            result.append(item)

    return result


class ASSISTANT_GRAPH_NODE(StrEnum):
    TITLE_GENERATOR = "title_generator"
    ROOT = "root"
    ROOT_TOOLS = "root_tools"
    INTERRUPT = "interrupt"
    END = "__end__"


class User(BaseModel):
    id: int
    username: str
    email: str


class Workspace(BaseModel):
    id: int
    name: str


class AssistantChat(BaseModel):
    id: int
    uuid: str
    title: Optional[str] = None
    user: User
    workspace: Workspace
    status: str

    @classmethod
    def from_orm(cls, chat: AssistantChatModel) -> "AssistantChat":
        return cls(
            id=chat.id,
            uuid=str(chat.uuid),
            title=chat.title,
            user=User(
                id=chat.user.id,
                username=chat.user.username,
                email=chat.user.email,
            ),
            workspace=Workspace(
                id=chat.workspace.id,
                name=chat.workspace.name,
            ),
            status=chat.status,
        )


class AssistantExecutionContext(BaseModel):
    chat: AssistantChat

    @classmethod
    def from_orm(cls, chat: AssistantChatModel) -> "AssistantExecutionContext":
        return cls(chat=AssistantChat.from_orm(chat))


# Database architect specific types
Color = Literal[
    "light-blue",
    "light-green",
    "light-cyan",
    "light-orange",
    "light-yellow",
    "light-red",
    "light-brown",
    "light-purple",
    "light-pink",
    "light-gray",
    "blue",
    "green",
    "cyan",
    "orange",
    "yellow",
    "red",
    "brown",
    "purple",
    "pink",
    "gray",
    "dark-blue",
    "dark-green",
    "dark-cyan",
    "dark-orange",
    "dark-yellow",
    "dark-red",
    "dark-brown",
    "dark-purple",
    "dark-pink",
    "dark-gray",
    "darker-blue",
    "darker-green",
    "darker-cyan",
    "darker-orange",
    "darker-yellow",
    "darker-red",
    "darker-brown",
    "darker-purple",
    "darker-pink",
    "darker-gray",
    "deep-dark-green",
    "deep-dark-orange",
]


class BaseFieldType(BaseModel):
    name: str = Field(
        description="The capitalized name of the field. Shorter is better. Use spaces, not underscores. Capitalize the first letter."
    )
    type: str

    def to_orm(self, resource_mapping) -> Dict[str, Any]:
        return {}

    @classmethod
    def from_orm(cls, orm_field) -> Dict[str, Any]:
        return cls(name=orm_field.name)


class TextFieldType(BaseFieldType):
    type: Literal["text"] = "text"


class LongTextFieldType(BaseFieldType):
    type: Literal["long_text"] = "long_text"


class EmailFieldType(BaseFieldType):
    type: Literal["email"] = "email"


class URLFieldType(BaseFieldType):
    type: Literal["url"] = "url"


class NumberFieldType(BaseFieldType):
    type: Literal["number"] = "number"
    decimal_places: int = 2
    negative: bool = False

    def to_orm(self, resource_mapping) -> Dict[str, Any]:
        return {
            "number_decimal_places": self.decimal_places,
            "number_negative": self.negative,
        }

    @classmethod
    def from_orm(cls, orm_field) -> Dict[str, Any]:
        field = orm_field.specific
        return cls(
            name=field.name,
            decimal_places=field.number_decimal_places,
            negative=field.number_negative,
        )


class RatingFieldType(BaseFieldType):
    type: Literal["rating"] = "rating"
    max_rating: int = 5

    def to_orm(self, resource_mapping) -> Dict[str, Any]:
        return {
            "max_value": self.max_rating,
        }

    @classmethod
    def from_orm(cls, orm_field) -> Dict[str, Any]:
        field = orm_field.specific
        return cls(
            name=field.name,
            max_rating=field.max_value,
        )


class DateFieldType(BaseFieldType):
    type: Literal["date"] = "date"
    include_time: bool = False

    def to_orm(self, resource_mapping) -> Dict[str, Any]:
        return {
            "date_include_time": self.include_time,
        }

    @classmethod
    def from_orm(cls, orm_field) -> Dict[str, Any]:
        field = orm_field.specific
        return cls(
            name=field.name,
            include_time=field.date_include_time,
        )


class BooleanFieldType(BaseFieldType):
    type: Literal["boolean"] = "boolean"


class LinkRowFieldType(BaseFieldType):
    type: Literal["link_row"] = "link_row"
    linked_table_name: str = Field(
        description=(
            "The name of the table being linked to. Only link already created tables. "
            "A reverse link will be created automatically."
        )
    )
    multiple: bool = False

    def to_orm(self, resource_mapping) -> Dict[str, Any]:
        linked_table_name = (
            self.linked_table_name.strip().capitalize().replace("_", " ")
        )

        linked_table = resource_mapping["table"][linked_table_name]
        return {
            "link_row_table": linked_table,
            # "link_row_multiple_relationships": self.multiple,
        }

    @classmethod
    def from_orm(cls, orm_field) -> Dict[str, Any]:
        field = orm_field.specific
        return cls(
            name=field.name,
            linked_table_name=field.link_row_table.name,
            multiple=field.link_row_multiple_relationships,
        )


class SelectOption(BaseModel):
    value: str
    color: Color


class SingleSelectFieldType(BaseFieldType):
    type: Literal["single_select"] = "single_select"
    options: list[SelectOption] = Field(
        default_factory=list,
        description="The list of options for the field. Try to find appropriate colors for each option.",
    )

    def to_orm(self, resource_mapping) -> Dict[str, Any]:
        # TODO: Handle existing options and IDs
        return {
            "select_options": [
                {"id": -i, "value": option.value, "color": option.color}
                for (i, option) in enumerate(self.options, start=1)
            ],
        }

    @classmethod
    def from_orm(cls, orm_field) -> Dict[str, Any]:
        field = orm_field.specific
        return cls(
            name=field.name,
            options=[
                SelectOption(value=opt.value, color=opt.color)
                for opt in field.select_options.all()
            ],
        )


class MultipleSelectFieldType(BaseFieldType):
    type: Literal["multiple_select"] = "multiple_select"
    options: list[SelectOption] = Field(
        default_factory=list,
        description="The list of options for the field. Try to find appropriate colors for each option.",
    )

    def to_orm(self, resource_mapping) -> Dict[str, Any]:
        # TODO: Handle existing options and IDs
        return {
            "select_options": [
                {"id": -i, "value": option.value, "color": option.color}
                for (i, option) in enumerate(self.options, start=1)
            ],
        }

    @classmethod
    def from_orm(cls, orm_field) -> Dict[str, Any]:
        field = orm_field.specific
        return cls(
            name=field.name,
            options=[
                SelectOption(value=opt.value, color=opt.color)
                for opt in field.select_options.all()
            ],
        )


class MultipleCollaboratorsFieldType(BaseFieldType):
    type: Literal["multiple_collaborators"] = "multiple_collaborators"


class FileFieldType(BaseFieldType):
    type: Literal["file"] = "file"


AnyFieldType = (
    TextFieldType
    | LongTextFieldType
    #    | EmailFieldType
    #    | URLFieldType
    | NumberFieldType
    | RatingFieldType
    | DateFieldType
    | BooleanFieldType
    | LinkRowFieldType
    | SingleSelectFieldType
    | MultipleSelectFieldType
    #    | MultipleCollaboratorsFieldType
    | FileFieldType
)

field_registry: Dict[str, BaseFieldType] = {
    "text": TextFieldType,
    "long_text": LongTextFieldType,
    "email": EmailFieldType,
    "url": URLFieldType,
    "number": NumberFieldType,
    "rating": RatingFieldType,
    "date": DateFieldType,
    "boolean": BooleanFieldType,
    "link_row": LinkRowFieldType,
    "single_select": SingleSelectFieldType,
    "multiple_select": MultipleSelectFieldType,
    "multiple_collaborators": MultipleCollaboratorsFieldType,
    "file": FileFieldType,
}


class TableSchema(BaseModel):
    id: int
    name: str
    primary_field: TextFieldType
    fields: list[AnyFieldType] = Field(default_factory=list)
    relationships: list[str] = Field(
        default_factory=list, description="Names of linked tables"
    )


class BaseDatabaseSchema(BaseModel):
    id: int
    name: str


class DatabaseSchema(BaseDatabaseSchema):
    tables: dict[str, TableSchema]


class WorkspaceSchema(BaseModel):
    id: int
    name: str
    databases: list[BaseDatabaseSchema] = Field(
        default_factory=list, description="Database IDs and names in the workspace"
    )
    current_database: Optional[DatabaseSchema] = Field(
        default=None, description="The currently active database in the workspace"
    )


class SchemaExecutableOperation(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    type: str

    def execute(self, user, resource_mapping) -> Any:
        pass

    def validate_operation(self, resource_mapping) -> None:
        pass


class TableOperation:
    pass


class StreamableOperation(SchemaExecutableOperation):
    def get_streaming_message(self) -> str:
        return f"Executing operation: {self.type}"


class NavigateToOperation:
    def get_navigation_args(self, resource_mapping) -> Dict[str, Any]:
        raise NotImplementedError()


class CreateTableOperation(StreamableOperation, NavigateToOperation, TableOperation):
    type: Literal["create_table"] = "create_table"
    name: str = Field(description="The name of the new table. Max 20 chars.")
    primary_field_name: str

    def validate_operation(self, resource_mapping) -> None:
        self.name = self.name.strip().capitalize().replace("_", " ")
        self.primary_field_name = (
            self.primary_field_name.strip().capitalize().replace("_", " ")
        )

    def execute(self, user, resource_mapping) -> Table:
        database = list(resource_mapping["database"].values())[0]
        with transaction.atomic():
            table, _ = CreateTableActionType.do(
                user=user,
                database=database,
                name=self.name,
                fill_example=False,
            )
            resource_mapping["table"][self.name] = table

            primary_field = table.get_primary_field().specific
            UpdateFieldActionType.do(
                user,
                primary_field,
                name=self.primary_field_name,
            )
            resource_mapping[f"fields_{table.id}"][
                self.primary_field_name
            ] = primary_field

        return table

    def get_streaming_message(self) -> str:
        return f"Creating table: {self.name}"

    def get_navigation_args(self, resource_mapping) -> Any:
        table = resource_mapping["table"][self.name]
        return NavigateToTableArgs(
            database_id=table.database_id,
            table_id=table.id,
            table_name=table.name,
        )


class UpdateTableOperation(SchemaExecutableOperation, TableOperation):
    type: Literal["update_table"] = "update_table"
    table_name: str
    new_name: str = Field(description="The new name of the table. Max 20 chars.")

    def validate_operation(self, resource_mapping) -> None:
        self.name = self.name.strip().capitalize()
        self.primary_field_name = self.primary_field_name.strip().capitalize()

    def execute(self, user, resource_mapping) -> Table:
        table = resource_mapping["table"].pop(self.table_name)
        with transaction.atomic():
            table, _ = UpdateTableActionType.do(user, table, name=self.new_name)
            resource_mapping["table"][self.new_name] = table


class DeleteTableOperation(SchemaExecutableOperation, TableOperation):
    type: Literal["delete_table"] = "delete_table"
    table_name: str

    def execute(self, user, resource_mapping) -> None:
        table = resource_mapping["table"].pop(self.table_name)

        # TODO: remove all link row fields pointing to this table from resource_mapping
        # or maybe just regenerate it from the database schema each time?
        with transaction.atomic():
            DeleteTableActionType.do(user, table)


class CreateFieldOperation(StreamableOperation):
    type: Literal["create_field"] = "create_field"
    table_name: str
    field: AnyFieldType

    def validate_operation(self, resource_mapping) -> None:
        self.table_name = self.table_name.strip().capitalize().replace("_", " ")
        self.field.name = self.field.name.strip().capitalize().replace("_", " ")

    def execute(self, user, resource_mapping) -> None:
        table = resource_mapping["table"].get(self.table_name)
        if table is None:
            return  # Table must exist

        if resource_mapping[f"fields_{table.id}"].get(self.field.name):
            # Field already exists, skip
            return

        with transaction.atomic():
            try:
                field = CreateFieldActionType.do(
                    user,
                    table,
                    self.field.type,
                    name=self.field.name,
                    **self.field.to_orm(resource_mapping),
                )
                resource_mapping[f"fields_{table.id}"][self.field.name] = field
            except FieldWithSameNameAlreadyExists:
                logger.exception(
                    "Creating field failed: ", resource_mapping[f"fields_{table.id}"]
                )
                # Field already exists, skip
                return
        return field

    def get_streaming_message(self) -> str:
        return f"Creating field: {self.field.name}"


class UpdateFieldOperation(SchemaExecutableOperation):
    type: Literal["update_field"] = "update_field"
    table_name: str
    field_name: str
    field: AnyFieldType

    def validate_operation(self, resource_mapping) -> None:
        self.field.name = self.field.name.strip().capitalize()

    def execute(self, user, resource_mapping) -> None:
        database = list(resource_mapping["database"].values())[0]
        table = resource_mapping["table"].get(self.table_name)
        if table is None:
            table = Table.objects.filter(
                name=self.table_name, database=database
            ).first()
            if table is None:
                return
            resource_mapping["table"][self.table_name] = table

        field = resource_mapping[f"fields_{table.id}"].pop(self.field_name, None)
        if field is None:
            # Try to fetch from the database
            field = table.field_set.filter(name=self.field_name).first()
            if field is None:
                return

        with transaction.atomic():
            field = UpdateFieldActionType.do(
                user,
                field,
                new_type_name=self.field.type,
                name=self.field.name,
                **self.field.to_orm(resource_mapping),
            )
            resource_mapping[f"fields_{table.id}"][self.field.name] = field
        return field


class DeleteFieldOperation(SchemaExecutableOperation):
    type: Literal["delete_field"] = "delete_field"
    table_name: str
    field_name: str

    def execute(self, user, resource_mapping) -> None:
        table = resource_mapping["table"][self.table_name]
        field = resource_mapping[f"fields_{table.id}"].pop(self.field_name)

        if field.primary:
            return  # Can't delete primary field

        with transaction.atomic():
            DeleteFieldActionType.do(user, field)


class DataExecutableOperation(BaseModel):
    type: str

    def execute(self, user, table) -> int:
        return 0


class CreateRowsOperation(DataExecutableOperation):
    type: Literal["create_rows"] = "create_rows"

    def execute(self, user, table) -> None:
        rows_values = getattr(self, "rows_values", None)  # Added dynamically
        if not rows_values:
            return 0

        with transaction.atomic():
            model = table.get_model()
            row_validation_serializer = get_row_serializer_class(
                model, user_field_names=True
            )
            validation_serializer = get_batch_row_serializer_class(
                row_validation_serializer
            )
            data = validate_data(
                validation_serializer,
                {"items": [row.model_dump() for row in rows_values]},
                partial=True,
                return_validated=True,
            )
            rows = CreateRowsActionType.do(user, table, data["items"], model=model)
            return len(rows)


class UpdateRowsOperation(DataExecutableOperation):
    type: Literal["update_rows"] = "update_rows"
    row_ids: List[int]


class DeleteRowsOperation(DataExecutableOperation):
    type: Literal["delete_rows"] = "delete_rows"
    row_ids: List[int]


AnySchemaOperation = (
    CreateTableOperation
    #     | UpdateTableOperation
    #     | DeleteTableOperation
    | CreateFieldOperation
    #     | UpdateFieldOperation
    #     | DeleteFieldOperation
)

AnyDataOperation = CreateRowsOperation | UpdateRowsOperation | DeleteRowsOperation


class ExecutionPlan(BaseModel):
    schema_operations: list[AnySchemaOperation]
    data_operations: list[AnyDataOperation]


class Clarification(NamedTuple):
    question: str
    answer: str


# State
class _SharedDatabaseArchitectState(BaseModel):
    dba_question: str | None = Field(
        default=None,
        description=(
            "An optional follow-up question for refining or clarifying the current plan. "
            "If the user's request is unclear, this should contain a clarification question and "
            "needs_clarification should be set to true. "
            "If the request is already clear, use it to suggest iterative improvements to the plan."
        ),
    )
    dba_needs_clarification: bool | None = Field(
        default=None,
        description="Whether the assistant needs an answer to a clarification question before proceeding.",
    )
    dba_schema_operations_plan: Optional[List[AnySchemaOperation]] = Field(
        default=None,
        description="The list of operations needed to fulfill the user's request, starting from the current schema.",
    )
    dba_markdown_plan_description: str | None = Field(
        default=None,
        description="A markdown formatted super-concise description of the plan to share with the user.",
    )


class DatabaseArchitectState(_SharedDatabaseArchitectState):
    dba_instructions: Optional[str] = Field(
        default=None,
        description="If set, contains the instructions for the database architect.",
    )


class PartialDatabaseArchitectState(_SharedDatabaseArchitectState):
    pass


class _SharedDataManagerState(BaseModel):
    dma_needs_clarification: bool | None = Field(
        default=None,
        description="Whether the data manager needs clarification before proceeding.",
    )
    dma_data_operations_plan: Optional[List[AnyDataOperation]] = Field(
        default=None,
        description="The list of data operations to be executed.",
    )


class DataManagerState(_SharedDataManagerState):
    dma_instructions: Optional[str] = Field(
        default=None,
        description="If set, contains the instructions for the data manager.",
    )


class PartialDataManagerState(_SharedDataManagerState):
    pass


class TaskPlan(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    id: str = Field(description="Unique identifier for this task")
    description: str = Field(
        description="Human-readable description of what this task does"
    )
    status: Literal["pending", "in_progress", "completed", "failed"] = Field(
        description="Current status of this task. Default is 'pending'.",
    )
    dependencies: List[str] = Field(
        description="IDs of tasks that must complete before this one",
    )
    # result: Optional[str] = Field(description="Result from task execution")


def merge_task_plans(existing: List[TaskPlan], new: List[TaskPlan]) -> List[TaskPlan]:
    """Merge task plans, updating existing tasks with new status."""
    if not new:
        return existing
    if not existing:
        return new

    # Create a mapping of existing tasks
    existing_map = {task.id: task for task in existing}

    # Update or add tasks
    for task in new:
        if task.id in existing_map:
            # Update existing task
            existing_map[task.id] = task
        else:
            # Add new task
            existing_map[task.id] = task

    return list(existing_map.values())


class _SharedPlannerState(BaseModel):
    task_plan: Optional[List[TaskPlan]] = Field(
        default=None, description="List of tasks to be executed in sequence"
    )
    current_task_id: Optional[str] = Field(
        default=None, description="ID of the currently executing task"
    )
    plan_mode_active: bool | None = Field(
        default=None, description="Whether the assistant is in planning mode"
    )


class PlannerState(_SharedPlannerState):
    task_plan: Annotated[List[TaskPlan], merge_task_plans] = Field(
        default_factory=list, description="List of tasks to be executed in sequence"
    )


class PartialPlannerState(_SharedPlannerState):
    pass


class _SharedState(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
    )

    ui_context: Optional[UIContext] = Field(
        default=None,
        description="The UI context the assistant is operating in.",
    )


class AssistantState(
    _SharedState, DatabaseArchitectState, DataManagerState, PlannerState
):
    messages: Annotated[
        Sequence[AssistantMessageUnion], add_and_merge_messages
    ] = Field(default=[])
    sources: Annotated[list[str], add_and_merge_sources] = Field(
        default_factory=list,
        description="The list of relevant source URLs referenced in the last user message.",
    )


class PartialAssistantState(
    _SharedState,
    PartialDatabaseArchitectState,
    PartialDataManagerState,
    PartialPlannerState,
):
    messages: Sequence[AssistantMessageUnion] = Field(default=[])
    sources: Optional[list[str]] = Field(
        default_factory=list,
        description=(
            "The list of relevant source URLs referenced in the last user message. "
            "Explicitly setting this to None will clear the sources in the state."
        ),
    )


class BaseToolArgsSchema(BaseModel):
    tool_call_id: Annotated[str, InjectedToolCallId]
    state: Annotated[AssistantState, InjectedState]
