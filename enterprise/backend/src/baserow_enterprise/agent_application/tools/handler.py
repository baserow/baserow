from typing import Any, Optional

from django.contrib.auth.models import AbstractUser

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.integrations.models import Integration
from baserow.core.services.exceptions import ServiceTypeDoesNotExist
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import DispatchTypes, service_type_registry

from ..exceptions import AgentToolDoesNotExist
from ..models import AgentDefinition, AgentTool
from ..signals import agent_tool_created, agent_tool_updated
from ..triggers.handler import check_service_table_in_workspace
from .registries import agent_tool_type_registry

_NOT_PROVIDED = object()


class AgentToolHandler:
    def list_tools(self, agent: AgentDefinition):
        return agent.tools.select_related("service", "identity").all()

    def _get_workspace_identity(self, agent: AgentDefinition, identity_id: int):
        from baserow.core.models import Agent

        identity = Agent.objects.filter(
            id=identity_id, workspace_id=agent.application.workspace_id
        ).first()
        if identity is None:
            raise DRFValidationError(
                detail=f"The agent with ID {identity_id} does not exist in the "
                "application's workspace.",
                code="invalid_agent",
            )
        return identity

    def _validate_tool_identities(self, agent: AgentDefinition, config: dict) -> dict:
        """
        Keeps only `tool_identities` entries that name a workspace agent of the
        application's workspace.
        """

        from baserow.core.models import Agent

        wanted = config.get("tool_identities") or {}
        if not wanted:
            return config
        ids = {
            int(value)
            for value in wanted.values()
            if isinstance(value, int) or (isinstance(value, str) and value.isdigit())
        }
        existing = set(
            Agent.objects.filter(
                workspace_id=agent.application.workspace_id, id__in=ids
            ).values_list("id", flat=True)
        )
        return {
            **config,
            "tool_identities": {
                name: int(value)
                for name, value in wanted.items()
                if str(value).isdigit() and int(value) in existing
            },
        }

    def find_tool_for_tool_name(
        self,
        agent: AgentDefinition,
        tool_name: str,
        tools: Optional[list[AgentTool]] = None,
    ) -> Optional[AgentTool]:
        """
        :param tools: The agent's tools when the caller already fetched them,
            so deciding many approvals doesn't query them per decision.
        """

        for tool in tools if tools is not None else self.list_tools(agent):
            try:
                tool_type = agent_tool_type_registry.get(tool.type)
            except agent_tool_type_registry.does_not_exist_exception_class:
                continue
            if tool_type.owns_tool_name(tool, tool_name):
                return tool
        return None

    def dont_ask_again(
        self,
        agent: AgentDefinition,
        tool_name: str,
        tools: Optional[list[AgentTool]] = None,
    ) -> Optional[AgentTool]:
        """
        Lets the named tool run without approval from now on. Returns the
        updated `AgentTool` or None when no tool contributes that name.
        """

        tool = self.find_tool_for_tool_name(agent, tool_name, tools=tools)
        if tool is None:
            return None
        config = agent_tool_type_registry.get(tool.type).apply_dont_ask_again(
            tool, tool_name
        )
        if config is None:
            return None
        tool.config = config
        tool.save(update_fields=["config", "updated_on"])
        agent_tool_updated.send(self, tool=tool, user=None)
        return tool

    def get_tool(self, tool_id: int) -> AgentTool:
        try:
            return AgentTool.objects.select_related(
                "agent__application__workspace", "service"
            ).get(
                id=tool_id,
                agent__application__trashed=False,
                agent__application__workspace__trashed=False,
            )
        except AgentTool.DoesNotExist:
            raise AgentToolDoesNotExist(f"The tool with id {tool_id} does not exist.")

    def _validate_service_type(self, service_type_str: str):
        try:
            service_type = service_type_registry.get(service_type_str)
        except ServiceTypeDoesNotExist as exc:
            raise DRFValidationError(
                detail=f"The service type {service_type_str} does not exist.",
                code="invalid_service_type",
            ) from exc

        if not service_type.can_be_dispatched_as(DispatchTypes.ACTION):
            raise DRFValidationError(
                detail=f"The service type {service_type_str} cannot be used as "
                "an action tool.",
                code="invalid_service_type",
            )

        return service_type

    def _prepare_service_values(self, agent: AgentDefinition, values: dict) -> dict:
        integration_id = values.pop("integration_id", None)
        if integration_id is None:
            return values

        integration = Integration.objects.filter(
            id=integration_id, application=agent.application
        ).first()
        if integration is None:
            raise DRFValidationError(
                detail=f"The integration {integration_id} does not belong to "
                "the application.",
                code="invalid_integration",
            )

        values["integration"] = integration
        return values

    def create_tool(
        self,
        user: AbstractUser,
        agent: AgentDefinition,
        tool_type_str: str,
        name: str = "",
        config: Optional[dict] = None,
        service_type_str: Optional[str] = None,
        service_values: Optional[dict] = None,
    ) -> AgentTool:
        tool_type = agent_tool_type_registry.get(tool_type_str)
        config = tool_type.prepare_config(config or {})

        service = None
        if service_type_str is not None:
            service_type = self._validate_service_type(service_type_str)
            prepared_values = service_type.prepare_values(
                self._prepare_service_values(agent, dict(service_values or {})),
                user,
            )
            check_service_table_in_workspace(prepared_values, agent.application)
            service = ServiceHandler().create_service(service_type, **prepared_values)

        last_tool = agent.tools.order_by("-order").first()

        tool = AgentTool.objects.create(
            agent=agent,
            type=tool_type_str,
            name=name,
            config=config or {},
            service=service,
            order=(last_tool.order + 1) if last_tool else 1,
        )
        agent_tool_created.send(self, tool=tool, user=user)
        return tool

    def update_tool(
        self,
        user: AbstractUser,
        tool: AgentTool,
        name: Optional[str] = None,
        config: Optional[dict] = None,
        service_values: Optional[dict] = None,
        identity_id: Any = _NOT_PROVIDED,
    ) -> AgentTool:
        """
        :param identity_id: The workspace agent the tool runs as, or None for
            the application's identity. Omitted when unchanged.
        :raises DRFValidationError: When the identity is not in the workspace.
        """

        update_fields = ["updated_on"]

        if name is not None:
            tool.name = name
            update_fields.append("name")
        if config is not None:
            tool_type = agent_tool_type_registry.get(tool.type)
            config = tool_type.prepare_config(
                tool_type.merge_secret_config(tool, config)
            )
            if tool.type == "workspace":
                config = self._validate_tool_identities(tool.agent, config)
            tool.config = config
            update_fields.append("config")
        if identity_id is not _NOT_PROVIDED:
            tool.identity = (
                None
                if identity_id is None
                else self._get_workspace_identity(tool.agent, identity_id)
            )
            update_fields.append("identity")

        tool.save(update_fields=update_fields)

        if service_values is not None and tool.service_id is not None:
            service = tool.service.specific
            service_type = service.get_type()
            prepared_values = service_type.prepare_values(
                self._prepare_service_values(tool.agent, dict(service_values)),
                user,
                instance=service,
            )
            check_service_table_in_workspace(prepared_values, tool.agent.application)
            ServiceHandler().update_service(service_type, service, **prepared_values)

        agent_tool_updated.send(self, tool=tool, user=user)
        return tool

    def trash_tool(self, user: AbstractUser, tool: AgentTool) -> None:
        """Moves the tool to the trash so the deletion can be undone."""

        from baserow.core.trash.handler import TrashHandler

        application = tool.agent.application
        TrashHandler.trash(user, application.workspace, application, tool)

    def delete_tool(self, tool: AgentTool) -> None:
        """Permanently deletes the tool and its service."""

        service = tool.service.specific if tool.service_id else None
        tool.delete()
        if service is not None:
            ServiceHandler().delete_service(service.get_type(), service)
