from typing import Any

from baserow.contrib.agent.database_previews import (
    database_reference,
    row_names,
    table_names,
    table_reference,
)
from baserow.contrib.agent.previews import StepPreview
from baserow.contrib.agent.tool_types import DatabaseAgentToolType
from baserow.core.tools import ToolContext
from baserow_enterprise.license.row_comment_tools import RowCommentToolLicense
from baserow_premium.row_comments import tools


def _row_reference(row_id: int, names: dict[int, str]) -> dict[str, Any]:
    """
    :param row_id: A row the call names.
    :param names: The row names the identity can see, by row ID.
    :return: The row's name, or its ID as written.
    """

    return {"row": names[row_id]} if row_id in names else {"row_id": row_id}


class RowCommentAgentToolType(RowCommentToolLicense, DatabaseAgentToolType):
    """Row comment tools available to Agents in Advanced workspaces."""


class ListRowCommentsAgentToolType(RowCommentAgentToolType):
    type = "list_row_comments"
    function = tools.list_row_comments

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        table, reference = table_reference(ctx, arguments["table_id"])
        row_id = arguments["row_id"]
        names = row_names(ctx, table, [row_id]) if table else {}
        return StepPreview({**reference, **_row_reference(row_id, names)})

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["comments"])}


class SearchRowCommentsAgentToolType(RowCommentAgentToolType):
    type = "search_row_comments"
    function = tools.search_row_comments

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        values = database_reference(ctx, arguments["database_id"])
        table_ids = arguments.get("table_ids")
        if table_ids:
            names = table_names(ctx, table_ids)
            values["tables"] = [names.get(table_id, table_id) for table_id in table_ids]
        for users in ("mentioned_users", "authors"):
            if arguments.get(users):
                values[users] = [
                    ctx.user.first_name
                    if tools.parse_user_reference(user) == tools.ACTING_USER
                    else user
                    for user in arguments[users]
                ]
        for moment in ("created_after", "created_before"):
            if arguments.get(moment):
                # A validated moment is no longer the text the model sent.
                values[moment] = str(arguments[moment])
        return StepPreview(values)

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["comments"])}


class CreateRowCommentsAgentToolType(RowCommentAgentToolType):
    type = "create_row_comments"
    function = tools.create_row_comments
    changes_data = True
    step_count_argument = "comments"

    def get_step_preview(
        self, ctx: ToolContext, arguments: dict[str, Any]
    ) -> StepPreview:
        table, reference = table_reference(ctx, arguments["table_id"])
        preview = StepPreview(reference, "comments")
        comments = preview.cut_items(arguments["comments"])
        names = (
            row_names(ctx, table, [comment["row_id"] for comment in comments])
            if table
            else {}
        )
        preview.items = [
            {**_row_reference(comment["row_id"], names), "text": comment["text"]}
            for comment in comments
        ]
        return preview

    def get_step_facts(
        self, ctx: ToolContext, arguments: dict[str, Any], result: Any
    ) -> dict[str, Any]:
        return {"count": len(result["created_comments"])}
