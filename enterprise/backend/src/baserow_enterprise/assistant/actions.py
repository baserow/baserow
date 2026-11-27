"""Explicit dispatch for targeted Kuma requests, without an action registry."""

from baserow.contrib.database.models import Database
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.integrations.local_baserow.service_filters.handler import (
    get_target_type,
)
from baserow.core.handler import CoreHandler
from baserow_enterprise.assistant.service_filters import run_service_filter_request

from .editor_generation import run_editor_action


def get_action_workspace(action, parameters):
    """Resolve the action's scope before checking assistant permissions."""
    if action == "update_service_filters":
        target_type = get_target_type(parameters["kind"])
        return target_type.get_workspace(target_type.get_owner(parameters["id"]))
    if action in ("generate_formula", "generate_ai_field_prompt", "create_view"):
        return TableHandler().get_table(parameters["table_id"]).database.workspace
    if action in ("edit_view_filters", "add_row_color"):
        return ViewHandler().get_view(parameters["view_id"]).table.database.workspace
    if action == "create_table":
        return (
            CoreHandler()
            .get_application(parameters["database_id"], Database.objects.all())
            .workspace
        )
    if action in ("generate_agent_instructions", "create_database"):
        return CoreHandler().get_workspace(parameters["workspace_id"])
    raise ValueError(f"Unsupported assistant action: {action}")


def run_assistant_action(
    action, ctx, prompt, parameters, model_profile, *, before_write=None
):
    """Execute a validated targeted action and return its common outcome."""
    if action == "update_service_filters":
        result = run_service_filter_request(
            ctx,
            parameters["kind"],
            parameters["id"],
            prompt,
            model_profile=model_profile,
            table_id=parameters.get("table_id"),
            before_write=before_write,
        )
        return {"changed": result.changed, "summary": result.summary, "result": {}}
    return run_editor_action(
        action, ctx, prompt, parameters, model_profile, before_write=before_write
    )
