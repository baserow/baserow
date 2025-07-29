from collections import defaultdict
from datetime import datetime, timezone
from typing import Annotated, Any, List, Literal, Self, Tuple
from uuid import uuid4
from zoneinfo import ZoneInfo
from pydantic import Field, BaseModel
import yaml
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.actions import (
    CreateViewActionType,
    DeleteViewActionType,
    UpdateViewActionType,
)
from baserow.contrib.database.views.models import DEFAULT_SORT_TYPE_KEY, View
from baserow_enterprise.ai_assistant.tools.base import BaserowBaseTool
from django.contrib.auth.models import AbstractUser
from django.conf import settings
from langchain_core.tools.base import InjectedToolArg
from asgiref.sync import sync_to_async
from django.db.models import F
from langchain_core.prompts import ChatPromptTemplate
from langchain.chat_models import init_chat_model
from baserow.contrib.database.views.handler import ViewHandler


class CreateViewArgs(BaseModel):
    view_name: str = Field(description="The name of the view to create.")
    view_type: Literal["grid", "calendar", "kanban", "gallery"] = Field(
        default="grid", description="The type of view to create. Defaults to 'grid'."
    )
    ownership_type: Literal["collaborative", "personal"] = Field(
        default="collaborative",
        description="The ownership type of the view. Always use the default unless specified otherwise.",
    )


class FilterDefinition(BaseModel):
    field_id: int
    filter_name: str
    value: str


class FilterGroupDefinition(BaseModel):
    operator: Literal["AND", "OR"] = "AND"
    filters: list[FilterDefinition] = []
    children: list[Self] = []


class SortDefinition(BaseModel):
    field_id: int
    order: Literal["ASC", "DESC"] = "ASC"


class SortsDefinition(BaseModel):
    sorts: list[SortDefinition] = []


AVAILABLE_FILTERS = {
    "boolean": [
        {
            "filter_name": "boolean",
            "value_description": "Filter by boolean values. Accepts the strings '0' for false and '1' for true.",
        },
    ],
    "date": [
        {
            "filter_name": "date_is_before",
            "filter_description": "Filter all rows where the date is before the given date.",
            "value_description": "The value must be a date in the ISO format.",
        },
        {
            "filter_name": "date_is_after",
            "filter_description": "Filter all rows where the date is after the given date.",
            "value_description": "The value must be a date in the ISO format.",
        },
        {
            "filter_name": "empty",
            "filter_description": "Filter all rows where the date is missing.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "not_empty",
            "filter_description": "Filter all rows where the date is present.",
            "value_description": "An empty string.",
        },
    ],
    "text": [
        {
            "filter_name": "contains",
            "filter_description": "Filter all rows where the text contains the given value (case insensitive).",
            "value_description": "The value must be a string.",
        },
        {
            "filter_name": "contains_not",
            "filter_description": "Filter all rows where the text doesn't contain the given value (case insensitive).",
            "value_description": "The value must be a string.",
        },
        {
            "filter_name": "empty",
            "filter_description": "Filter all rows where the text is empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "not_empty",
            "filter_description": "Filter all rows where the text is not empty.",
            "value_description": "An empty string.",
        },
    ],
    "number": [
        {
            "filter_name": "higher_than",
            "filter_description": "Filter all rows where the number is higher than the given value.",
            "value_description": "The value must be a string representing a number.",
        },
        {
            "filter_name": "lower_than",
            "filter_description": "Filter all rows where the number is lower than the given value.",
            "value_description": "The value must be a string representing a number.",
        },
        {
            "filter_name": "empty",
            "filter_description": "Filter all rows where the number is present.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "not_empty",
            "filter_description": "Filter all rows where the number is missing.",
            "value_description": "An empty string.",
        },
    ],
    "link_row": [
        {
            "filter_name": "link_row_has",
            "filter_description": "Filter all rows where the link row field contains the provided ID.",
            "value_description": "The ID of the linked row.",
        },
        {
            "filter_name": "link_row_has_not",
            "filter_description": "Filter all rows where the link row field doesn't contain the provided ID.",
            "value_description": "The ID of the linked row.",
        },
        {
            "filter_name": "empty",
            "filter_description": "Filter all rows where the text is empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "not_empty",
            "filter_description": "Filter all rows where the text is not empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "link_row_contains",
            "filter_description": "Filter all rows where the link row field contains the provided value",
            "value_description": "The value of the linked row.",
        },
        {
            "filter_name": "link_row_not_contains",
            "filter_description": "Filter all rows where the link row field doesn't contain the provided value.",
            "value_description": "The value of the linked row.",
        },
    ],
    "single_select": [
        {
            "filter_name": "empty",
            "filter_description": "Filter all rows where the text is empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "not_empty",
            "filter_description": "Filter all rows where the text is not empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "is_any_of",
            "filter_description": "Filter all rows where the single select field is any of the provided values.",
            "value_description": "A comma separated list of option IDs.",
        },
        {
            "filter_name": "is_none_of",
            "filter_description": "Filter all rows where the single select field is none of the provided values.",
            "value_description": "A comma separated list of option IDs.",
        },
        {
            "filter_name": "contains",
            "filter_description": "Filter all rows where the text contains the given value (case insensitive).",
            "value_description": "The value must be a string.",
        },
        {
            "filter_name": "contains_not",
            "filter_description": "Filter all rows where the text doesn't contain the given value (case insensitive).",
            "value_description": "The value must be a string.",
        },
    ],
    "multiple_select": [
        {
            "filter_name": "empty",
            "filter_description": "Filter all rows where the text is empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "not_empty",
            "filter_description": "Filter all rows where the text is not empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "multiple_select_has",
            "filter_description": "Filter all rows where the multiple select field is any of the provided values.",
            "value_description": "A comma separated list of option IDs.",
        },
        {
            "filter_name": "multiple_select_has_not",
            "filter_description": "Filter all rows where the multiple select field is none of the provided values.",
            "value_description": "A comma separated list of option IDs.",
        },
        {
            "filter_name": "contains",
            "filter_description": "Filter all rows where the text contains the given value (case insensitive).",
            "value_description": "The value must be a string.",
        },
        {
            "filter_name": "contains_not",
            "filter_description": "Filter all rows where the text doesn't contain the given value (case insensitive).",
            "value_description": "The value must be a string.",
        },
    ],
    "multiple_collaborators": [
        {
            "filter_name": "empty",
            "filter_description": "Filter all rows where the text is empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "not_empty",
            "filter_description": "Filter all rows where the text is not empty.",
            "value_description": "An empty string.",
        },
        {
            "filter_name": "multiple_collaborators_has",
            "filter_description": "Filter all rows where the multiple collaborators field is any of the provided values.",
            "value_description": "A comma separated list of user IDs.",
        },
        {
            "filter_name": "multiple_collaborators_has_not",
            "filter_description": "Filter all rows where the multiple collaborators field is none of the provided values.",
            "value_description": "A comma separated list of user IDs.",
        },
    ],
}

FILTER_TOOL_PROMPT = """
You are the Baserow AI View filter specialist. Your job is to assist users in creating and managing filters for their table views.

CAPABILITIES:
- Define the final filters state based on user input

KEY INSTRUCTIONS:
- NEver assume filter/row state as other users may modify them, always start from the current state.
- To remove all the filters return an empty list as finale state.

TABLE SCHEMA:
{table_schema}

AVAILABLE FILTERS:
{available_filters}

FILTER USAGE EXAMPLES:
- field_id: 7547, filter_name: contains, value: "Davide Silvestri"
- field_id: 7546, filter_name: boolean, value: "1"
- field_id: 7548, filter_name: higher_than, value: "2"
- field_id: 7566, filter_name: date_is_after, value: "2025-05-31"
- field_id: 7545, filter_name: empty, value: ""


CURRENTLY FILTERED BY:
{current_filters}

CURRENT USER:
ID: {user_id}
Email: {user_email}
Name: {user_name}

CURRENT DATE:
{current_date}

TIMEZONE:
{timezone}
"""

SORT_TOOL_PROMPT = """
You are the Baserow AI View sort specialist. Your job is to assist users in creating and managing sorts for their table views.

CAPABILITIES:
- Define the final sort state based on user input

KEY INSTRUCTIONS:
- Never assume sort/row state as other users may modify them, always verify the current state before making changes.
- The sort order is crucial, so make sure to maintain it when adding or removing sorts.
- To remove all the sorts return an empty list as finale state.

TABLE SCHEMA:
{table_schema}

SORTABLE FIELD IDS:
{available_sorts}

CURRENTLY SORTED BY:
{current_sorts}
"""

GROUP_BY_TOOL_PROMPT = """
You are the Baserow AI View group by specialist. Your job is to assist users in creating and managing group bys for their table views.

CAPABILITIES:
- Define the final group by state based on user input

KEY INSTRUCTIONS:
- Never assume group by/row state as other users may modify them, always verify the current state before making changes.
- The group by order is crucial, so make sure to maintain it when adding or removing group bys.
- To remove all the group bys return an empty list as finale state.

TABLE SCHEMA:
{table_schema}

GROUP BY FIELD IDS:
{available_group_bys}

CURRENTLY GROUPED BY:
{current_group_bys}
"""

COLOR_TOOL_PROMPT = """
You are the Baserow AI View color specialist. Your job is to assist users in creating and managing colors for their table views.

CAPABILITIES:
- Define the final colors state based on user input

KEY INSTRUCTIONS:
- Never assume color state as other users may modify them, always start from the current state.
- To remove all the colors return an empty list as finale state.
- Keep the previous colors when possible, unless the request is to replace them.

TABLE SCHEMA:
{table_schema}

AVAILABLE FILTERS FOR COLORS:
{available_filters}

FILTER USAGE EXAMPLES:
- field_id: 7547, filter_name: contains, value: "Davide Silvestri"
- field_id: 7546, filter_name: boolean, value: "1"
- field_id: 7548, filter_name: higher_than, value: "2"
- field_id: 7566, filter_name: date_is_after, value: "2025-05-31"
- field_id: 7545, filter_name: empty, value: ""


CURRENTLY COLORED BY:
{current_colors}

CURRENT USER:
ID: {user_id}
Email: {user_email}
Name: {user_name}

CURRENT DATE:
{current_date}

TIMEZONE:
{timezone}
"""


class UpdateViewArgs(BaseModel):
    name: str | None = Field(default=None, description="The new name of the view.")
    ownership_type: Literal["collaborative", "personal"] | None = Field(
        default=None,
        description="The new ownership type of the view.",
    )
    public: bool | None = Field(
        default=None, description="Whether the view is public or not."
    )
    public_view_password: str | None = Field(
        default=None, description="The password for the public view."
    )


class DynamicViewToolFactory:
    """Factory for creating row manipulation tools based on table schema"""

    @classmethod
    async def create_view_tool(
        cls, user: AbstractUser, table: Table
    ) -> BaserowBaseTool:
        """Create a view tool for the given table ID."""

        @sync_to_async
        def get_tool():
            class CreateViewTool(BaserowBaseTool):
                name: str = "create_view"
                description: str = "Create a new view in the current table. Always use the collaborative ownership type unless specified otherwise."
                args_schema: type = CreateViewArgs

                def _run_impl(
                    self,
                    view_name: str,
                    view_type: Literal[
                        "grid", "calendar", "kanban", "gallery"
                    ] = "grid",
                    ownership_type: Literal[
                        "collaborative", "personal"
                    ] = "collaborative",
                ) -> Tuple[str, Any]:
                    view = CreateViewActionType.do(
                        user,
                        table,
                        view_type,
                        name=view_name,
                        ownership_type=ownership_type,
                    )
                    view_url = (
                        f"/database/{table.database_id}/table/{table.id}/{view.id}/"
                    )
                    content = (
                        f"Created view '{view.name}' (ID: {view.id}, URL: '{view_url}')"
                    )
                    return content, {
                        "view": view,
                        "navigate": {
                            "type": "view",
                            "view_id": view.id,
                            "view_name": view.name,
                            "table_id": table.id,
                            "table_name": table.name,
                            "database_id": table.database_id,
                            "database_name": table.database.name,
                        },
                        "latest_action_is_undoable": True,
                    }

            return CreateViewTool()

        return await get_tool()

    @classmethod
    async def update_view_tool(cls, user: AbstractUser, view: View) -> BaserowBaseTool:
        """Create a view tool for the given table ID."""

        @sync_to_async
        def get_tool():
            class UpdateViewTool(BaserowBaseTool):
                name: str = "update_view"
                description: str = (
                    "Update an existing view in the current table. It can update the name, the ownership type, "
                    "make it public with or without password or turn it back to be private."
                )
                args_schema: type = UpdateViewArgs

                def _run_impl(self, **kwargs) -> Tuple[str, Any]:
                    data = {k: v for k, v in kwargs.items() if v is not None}
                    updated_view = UpdateViewActionType.do(user, view, **data)
                    content = (
                        f"Updated view '{updated_view.name}' (ID: {updated_view.id})"
                    )
                    return content, {
                        "view": updated_view,
                        "latest_action_is_undoable": True,
                    }

            return UpdateViewTool()

        return await get_tool()

    # @classmethod
    # async def delete_view_tool(cls, user: AbstractUser, view: View) -> BaserowBaseTool:
    #     """Create a view tool for the given table ID."""

    #     @sync_to_async
    #     def get_tool():
    #         class DeleteViewTool(BaserowBaseTool):
    #             name: str = "delete_view"
    #             description: str = "Delete an existing view in the current table."
    #             args_schema: type = DeleteViewArgs

    #             def _run_impl(self, **kwargs) -> Tuple[str, Any]:
    #                 data = {k: v for k, v in kwargs.items() if v is not None}
    #                 deleted_view = DeleteViewActionType.do(user, view, **data)
    #                 content = (
    #                     f"Deleted view '{deleted_view.name}' (ID: {deleted_view.id})"
    #                 )
    #                 return content, {
    #                     "view": deleted_view,
    #                     "latest_action_is_undoable": True,
    #                 }

    #         return DeleteViewTool()

    #     return await get_tool()

    @classmethod
    async def set_filters_tool(cls, user: AbstractUser, view: View) -> BaserowBaseTool:
        """Create a filter tool for the given view ID."""

        class SetViewFilterToolArgs(BaseModel):
            view_id: int = Field(
                description="The ID of the view to set filters on.", default=view.id
            )
            request: str = Field(
                description="The user request to set filters on a view."
            )

        @sync_to_async
        def get_tool():
            table_model = view.table.get_model()
            fields_map, existing_types, fields_by_id = {}, set(), {}
            for field_obj in table_model.get_field_objects():
                field = field_obj["field"]
                field_type = field_obj["type"]
                if field_type.type not in AVAILABLE_FILTERS:
                    continue  # TODO Add missing filters
                field_dict = {
                    "id": field.id,
                    "name": field.name,
                    "type": field_type.type,
                }
                if field.description:
                    field_dict["description"] = field.description
                fields_map[field.id] = field_dict
                fields_by_id[field.id] = field
                existing_types.add(field_type.type)

            available_filters = {
                k: v for k, v in AVAILABLE_FILTERS.items() if k in existing_types
            }

            def get_view_filters(view) -> list[FilterGroupDefinition]:
                """Get the available filters for the view."""
                filters_by_group = defaultdict(list)
                for f in view.viewfilter_set.all():
                    if f.field_id not in fields_map:
                        continue  # TODO: complete it. Let's exclude unsupported filters for now
                    field_type = fields_map[f.field_id]["type"]
                    if f.type not in [
                        af["filter_name"] for af in available_filters[field_type]
                    ]:
                        continue
                    filter_def = FilterDefinition(
                        field_id=f.field_id,
                        filter_name=f.type,
                        value=f.value,
                    )
                    filters_by_group[f.group_id].append(filter_def)

                root_group = FilterGroupDefinition(
                    operator=view.filter_type, filters=filters_by_group[None]
                )
                groups_by_id = {None: root_group}
                for filter_group in view.filter_groups.order_by(
                    F("parent_group_id").asc(nulls_first=True)
                ):
                    parent = groups_by_id.get(filter_group.parent_group_id)
                    group = FilterGroupDefinition(
                        operator=filter_group.filter_type,
                        filters=filters_by_group.get(filter_group.id, []),
                    )
                    groups_by_id[filter_group.id] = group
                    parent.children.append(group)

                return root_group

            def get_llm_model(view):
                current_filters = get_view_filters(view)
                timezone = user.profile.timezone or "UTC"
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            FILTER_TOOL_PROMPT.format(
                                table_schema=yaml.dump(fields_map),
                                available_filters=yaml.dump(available_filters),
                                current_filters=yaml.dump(current_filters),
                                user_id=user.id,
                                user_email=user.email,
                                user_name=user.first_name,
                                current_date=datetime.now(
                                    tz=ZoneInfo(timezone)
                                ).isoformat(),
                                timezone=timezone,
                            ),
                        ),
                        ("user", "{request}"),
                    ]
                )
                return prompt | init_chat_model(
                    model="gpt-4.1", temperature=0.3
                ).with_structured_output(FilterGroupDefinition)

            def set_view_filters(view, result):
                handler = ViewHandler()

                for filter_group in view.filter_groups.all():
                    handler.delete_filter_group(user, filter_group=filter_group)

                for view_filter in view.viewfilter_set.all():
                    handler.delete_filter(user, view_filter)

                def _create_filter_group(
                    fg: FilterGroupDefinition, parent_group_id: int | None = None
                ):
                    for flt in fg.filters:
                        flt = to_baserow_filter(flt)
                        field = fields_by_id[flt.field_id]
                        handler.create_filter(
                            user,
                            view,
                            field,
                            flt.filter_name,
                            flt.value,
                            parent_group_id,
                        )
                    for grp in fg.children:
                        new_group = handler.create_filter_group(
                            user, view, grp.operator, parent_group_id
                        )
                        _create_filter_group(grp, new_group.id)

                _create_filter_group(result, None)

            class SetViewFiltersTool(BaserowBaseTool):
                name: str = "set_view_filters"
                description: str = "Set view filter in a view."
                args_schema: type = SetViewFilterToolArgs

                def _run_impl(self, view_id, request):
                    current_view = View.objects.get(id=view_id).specific
                    llm_model = get_llm_model(current_view)
                    res = llm_model.invoke({"request": request})
                    set_view_filters(current_view, res)
                    return "View filters updated.", {"result": res}

            return SetViewFiltersTool()

        return await get_tool()

    @classmethod
    async def set_sorts_tool(cls, user: AbstractUser, view: View) -> BaserowBaseTool:
        """Create a sort tool for the given view ID."""

        class SetViewSortsToolArgs(BaseModel):
            view_id: int = Field(
                description="The ID of the view to set sorts on.", default=view.id
            )
            request: str = Field(description="The user request to set sorts on a view.")

        @sync_to_async
        def get_tool():
            table_model = view.table.get_model()
            fields_map, existing_types, field_by_id = {}, set(), {}
            available_sorts = []
            for field_obj in table_model.get_field_objects():
                field = field_obj["field"]
                field_type = field_obj["type"]
                if field_type.type not in AVAILABLE_FILTERS:
                    continue  # TODO Add missing filters
                field_dict = {
                    "id": field.id,
                    "name": field.name,
                    "type": field_type.type,
                }
                if field.description:
                    field_dict["description"] = field.description
                fields_map[field.id] = field_dict
                field_by_id[field.id] = field
                existing_types.add(field_type.type)
                if field_type.check_can_order_by(field, DEFAULT_SORT_TYPE_KEY):
                    available_sorts.append(field.id)

            def get_llm_model(view):
                current_sorts = []

                for sort in view.viewsort_set.all():
                    current_sorts.append(
                        {"field_id": sort.field_id, "order": sort.order}
                    )
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            SORT_TOOL_PROMPT.format(
                                table_schema=yaml.dump(fields_map),
                                available_sorts=yaml.dump(available_sorts),
                                current_sorts=yaml.dump(current_sorts),
                            ),
                        ),
                        ("user", "{request}"),
                    ]
                )
                return prompt | init_chat_model(
                    model="gpt-4.1", temperature=0.3
                ).with_structured_output(SortsDefinition)

            def set_view_sorts(view, sorts):
                handler = ViewHandler()
                for view_sort in view.viewsort_set.all():
                    handler.delete_sort(user, view_sort)

                for sort in sorts:
                    field = field_by_id[sort.field_id]
                    handler.create_sort(user, view, field, sort.order)

            class SetViewSortsTool(BaserowBaseTool):
                name: str = "set_view_sorts"
                description: str = "Set view sort in the current view."
                args_schema: type = SetViewSortsToolArgs

                def _run_impl(self, view_id, request):
                    view = View.objects.get(id=view_id).specific
                    llm_model = get_llm_model(view)
                    res = llm_model.invoke({"request": request})
                    set_view_sorts(view, res.sorts)
                    return "View sorts updated.", {"result": res}

            return SetViewSortsTool()

        return await get_tool()

    @classmethod
    async def set_group_bys_tool(
        cls, user: AbstractUser, view: View
    ) -> BaserowBaseTool:
        """Create a group by tool for the given view ID."""

        class SetViewGroupBysToolArgs(BaseModel):
            view_id: int = Field(
                description="The ID of the view to set group bys on.", default=view.id
            )
            request: str = Field(
                description="The user request to set group bys on a view."
            )

        @sync_to_async
        def get_tool():
            table_model = view.table.get_model()
            fields_map, existing_types, field_by_id = {}, set(), {}
            available_group_bys = []
            for field_obj in table_model.get_field_objects():
                field = field_obj["field"]
                field_type = field_obj["type"]
                if field_type.type not in AVAILABLE_FILTERS:
                    continue  # TODO Add missing filters
                field_dict = {
                    "id": field.id,
                    "name": field.name,
                    "type": field_type.type,
                }
                if field.description:
                    field_dict["description"] = field.description
                fields_map[field.id] = field_dict
                field_by_id[field.id] = field
                existing_types.add(field_type.type)
                if field_type.check_can_group_by(field, DEFAULT_SORT_TYPE_KEY):
                    available_group_bys.append(field.id)

            def get_llm_model(view):
                current_group_bys = []

                for group_by in view.viewgroupby_set.all():
                    current_group_bys.append(
                        {"field_id": group_by.field_id, "order": group_by.order}
                    )

                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            GROUP_BY_TOOL_PROMPT.format(
                                table_schema=yaml.dump(fields_map),
                                available_group_bys=yaml.dump(available_group_bys),
                                current_group_bys=yaml.dump(current_group_bys),
                            ),
                        ),
                        ("user", "{request}"),
                    ]
                )
                return prompt | init_chat_model(
                    model="gpt-4.1", temperature=0.3
                ).with_structured_output(SortsDefinition)

            def set_view_group_bys(view, group_bys):
                handler = ViewHandler()
                for view_group_by in view.viewgroupby_set.all():
                    handler.delete_group_by(user, view_group_by)

                for group_by in group_bys:
                    field = field_by_id[group_by.field_id]
                    handler.create_group_by(user, view, field, group_by.order, 200)

            class SetViewGroupBysTool(BaserowBaseTool):
                name: str = "set_view_group_bys"
                description: str = "Set view group by in the current view. If a user requires to group by in a grid view, this is the right tool for the job."
                args_schema: type = SetViewGroupBysToolArgs

                def _run_impl(self, view_id, request):
                    view = View.objects.get(id=view_id).specific
                    llm_model = get_llm_model(view)
                    res = llm_model.invoke({"request": request})
                    set_view_group_bys(view, res.sorts)
                    return "View group by updated.", {"result": res}

            return SetViewGroupBysTool()

        return await get_tool()

    @classmethod
    async def set_colors_tool(cls, user: AbstractUser, view: View) -> BaserowBaseTool:
        """Create a set colors tool for the given view ID."""

        class SetViewColorsToolArgs(BaseModel):
            view_id: int = Field(
                description="The ID of the view to set group bys on.", default=view.id
            )
            request: str = Field(
                description="The user request to set group bys on a view."
            )

        def set_view_colors(view, colors):
            handler = ViewHandler()
            for view_color in view.viewdecoration_set.all():
                handler.delete_decoration(view_color, user)

            if colors:
                baserow_decoration_conf = to_baserow_colors(colors)
                handler.create_decoration(
                    view,
                    "background_color",
                    "conditional_color",
                    baserow_decoration_conf,
                    user=user,
                )

        @sync_to_async
        def get_tool():
            table_model = view.table.get_model()
            fields_map, existing_types, fields_by_id = {}, set(), {}
            for field_obj in table_model.get_field_objects():
                field = field_obj["field"]
                field_type = field_obj["type"]
                if field_type.type not in AVAILABLE_FILTERS:
                    continue  # TODO Add missing filters
                field_dict = {
                    "id": field.id,
                    "name": field.name,
                    "type": field_type.type,
                }
                if field.description:
                    field_dict["description"] = field.description
                fields_map[field.id] = field_dict
                fields_by_id[field.id] = field
                existing_types.add(field_type.type)

            available_filters = {
                k: v for k, v in AVAILABLE_FILTERS.items() if k in existing_types
            }

            def get_llm_model(view):
                first_decoration = view.viewdecoration_set.first()
                if first_decoration:
                    current_colors = first_decoration.value_provider_conf
                else:
                    current_colors = {"colors": []}

                tzone = user.profile.timezone or "UTC"
                prompt = ChatPromptTemplate.from_messages(
                    [
                        (
                            "system",
                            COLOR_TOOL_PROMPT.format(
                                table_schema=yaml.dump(fields_map),
                                available_filters=yaml.dump(available_filters),
                                current_colors=yaml.dump(current_colors),
                                user_id=user.id,
                                user_email=user.email,
                                user_name=user.first_name,
                                current_date=datetime.now(
                                    tz=ZoneInfo(tzone)
                                ).isoformat(),
                                timezone=tzone,
                            ),
                        ),
                        ("user", "{request}"),
                    ]
                )
                return prompt | init_chat_model(
                    model="gpt-4.1", temperature=0.3
                ).with_structured_output(ColorsDefinition)

            class SetViewColorsTool(BaserowBaseTool):
                name: str = "set_view_colors"
                description: str = "Colors rows in a view based on filter conditions"
                args_schema: type = SetViewColorsToolArgs

                def _run_impl(self, view_id, request):
                    current_view = View.objects.get(id=view_id).specific
                    llm_model = get_llm_model(current_view)
                    res = llm_model.invoke({"request": request})
                    set_view_colors(current_view, res.colors)
                    return "View colors updated.", {"result": res}

            return SetViewColorsTool()

        return await get_tool()


def to_baserow_filter(filter_def: FilterDefinition) -> FilterDefinition:
    """
    Convert the filter value to the Baserow filter value.
    """

    f = filter_def
    if f.filter_name in ["date_is_before", "date_is_after"]:
        f.value = f"UTC?{f.value}?exact_date"
    return f


class ColorDefinition(BaseModel):
    color: Literal[
        "light-blue",
        "blue",
        "dark-blue",
        "indigo",
        "purple",
        "pink",
        "red",
        "orange",
        "yellow",
        "green",
        "teal",
        "brown",
        "grey",
        "black",
    ]
    operator: Literal["AND", "OR"] = "AND"
    filters: List[FilterDefinition]


class ColorsDefinition(BaseModel):
    colors: List[ColorDefinition]


def to_baserow_colors(colors: List[ColorDefinition]) -> dict[str, Any]:
    """
    Convert the color value to the Baserow color value.
    """

    baserow_colors = []

    for c in colors:
        # br_group = {"operator": c.operator, "id": str(uuid4())}
        br_filters = []
        for flt in c.filters:
            br_flt = to_baserow_filter(flt)
            br_filters.append(
                {
                    "id": str(uuid4()),
                    "type": br_flt.filter_name,
                    "value": br_flt.value,
                    "field": br_flt.field_id,
                    # "group": br_group["id"],
                }
            )
        baserow_colors.append(
            {
                "id": str(uuid4()),
                "color": c.color,
                "filters": br_filters,
                # "groups": [br_group],
                "operator": c.operator,
            }
        )
    return {"colors": baserow_colors}
