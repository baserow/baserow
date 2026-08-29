import re
from typing import TYPE_CHECKING

from asgiref.sync import sync_to_async
from pydantic_ai import RunContext, Tool
from pydantic_ai.toolsets import FunctionToolset

from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.handler import ServiceHandler

from ..agent_dispatch_context import AgentDispatchContext
from .registries import AgentToolType

if TYPE_CHECKING:
    from ..deps import AgentRunDeps
    from ..models import AgentTool

_INPUT_TYPE_TO_JSON_SCHEMA = {
    "string": {"type": "string"},
    "number": {"type": "number"},
    "boolean": {"type": "boolean"},
}


def get_service_tool_name(tool: "AgentTool") -> str:
    slug = re.sub(r"[^a-z0-9_]+", "_", (tool.name or "").lower()).strip("_")
    return slug or f"service_tool_{tool.id}"


def build_service_tool_schema(tool: "AgentTool") -> dict:
    """
    Builds the JSON schema for the tool's arguments from the user-declared
    runtime inputs. The user configures the service itself; the model only
    supplies these inputs, referenced in service formulas as
    `get('tool_input.<name>')`.
    """

    properties = {}
    required = []

    for input_definition in tool.config.get("inputs", []):
        name = input_definition.get("name")
        if not name:
            continue
        schema = dict(
            _INPUT_TYPE_TO_JSON_SCHEMA.get(
                input_definition.get("type", "string"),
                _INPUT_TYPE_TO_JSON_SCHEMA["string"],
            )
        )
        if input_definition.get("description"):
            schema["description"] = input_definition["description"]
        properties[name] = schema
        if input_definition.get("required", True):
            required.append(name)

    return {
        "type": "object",
        "properties": properties,
        "required": required,
        "additionalProperties": False,
    }


def build_service_tool(tool: "AgentTool", deps: "AgentRunDeps") -> Tool:
    service = tool.service.specific
    service_type = service.get_type()
    description = (
        tool.config.get("description")
        or f"Executes the configured {service_type.type} action."
    )

    async def run_service_tool(ctx: RunContext["AgentRunDeps"], **kwargs):
        ctx.deps.tool_helpers.raise_if_cancelled()
        dispatch_context = AgentDispatchContext(
            chat=ctx.deps.chat, runtime_inputs=kwargs
        )

        def dispatch():
            return ServiceHandler().dispatch_service(service, dispatch_context)

        try:
            result = await sync_to_async(dispatch)()
        except ServiceImproperlyConfiguredDispatchException as exc:
            return {"error": f"The tool's service is misconfigured: {exc}"}
        except Exception as exc:
            return {"error": f"The tool failed: {exc}"}

        return result.data

    return Tool.from_schema(
        run_service_tool,
        name=get_service_tool_name(tool),
        description=description,
        json_schema=build_service_tool_schema(tool),
        takes_ctx=True,
    )


class ServiceAgentToolType(AgentToolType):
    """
    Exposes a user-configured action service (send Slack message, send email,
    HTTP request, create rows, start workflow, ...) as a callable tool.
    """

    type = "service"
    is_configurable = True

    def build_toolsets(self, tool: "AgentTool", deps: "AgentRunDeps") -> list:
        from .gating import wrap_approval_required

        if tool.service_id is None:
            return []

        toolset = FunctionToolset([build_service_tool(tool, deps)], max_retries=3)
        # Action services always change something (rows, emails, requests),
        # so they sit behind the approval queue unless explicitly disabled.
        if tool.config.get("require_approval", True):
            return [wrap_approval_required(toolset)]
        return [toolset]
