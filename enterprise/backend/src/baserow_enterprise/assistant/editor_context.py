from baserow.contrib.agent.models import AgentApplication
from baserow.contrib.agent.operations import ReadAgentConfigurationOperationType
from baserow.contrib.database.fields.operations import (
    ListFieldsOperationType,
    ReadFieldOperationType,
)
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools.tables import get_database, get_table
from baserow.contrib.database.tools.views import get_view
from baserow.contrib.database.views.exceptions import ViewDoesNotExist
from baserow.contrib.integrations.local_baserow.service_filters.exceptions import (
    ServiceFilterTargetDoesNotExist,
    ServiceFilterTargetNotSupported,
)
from baserow.contrib.integrations.local_baserow.service_filters.handler import (
    resolve_service_filter_target,
)
from baserow.core.exceptions import ApplicationDoesNotExist, PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.tools.applications import get_application_in_workspace

from .exceptions import EditorGenerationFailed
from .types import UIContext

EDITOR_ACCESS_ERRORS = (
    PermissionException,
    ApplicationDoesNotExist,
    Table.DoesNotExist,
    ViewDoesNotExist,
    ServiceFilterTargetDoesNotExist,
    ServiceFilterTargetNotSupported,
    EditorGenerationFailed,
)


def _named(obj):
    return {"id": obj.pk, "name": obj.name}


def resolve_editor_location(ctx, action, target):
    """Read the saved resource through the acting user's current workspace permissions."""

    location = {"workspace": _named(ctx.workspace)}
    table = database = None
    if action == "update_service_filters":
        service = resolve_service_filter_target(
            ctx,
            target["kind"],
            target["id"],
            for_update=False,
            table_id=target.get("table_id"),
        )
        owner = service.owner
        if service.kind == "builder_data_source":
            location.update(
                application=_named(owner.page.builder), page=_named(owner.page)
            )
        elif service.kind == "automation_node":
            location.update(
                automation=_named(owner.workflow.automation),
                workflow=_named(owner.workflow),
            )
        elif service.kind == "dashboard_data_source":
            location["dashboard"] = _named(owner.dashboard)
        return location, service.name
    if "view_id" in target:
        view = get_view(ctx, target["view_id"])
        location["view"] = {**_named(view), "type": view.get_type().type}
        table = view.table
    elif "table_id" in target:
        table = get_table(ctx, target["table_id"], ListFieldsOperationType.type)
    elif "database_id" in target:
        database = get_database(ctx, target["database_id"])
    elif "agent_id" in target:
        agent = get_application_in_workspace(ctx, target["agent_id"], AgentApplication)
        CoreHandler().check_permissions(
            ctx.user,
            ReadAgentConfigurationOperationType.type,
            workspace=ctx.workspace,
            context=agent,
        )
        location["agent"] = _named(agent)
    if table is not None:
        location["table"] = _named(table)
        database = table.database
    if database is not None:
        location["database"] = _named(database)
    if target.get("field_id"):
        field = table.field_set.filter(pk=target["field_id"]).first()
        if field is None:
            raise EditorGenerationFailed()
        CoreHandler().check_permissions(
            ctx.user,
            ReadFieldOperationType.type,
            workspace=ctx.workspace,
            context=field,
        )
        return location, field.name
    for key in ("view", "table", "database", "agent", "workspace"):
        if key in location:
            return location, location[key]["name"]


def resume_editor_chat(ctx, chat, ui_context):
    """Use the original target even when history is opened from another screen."""

    saved = chat.editor_context
    target = dict(saved["target"])
    location = saved["location"]
    if saved["action"] in ("create_database", "create_table", "create_view"):
        if view := location.get("view"):
            target = {"view_id": view["id"]}
        elif table := location.get("table"):
            target = {"table_id": table["id"]}
        elif database := location.get("database"):
            target = {"database_id": database["id"]}
    live, _ = resolve_editor_location(ctx, saved["action"], target)
    return UIContext(
        user=ui_context.user,
        timezone=ui_context.timezone,
        editor={
            "action": saved["action"],
            "target": target,
            "label": saved["label"],
        },
        **live,
    )
