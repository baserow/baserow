"""Explicit dispatch for targeted Kuma requests, without an action registry."""

from baserow.contrib.integrations.local_baserow.service_filters.handler import (
    get_target_type,
)
from baserow_enterprise.assistant.service_filters import run_service_filter_request


def get_action_workspace(action, parameters):
    """Resolve the action's scope before checking assistant permissions."""
    if action == "update_service_filters":
        target_type = get_target_type(parameters["kind"])
        return target_type.get_workspace(target_type.get_owner(parameters["id"]))
    raise ValueError(f"Unsupported assistant action: {action}")


def run_assistant_action(action, ctx, prompt, parameters, model_profile):
    """Execute a validated targeted action and return its common outcome."""
    if action == "update_service_filters":
        result = run_service_filter_request(
            ctx,
            parameters["kind"],
            parameters["id"],
            prompt,
            model_profile=model_profile,
            table_id=parameters.get("table_id"),
        )
        return {"changed": result.changed, "summary": result.summary, "result": {}}
    raise ValueError(f"Unsupported assistant action: {action}")
