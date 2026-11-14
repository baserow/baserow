from typing import Annotated, Any, Literal

from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils.translation import gettext as _

from pydantic import Field
from pydantic_ai import ModelRetry, RunContext

from baserow.contrib.integrations.local_baserow.service_filters import (
    tools as shared_service_filters,
)
from baserow.contrib.integrations.local_baserow.service_filters.exceptions import (
    ServiceFilterTargetDoesNotExist,
    ServiceFilterTargetNotSupported,
)
from baserow.contrib.integrations.local_baserow.service_filters.handler import (
    describe_filter_state,
)
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow_enterprise.assistant.deps import AssistantDeps
from baserow_enterprise.assistant.exceptions import ServiceFilterGenerationFailed
from baserow_enterprise.assistant.service_filters import run_service_filter_request
from baserow_enterprise.assistant.tools.toolset import AssistantFunctionToolset

TargetKind = Literal["builder_data_source", "dashboard_data_source", "automation_node"]

TARGET_KIND_DESCRIPTION = (
    "What owns the filters: 'builder_data_source' for an application page data "
    "source, 'dashboard_data_source' for a dashboard chart's data source, "
    "'automation_node' for an automation node. list_filterable_data_sources gives "
    "the kind and id of each."
)

_TARGET_NOT_FOUND = (
    "{kind} {id} doesn't exist in this workspace. Look its kind and id up with "
    "list_filterable_data_sources first."
)


def list_filterable_data_sources(
    ctx: RunContext[AssistantDeps],
    application_id: Annotated[
        int | None,
        Field(
            description="Only list the ones of this application, builder, dashboard "
            "or automation. null lists those of every application."
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List the data sources and automation nodes whose filters can be changed.

    WHEN to use: Find the kind and id of a data source, dashboard chart or automation node before reading or changing its filters.
    WHAT it does: Lists the data sources of applications and dashboards, and the automation nodes reading rows from a table.
    RETURNS: Items with kind, id, name, application, location (page, dashboard or workflow), service_type, table_id and filter_count.
    """

    ctx.deps.tool_helpers.update_status(_("Listing data sources..."))
    try:
        return shared_service_filters.list_filterable_data_sources(
            ctx.deps.tool_context(), application_id, size=100
        )
    except ApplicationDoesNotExist:
        raise ModelRetry(
            f"Application {application_id} doesn't exist in this workspace. Use "
            "list_builders to find its id."
        )


def list_service_filters(
    ctx: RunContext[AssistantDeps],
    kind: Annotated[TargetKind, Field(description=TARGET_KIND_DESCRIPTION)],
    id: Annotated[int, Field(description="The id of the data source or node.")],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    List the filters of a data source or automation node reading rows from a table.

    WHEN to use: The user asks which filters a data source, dashboard chart or automation node has.
    WHAT it does: Returns its top level filter type (AND/OR), filter groups and filters, with its table's fields.
    RETURNS: filter_type, groups and filters with field_id, field_name, type and value.
    DO NOT USE when: You want to change the filters — update_service_filters reads them itself.
    """

    try:
        return shared_service_filters.list_service_filters(
            ctx.deps.tool_context(), kind, id
        )
    except ServiceFilterTargetDoesNotExist:
        raise ModelRetry(_TARGET_NOT_FOUND.format(kind=kind, id=id))
    except DjangoValidationError as exc:
        return {"error": " ".join(exc.messages)}


def update_service_filters(
    ctx: RunContext[AssistantDeps],
    kind: Annotated[TargetKind, Field(description=TARGET_KIND_DESCRIPTION)],
    id: Annotated[
        int,
        Field(
            description=(
                "The id of the data source or node. The one the user names, else "
                "`element.data_source_id` from `<ui_context>`. If neither identifies "
                "it and the page has more than one data source, don't call this "
                "tool: call ask_user naming the data sources."
            )
        ),
    ],
    instructions: Annotated[
        str,
        Field(
            description=(
                "The user's filter request, verbatim, including words saying how "
                "it relates to the existing filters such as 'update', 'change', "
                "'also', 'instead' or 'remove'. Don't shorten or rephrase it, don't "
                "resolve field or option ids, and don't write the filters yourself."
            )
        ),
    ],
    thought: Annotated[
        str, Field(description="Brief reasoning for calling this tool.")
    ],
) -> dict[str, Any]:
    """\
    Add, update or delete the filters of a data source or automation node reading rows from a table.

    WHEN to use: The user wants to filter the rows of an application data source, a dashboard chart or an automation node (list rows, get row, aggregate rows), e.g. "only show the tasks of the `ID` page parameter" or "remove the status filter".
    WHAT it does: Works out and saves the filter changes for the request, including dynamic values such as page parameters, the logged in user or previous node outputs.
    RETURNS: Whether the filters changed, a summary to relay to the user, and the resulting filters.
    DO NOT USE when: The user wants to filter a database view — use create_view_filters. Don't create a database view to filter a data source either.
    HOW: Find the data source or node id first, then pass the user's request verbatim in `instructions`. One call handles the whole request.
    WHICH DATA SOURCE: Use the one the user names. When they don't name one, or say "this table" / "the selected element", use the data source of the selected element (`element.data_source_id` in `<ui_context>`, kind 'builder_data_source'). When no element with a data source is selected and several data sources could fit, call ask_user naming them instead of guessing.
    """

    try:
        result = run_service_filter_request(
            ctx.deps.tool_context(),
            kind,
            id,
            instructions,
            model_profile=ctx.deps.tool_helpers.model_profile,
        )
    except ServiceFilterTargetDoesNotExist:
        raise ModelRetry(_TARGET_NOT_FOUND.format(kind=kind, id=id))
    except (ServiceFilterTargetNotSupported, ServiceFilterGenerationFailed) as exc:
        return {"changed": False, "error": str(exc)}

    return {
        "changed": result.changed,
        "summary": result.summary,
        **describe_filter_state(result.state),
    }


TOOL_FUNCTIONS = [
    list_filterable_data_sources,
    list_service_filters,
    update_service_filters,
]
services_toolset = AssistantFunctionToolset(TOOL_FUNCTIONS, max_retries=3)
