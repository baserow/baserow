from dataclasses import dataclass

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.models import AgentAction, AgentApplication
from baserow.core.services.handler import ServiceHandler
from baserow.core.trash.handler import TrashHandler

from .exceptions import AgentActionDoesNotExist, AgentActionTypeNotAvailable
from .inputs import validate_inputs, validate_name
from .registries import agent_action_type_registry


@dataclass
class AgentActionUpdated:
    action: AgentAction
    changed_fields: list[str]


class AgentActionHandler:
    """Persistence of configured action tools, independent of their pending calls."""

    editable_fields = ("name", "description", "inputs", "enabled", "ask_first")

    def get_action(
        self, action_id: int, base_queryset: QuerySet[AgentAction] | None = None
    ) -> AgentAction:
        queryset = (
            base_queryset if base_queryset is not None else AgentAction.objects.all()
        )
        try:
            return queryset.select_related("agent__workspace", "service").get(
                id=action_id
            )
        except AgentAction.DoesNotExist as exc:
            raise AgentActionDoesNotExist from exc

    def list_actions(self, agent: AgentApplication) -> QuerySet[AgentAction]:
        return AgentAction.objects.filter(agent=agent).select_related(
            "agent__workspace", "service"
        )

    def available_action_types(self, agent: AgentApplication) -> list[str]:
        return [
            adapter.type
            for adapter in agent_action_type_registry.get_all()
            if adapter.is_available(agent.workspace)
        ]

    def check_type_available(self, agent: AgentApplication, type_name: str) -> None:
        if type_name not in self.available_action_types(agent):
            raise AgentActionTypeNotAvailable(type_name)

    def get_configuration_errors(self, action: AgentAction) -> dict[str, str]:
        return agent_action_type_registry.get(
            action.service.get_type().type
        ).get_configuration_errors(action)

    @staticmethod
    def reserved_names() -> set[str]:
        from pydantic_ai import WebSearchTool

        from baserow.contrib.agent.registries import agent_tool_type_registry

        return {*agent_tool_type_registry.get_types(), WebSearchTool.kind}

    def unique_name(
        self, agent: AgentApplication, name: str, excluding_id: int | None = None
    ) -> str:
        names = self.reserved_names() | set(
            AgentAction.objects.filter(agent=agent)
            .exclude(pk=excluding_id)
            .values_list("name", flat=True)
        )
        candidate, number = name, 2
        while candidate in names:
            suffix = f"_{number}"
            candidate = f"{name[: 64 - len(suffix)]}{suffix}"
            number += 1
        return candidate

    def check_name_available(
        self, agent: AgentApplication, name: str, excluding_id=None
    ):
        if name in self.reserved_names():
            raise ValidationError(
                {"name": "This name is reserved for a built-in tool."}
            )
        if self.unique_name(agent, name, excluding_id) != name:
            raise ValidationError({"name": "An action with this name already exists."})

    def create_action(
        self,
        agent: AgentApplication,
        service_type,
        prepared_service_values: dict,
        **values,
    ) -> AgentAction:
        self.check_name_available(agent, values["name"])
        service = ServiceHandler().create_service(
            service_type, **prepared_service_values
        )
        return AgentAction.objects.create(agent=agent, service=service, **values)

    def update_action(
        self, action: AgentAction, prepared_service_values: dict | None = None, **values
    ) -> AgentActionUpdated:
        if "name" in values:
            self.check_name_available(action.agent, values["name"], action.id)
        changed = []
        for name in self.editable_fields:
            if name in values and values[name] != getattr(action, name):
                setattr(action, name, values[name])
                changed.append(name)
        if changed:
            action.save(update_fields=[*changed, "updated_on"])
        if prepared_service_values is not None:
            service = action.service.specific
            updated = ServiceHandler().update_service(
                service.get_type(), service, **prepared_service_values
            )
            action.service = updated.service
            if updated.original_service_values != updated.new_service_values:
                changed.append("service")
        return AgentActionUpdated(action, changed)

    def delete_action(self, user: AbstractUser, action: AgentAction) -> None:
        TrashHandler.trash(user, action.agent.workspace, action.agent, action)

    def export_actions(self, agent, import_export_config, files_zip=None, storage=None):
        return [
            {
                "id": action.id,
                **{field: getattr(action, field) for field in self.editable_fields},
                "service": ServiceHandler().export_service(
                    action.service.specific,
                    import_export_config=import_export_config,
                    files_zip=files_zip,
                    storage=storage,
                ),
            }
            for action in self.list_actions(agent)
        ]

    def import_actions(
        self,
        agent,
        serialized_actions,
        id_mapping,
        import_export_config,
        files_zip=None,
        storage=None,
    ):
        from baserow.core.integrations.handler import IntegrationHandler

        action_ids = id_mapping.setdefault("agent_actions", {})
        copied = []
        for serialized in serialized_actions:
            service_values = serialized["service"]
            if service_values["type"] not in agent_action_type_registry.get_types():
                continue
            values = {
                field: serialized[field]
                for field in self.editable_fields
                if field in serialized
            }
            values["name"] = self.unique_name(
                agent, validate_name(values.get("name", service_values["type"]))
            )
            values["inputs"] = validate_inputs(values.get("inputs", []))
            values["enabled"] = bool(
                import_export_config.is_duplicate
                and not import_export_config.is_template
                and values.get("enabled", False)
            )
            integration = IntegrationHandler().get_integration_for_import(
                service_values.get("integration_id"),
                id_mapping,
                application_id=agent.id,
                keep_unmapped=False,
            )
            service = ServiceHandler().import_service(
                integration,
                service_values,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                import_export_config=import_export_config,
            )
            action = AgentAction.objects.create(agent=agent, service=service, **values)
            action_ids[serialized["id"]] = action.id
            copied.append(action)
        return copied
