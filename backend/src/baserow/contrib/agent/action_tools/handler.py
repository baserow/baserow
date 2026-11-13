from dataclasses import dataclass
from typing import Any
from zipfile import ZipFile

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db.models import QuerySet

from pydantic_ai import WebSearchTool
from rest_framework.exceptions import ValidationError

from baserow.contrib.agent.models import AgentAction, AgentApplication
from baserow.contrib.agent.registries import agent_tool_type_registry
from baserow.core.integrations.handler import IntegrationHandler
from baserow.core.registries import ImportExportConfig
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import ServiceType
from baserow.core.storage import ExportZipFile
from baserow.core.trash.handler import TrashHandler

from .exceptions import (
    AgentActionDoesNotExist,
    AgentActionLimitReached,
    AgentActionTypeNotAvailable,
)
from .inputs import validate_action_name, validate_inputs
from .registries import agent_action_type_registry


@dataclass
class AgentActionUpdated:
    action: AgentAction
    changed_fields: list[str]
    """The action's changed fields, and ``service`` when its service changed."""


class AgentActionHandler:
    """The actions of Agents and their services, without permission checks."""

    editable_fields = ("name", "description", "inputs", "enabled", "ask_first")

    def _load_services(self, actions: list[AgentAction]) -> list[AgentAction]:
        """
        Give each action its specific service, with that service's specific
        integration, in a number of queries that doesn't grow with the actions.

        :param actions: The actions to complete.
        :return: The same actions.
        """

        services = {
            service.id: service
            for service in ServiceHandler().get_services(
                base_queryset=Service.objects.filter(
                    id__in=[action.service_id for action in actions]
                )
            )
        }
        for action in actions:
            action.service = services[action.service_id]
        return actions

    def get_action(
        self, action_id: int, base_queryset: QuerySet[AgentAction] | None = None
    ) -> AgentAction:
        """
        :param action_id: The id of the action.
        :param base_queryset: Restricts or locks the actions looked up.
        :return: The action, with its agent, workspace and specific service.
        :raises AgentActionDoesNotExist: When it doesn't exist or is trashed.
        """

        queryset = (
            base_queryset if base_queryset is not None else AgentAction.objects.all()
        )
        try:
            action = queryset.select_related("agent__workspace").get(id=action_id)
        except AgentAction.DoesNotExist as exc:
            raise AgentActionDoesNotExist from exc
        return self._load_services([action])[0]

    def list_actions(
        self, agent: AgentApplication, only_enabled: bool = False
    ) -> list[AgentAction]:
        """
        :param agent: The Agent.
        :param only_enabled: Leave out the actions that are switched off.
        :return: The Agent's actions, oldest first, each with its agent, workspace
            and specific service.
        """

        queryset = AgentAction.objects.filter(agent=agent)
        if only_enabled:
            queryset = queryset.filter(enabled=True)
        return self._load_services(list(queryset.select_related("agent__workspace")))

    def available_action_types(self, agent: AgentApplication) -> list[str]:
        """
        :param agent: The Agent.
        :return: The service types that can be added to it as actions.
        """

        return [
            action_type.type
            for action_type in agent_action_type_registry.get_all()
            if action_type.is_available(agent.workspace)
        ]

    def check_type_available(self, agent: AgentApplication, type_name: str) -> None:
        """
        :param agent: The Agent.
        :param type_name: A service type name.
        :raises AgentActionTypeNotAvailable: When it can't be added as an action.
        """

        if type_name not in self.available_action_types(agent):
            raise AgentActionTypeNotAvailable(type_name)

    def check_limit(self, agent: AgentApplication) -> None:
        """
        :param agent: The Agent, locked so that two additions can't both pass.
        :raises AgentActionLimitReached: When it can't have one more action.
        """

        limit = settings.BASEROW_AGENT_MAX_ACTIONS_PER_AGENT
        if limit and AgentAction.objects.filter(agent=agent).count() >= limit:
            raise AgentActionLimitReached(limit)

    def get_configuration_errors(self, action: AgentAction) -> dict[str, str]:
        """
        :param action: The action, with its agent and workspace.
        :return: An error code by field, empty when the action can be called.
        """

        return agent_action_type_registry.get(
            action.service.get_type().type
        ).get_configuration_errors(action)

    def get_callable_actions(self, agent: AgentApplication) -> list[AgentAction]:
        """
        :param agent: The Agent.
        :return: Its actions the model may call: switched on, of an available
            type and completely configured.
        """

        available = set(self.available_action_types(agent))
        return [
            action
            for action in self.list_actions(agent, only_enabled=True)
            if action.service.get_type().type in available
            and not self.get_configuration_errors(action)
        ]

    @staticmethod
    def reserved_names() -> set[str]:
        """
        :return: The names of the tools Baserow itself offers to a reply.
        """

        return {*agent_tool_type_registry.get_types(), WebSearchTool.kind}

    def unique_name(
        self, agent: AgentApplication, name: str, excluding_id: int | None = None
    ) -> str:
        """
        :param agent: The Agent.
        :param name: The wanted name.
        :param excluding_id: An action whose own name doesn't count as taken.
        :return: The name, or the name with the first numeric suffix that neither
            another action of the Agent nor a built-in tool has.
        """

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
        self, agent: AgentApplication, name: str, excluding_id: int | None = None
    ) -> None:
        """
        :param agent: The Agent.
        :param name: The wanted name.
        :param excluding_id: An action whose own name doesn't count as taken.
        :raises ValidationError: When a built-in tool or another action has it.
        """

        if name in self.reserved_names():
            raise ValidationError(
                {"name": "This name is reserved for a built-in tool."}
            )
        if self.unique_name(agent, name, excluding_id) != name:
            raise ValidationError({"name": "An action with this name already exists."})

    def create_action(
        self,
        agent: AgentApplication,
        service_type: ServiceType,
        prepared_service_values: dict[str, Any],
        **values: Any,
    ) -> AgentAction:
        """
        :param agent: The Agent, locked.
        :param service_type: The type of the action's service.
        :param prepared_service_values: The service values, prepared by its type.
        :param values: The action's validated editable fields.
        :return: The new action with its service.
        :raises AgentActionLimitReached: When the Agent can't have one more.
        :raises ValidationError: When the name is taken.
        """

        self.check_limit(agent)
        self.check_name_available(agent, values["name"])
        service = ServiceHandler().create_service(
            service_type, **prepared_service_values
        )
        return AgentAction.objects.create(agent=agent, service=service, **values)

    def update_action(
        self,
        action: AgentAction,
        prepared_service_values: dict[str, Any] | None = None,
        **values: Any,
    ) -> AgentActionUpdated:
        """
        :param action: The action, locked with its Agent.
        :param prepared_service_values: The service values to change, prepared by
            its type. None leaves the service as it is.
        :param values: The validated editable fields to change.
        :return: The action and what changed.
        :raises ValidationError: When the new name is taken.
        """

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
        """
        :param user: The user deleting the action.
        :param action: The action to trash with its service.
        """

        TrashHandler.trash(user, action.agent.workspace, action.agent, action)

    def export_actions(
        self,
        agent: AgentApplication,
        import_export_config: ImportExportConfig | None = None,
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
    ) -> list[dict[str, Any]]:
        """
        :param agent: The Agent whose actions are exported.
        :param import_export_config: How the Agent is exported; it decides whether
            sensitive service values are redacted.
        :param files_zip: The zip file service files are written to.
        :param storage: The storage the files are read from.
        :return: The actions, oldest first, each with its exported service.
        """

        return [
            {
                "id": action.id,
                **{field: getattr(action, field) for field in self.editable_fields},
                "service": ServiceHandler().export_service(
                    action.service,
                    import_export_config=import_export_config,
                    files_zip=files_zip,
                    storage=storage,
                ),
            }
            for action in self.list_actions(agent)
        ]

    def import_actions(
        self,
        agent: AgentApplication,
        serialized_actions: list[dict[str, Any]],
        id_mapping: dict[str, Any],
        import_export_config: ImportExportConfig,
        files_zip: ZipFile | None = None,
        storage: Storage | None = None,
    ) -> list[AgentAction]:
        """
        Copy actions into the Agent. Only a duplicate keeps them switched on: an
        imported or template action would otherwise act without anyone asking.
        The Agent's action limit doesn't apply, as its source had them already.

        :param agent: The Agent the actions are copied into.
        :param serialized_actions: What ``export_actions`` returned.
        :param id_mapping: The ids of the copied objects by their original id,
            completed with the actions under ``agent_actions``.
        :param import_export_config: How the Agent is imported.
        :param files_zip: The zip file service files are read from.
        :param storage: The storage the files are written to.
        :return: The copied actions. One of a type that isn't an action type
            here is left out.
        :raises ValidationError: When a name or the inputs are malformed.
        """

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
                agent,
                validate_action_name(values.get("name", service_values["type"])),
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
