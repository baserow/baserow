from typing import Optional

from django.contrib.auth.models import AbstractUser

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.integrations.models import Integration
from baserow.core.services.exceptions import ServiceTypeDoesNotExist
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import DispatchTypes, service_type_registry

from ..exceptions import AgentToolDoesNotExist
from ..models import AgentDefinition, AgentTool
from .registries import agent_tool_type_registry


class AgentToolHandler:
    def list_tools(self, agent: AgentDefinition):
        return agent.tools.select_related("service").all()

    def get_tool(self, tool_id: int) -> AgentTool:
        try:
            return AgentTool.objects.select_related(
                "agent__application__workspace", "service"
            ).get(id=tool_id)
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
        # Validates the tool type exists.
        agent_tool_type_registry.get(tool_type_str)

        service = None
        if service_type_str is not None:
            service_type = self._validate_service_type(service_type_str)
            prepared_values = service_type.prepare_values(
                self._prepare_service_values(agent, dict(service_values or {})),
                user,
            )
            service = ServiceHandler().create_service(service_type, **prepared_values)

        last_tool = agent.tools.order_by("-order").first()

        return AgentTool.objects.create(
            agent=agent,
            type=tool_type_str,
            name=name,
            config=config or {},
            service=service,
            order=(last_tool.order + 1) if last_tool else 1,
        )

    def update_tool(
        self,
        user: AbstractUser,
        tool: AgentTool,
        name: Optional[str] = None,
        config: Optional[dict] = None,
        service_values: Optional[dict] = None,
    ) -> AgentTool:
        update_fields = ["updated_on"]

        if name is not None:
            tool.name = name
            update_fields.append("name")
        if config is not None:
            tool.config = config
            update_fields.append("config")

        tool.save(update_fields=update_fields)

        if service_values is not None and tool.service_id is not None:
            service = tool.service.specific
            service_type = service.get_type()
            prepared_values = service_type.prepare_values(
                self._prepare_service_values(tool.agent, dict(service_values)),
                user,
                instance=service,
            )
            ServiceHandler().update_service(service_type, service, **prepared_values)

        return tool

    def delete_tool(self, tool: AgentTool) -> None:
        service = tool.service.specific if tool.service_id else None
        tool.delete()
        if service is not None:
            ServiceHandler().delete_service(service.get_type(), service)
