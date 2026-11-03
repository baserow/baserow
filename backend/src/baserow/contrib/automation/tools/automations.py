"""
Automation application tools shared by the clients that act for a user.
"""

from typing import Annotated, Any

from django.db import transaction
from django.utils.translation import gettext as _

from pydantic import Field

from baserow.contrib.automation.tools.workflows import get_automation_in_workspace
from baserow.core.integrations.registries import integration_type_registry
from baserow.core.integrations.service import IntegrationService
from baserow.core.tools import ToolContext
from baserow.core.tools.applications import (
    ApplicationName,
    create_application,
    rename_application,
)


def create_automation(
    ctx: ToolContext,
    name: Annotated[
        ApplicationName,
        Field(description="The name of the automation, at most 160 characters."),
    ],
) -> dict[str, Any]:
    """
    Create one empty automation in the workspace, connected to its data. Add workflows to it with
    create_workflows. Returns its id and name.
    """

    ctx.update_status(_("Creating automation %(name)s...") % {"name": name})
    with transaction.atomic():
        automation = create_application(ctx, "automation", name)
        # Row actions read and write tables through it, so workflows can't run
        # without one.
        IntegrationService().create_integration(
            ctx.user,
            integration_type_registry.get("local_baserow"),
            automation,
            name="Local Baserow",
        )
    return {"created_automation": {"id": automation.id, "name": automation.name}}


def update_automation(
    ctx: ToolContext,
    automation_id: Annotated[
        int, Field(description="The ID of the automation, from list_workflows.")
    ],
    name: Annotated[
        ApplicationName,
        Field(description="The new name, at most 160 characters."),
    ],
) -> dict[str, Any]:
    """
    Rename an automation. Returns its id and name, and changed, which is false
    when it already had that name.
    """

    automation = get_automation_in_workspace(ctx, automation_id)
    return rename_application(ctx, automation, name, "updated_automation")
