from typing import TYPE_CHECKING, Any, Callable, Literal

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.utils.translation import gettext as _

from baserow.core.actions import CreateApplicationActionType
from baserow.core.models import Workspace
from baserow.core.registries import application_type_registry
from baserow.core.service import CoreService
from baserow_enterprise.assistant.tools.registries import AssistantToolType

from .types import AnyBuilderItem, BuilderItem, BuilderItemCreate

if TYPE_CHECKING:
    from baserow_enterprise.assistant.assistant import ToolHelpers


def get_list_builders_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[], list[AnyBuilderItem]]:
    """
    Returns a function that lists all the builders the user has access to in the
    current workspace.
    """

    def list_builders(
        builder_types: list[
            Literal["database", "application", "automation", "dashboard"]
        ]
        | None = None
    ) -> list[AnyBuilderItem] | str:
        """
        Lists all the builders the user can access (databases, applications,
        automations, dashboards) in the current workspace.

        If `builder_types` is provided, only builders of that type are returned,
        otherwise all builders are returned (default).
        """

        nonlocal user, workspace, tool_helpers

        tool_helpers.update_status(
            _("Listing %(builder_types)ss...")
            % {
                "builder_types": builder_types[0]
                if builder_types and len(builder_types) == 1
                else "builder"
            }
        )

        applications_qs = CoreService().list_applications_in_workspace(
            user, workspace, specific=False
        )

        builders = {}
        for builder in applications_qs:
            builder_type = application_type_registry.get_by_model(
                builder.specific_class
            ).type
            if not builder_types or builder_type in builder_types:
                builders.setdefault(builder_type, []).append(
                    BuilderItem(
                        id=builder.id, name=builder.name, type=builder_type
                    ).model_dump()
                )

        return builders if builders else "no builders found"

    return list_builders


class ListBuildersToolType(AssistantToolType):
    type = "list_builders"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_list_builders_tool(user, workspace, tool_helpers)


def get_create_modules_tool(
    user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
) -> Callable[[str], dict[str, Any]]:
    """
    Returns a function that creates a module in the current workspace.
    """

    def create_builders(builders: list[BuilderItemCreate]) -> dict[str, Any]:
        """
        Create a builder in the current workspace and return its ID and name.

        - name: desired name for the builder (better if unique in the workspace)
        """

        nonlocal user, workspace, tool_helpers

        created_builders = []
        with transaction.atomic():
            for builder in builders:
                tool_helpers.update_status(
                    _("Creating %(builder_type)s %(builder_name)s...")
                    % {"builder_type": builder.type, "builder_name": builder.name}
                )
                builder_orm_instance = CreateApplicationActionType.do(
                    user, workspace, builder.get_orm_type(), name=builder.name
                )
                builder.post_creation_hook(user, builder_orm_instance)
                created_builders.append(
                    BuilderItem(
                        id=builder_orm_instance.id,
                        name=builder_orm_instance.name,
                        type=builder.type,
                    ).model_dump()
                )

        return {"created_builders": created_builders}

    return create_builders


class CreateBuildersToolType(AssistantToolType):
    type = "create_builders"

    @classmethod
    def get_tool(
        cls, user: AbstractUser, workspace: Workspace, tool_helpers: "ToolHelpers"
    ) -> Callable[[Any], Any]:
        return get_create_modules_tool(user, workspace, tool_helpers)
