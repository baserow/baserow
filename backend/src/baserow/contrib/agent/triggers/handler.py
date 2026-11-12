import json
from datetime import datetime
from typing import Any
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db.models import QuerySet

from baserow.contrib.agent.constants import (
    AGENT_TRIGGER_NAME_MAX_LENGTH,
    AGENT_TRIGGER_TYPES_ENABLED,
)
from baserow.contrib.agent.models import AgentApplication, AgentTrigger
from baserow.contrib.agent.types import AgentTriggerUpdated
from baserow.contrib.agent.validators import AGENT_TEXT_MAX_LENGTH
from baserow.core.formula import resolve_formula
from baserow.core.formula.registries import formula_runtime_function_registry
from baserow.core.formula.types import BaserowFormulaObject
from baserow.core.formula.validator import ensure_string
from baserow.core.registries import ImportExportConfig
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.models import Service
from baserow.core.services.registries import (
    TriggerServiceTypeMixin,
    service_type_registry,
)
from baserow.core.storage import ExportZipFile
from baserow.core.trash.handler import TrashHandler

from .data_providers import AgentTriggerDispatchContext
from .exceptions import AgentTriggerDoesNotExist, AgentTriggerTypeNotAvailable


class AgentTriggerHandler:
    """The triggers of Agents and their services, without permission checks."""

    def get_trigger(
        self, trigger_id: int, base_queryset: QuerySet[AgentTrigger] | None = None
    ) -> AgentTrigger:
        """
        Fetch a trigger with its agent, workspace and service.

        :param trigger_id: The id of the trigger.
        :param base_queryset: The queryset to look the trigger up in, to add a lock
            or a filter. Defaults to the triggers that aren't trashed.
        :raises AgentTriggerDoesNotExist: When the trigger doesn't exist or is
            trashed.
        :return: The trigger.
        """

        queryset = (
            base_queryset if base_queryset is not None else AgentTrigger.objects.all()
        )
        try:
            return queryset.select_related("agent__workspace", "service").get(
                id=trigger_id
            )
        except AgentTrigger.DoesNotExist as exc:
            raise AgentTriggerDoesNotExist from exc

    def list_triggers(self, agent: AgentApplication) -> list[AgentTrigger]:
        """
        Return the agent's triggers with their specific services, oldest first,
        loaded with one query per service type rather than one per trigger.

        :param agent: The agent the triggers belong to.
        :return: The triggers that aren't trashed.
        """

        triggers = list(AgentTrigger.objects.filter(agent=agent))
        services = ServiceHandler().get_services(
            base_queryset=Service.objects.filter(
                id__in=[trigger.service_id for trigger in triggers]
            )
        )
        services_by_id = {service.id: service for service in services}
        for trigger in triggers:
            if trigger.service_id in services_by_id:
                trigger.service = services_by_id[trigger.service_id]
        return triggers

    def available_trigger_types(self, agent: AgentApplication) -> list[str]:
        """
        List the trigger types a trigger of this Agent can have, in registry order.

        :param agent: The Agent the triggers would belong to.
        :return: The names of the registered trigger service types the picker
            allows, minus the ones deactivated in the Agent's workspace.
        """

        return [
            service_type.type
            for service_type in service_type_registry.get_all()
            if isinstance(service_type, TriggerServiceTypeMixin)
            and service_type.type in AGENT_TRIGGER_TYPES_ENABLED
            and not service_type.is_deactivated(agent.workspace)
        ]

    def check_type_available(self, agent: AgentApplication, type_name: str) -> None:
        """
        :param agent: The Agent the trigger belongs to.
        :param type_name: The service type of the trigger.
        :raises AgentTriggerTypeNotAvailable: When the Agent's configuration doesn't
            offer the type, so no trigger of it may be created, armed or fired.
        """

        if type_name not in self.available_trigger_types(agent):
            raise AgentTriggerTypeNotAvailable(type_name)

    def create_trigger(
        self,
        agent: AgentApplication,
        service_type: TriggerServiceTypeMixin,
        prepared_service_values: dict,
        message: str | BaserowFormulaObject = "",
        enabled: bool = True,
        name: str = "",
    ) -> AgentTrigger:
        """
        Create a trigger with a new service of the given type and arm it.

        :param agent: The agent the trigger starts conversations in.
        :param service_type: The trigger service type that produces the events.
        :param prepared_service_values: The service values, already passed through
            ``service_type.prepare_values``.
        :param message: The message formula resolved against the trigger payload.
        :param enabled: Whether firing starts a conversation.
        :param name: The trigger's name, or blank for the type's default.
        :raises AgentTriggerTypeNotAvailable: When the type isn't available.
        :return: The created trigger, with its specific service.
        """

        service = ServiceHandler().create_service(
            service_type, **prepared_service_values
        )
        trigger = AgentTrigger.objects.create(
            agent=agent,
            service=service,
            name=name,
            message=message,
            enabled=enabled,
        )
        self.arm(trigger)
        return trigger

    def update_trigger(
        self,
        trigger: AgentTrigger,
        enabled: bool | None = None,
        message: str | BaserowFormulaObject | None = None,
        prepared_service_values: dict | None = None,
        name: str | None = None,
    ) -> AgentTriggerUpdated:
        """
        Update a trigger, re-arming its service when its values change or the
        trigger is switched on: arming also replaces any schedule a concurrent run
        wrote meanwhile. Values that change nothing aren't written, as saving the
        service could put back a run time a concurrent run already moved on.

        :param trigger: The trigger to update.
        :param enabled: The new enabled state, or None to keep it.
        :param message: The new message formula, or None to keep it.
        :param prepared_service_values: The service values to set, already passed
            through ``prepare_values``, or None to leave the service as it is.
        :param name: The new name, blank for the type's default, or None to keep
            it.
        :raises AgentTriggerTypeNotAvailable: When it would re-arm a trigger of a
            type that isn't available.
        :return: The updated trigger and the names of the parts that changed:
            ``name``, ``enabled``, ``message`` and ``service``.
        """

        service_changed = self._update_service(trigger, prepared_service_values)
        rearm = service_changed
        changed_fields = []
        if name is not None and name != trigger.name:
            trigger.name = name
            changed_fields.append("name")
        if enabled is not None and enabled != trigger.enabled:
            trigger.enabled = enabled
            changed_fields.append("enabled")
            rearm = rearm or enabled
        if message is not None and message != trigger.message:
            trigger.message = message
            changed_fields.append("message")
        if changed_fields:
            trigger.save(update_fields=[*changed_fields, "updated_on"])
        if rearm:
            self.arm(trigger)
        if service_changed:
            changed_fields.append("service")
        return AgentTriggerUpdated(trigger, changed_fields)

    def _update_service(
        self, trigger: AgentTrigger, prepared_service_values: dict | None
    ) -> bool:
        """
        Write the values that differ from the saved ones to the trigger's service.

        :param trigger: The trigger whose service is updated.
        :param prepared_service_values: The service values to set, already passed
            through ``prepare_values``, or None to leave the service as it is.
        :return: Whether any value changed.
        """

        if prepared_service_values is None:
            return False
        service = trigger.service.specific
        changed = self._changes_service(service, prepared_service_values)
        if changed:
            service = (
                ServiceHandler()
                .update_service(service.get_type(), service, **prepared_service_values)
                .service
            )
        trigger.service = service
        return changed

    def _changes_service(self, service: Service, prepared_service_values: dict) -> bool:
        """
        :param service: The specific service of the trigger.
        :param prepared_service_values: The service values to set, already passed
            through ``prepare_values``.
        :return: Whether any of the values differs from the saved one.
        """

        saved = service.get_type().export_prepared_values(service)
        return any(
            key not in saved or saved[key] != value
            for key, value in prepared_service_values.items()
        )

    def delete_trigger(self, user: AbstractUser, trigger: AgentTrigger) -> None:
        """
        Trash a trigger; its service stops receiving events with it.

        :param user: The user deleting the trigger.
        :param trigger: The trigger to trash.
        """

        agent = trigger.agent
        TrashHandler.trash(user, agent.workspace, agent, trigger)

    def arm(self, trigger: AgentTrigger) -> None:
        """
        Make the trigger's service receive real events from now on.

        :param trigger: The trigger whose service is armed, with its Agent.
        :raises AgentTriggerTypeNotAvailable: When the type isn't available.
        """

        service = trigger.service.specific
        service_type = service.get_type()
        self.check_type_available(trigger.agent, service_type.type)
        service_type.arm(service)

    def payload_as_message(self, event_payload: dict[str, Any]) -> str:
        """
        :param event_payload: The payload the trigger's service produced.
        :return: The payload as a fenced JSON block, which opens the conversation
            when the trigger's message has no text of its own.
        """

        payload = json.dumps(event_payload, default=str, indent=2)
        return f"Trigger data:\n```json\n{payload}\n```"[:AGENT_TEXT_MAX_LENGTH]

    def resolve_message(
        self,
        trigger: AgentTrigger,
        event_payload: dict[str, Any],
        fired_at: datetime,
    ) -> str:
        """
        Resolve the trigger's message formula against the event payload. A blank
        result opens the conversation with the payload itself, so a trigger with
        no message still tells the agent what happened.

        :param trigger: The trigger that fired, with its agent and service.
        :param event_payload: The payload its service produced for this event.
        :param fired_at: When the dispatcher handled the event.
        :return: The message that opens the conversation, cut to the length the
            API accepts for a message.
        """

        content = ensure_string(
            resolve_formula(
                BaserowFormulaObject.to_formula(trigger.message),
                formula_runtime_function_registry,
                AgentTriggerDispatchContext(trigger, event_payload, fired_at),
            )
        )
        if not content.strip():
            return self.payload_as_message(event_payload)
        return content[:AGENT_TEXT_MAX_LENGTH]

    def export_triggers(
        self,
        agent: AgentApplication,
        import_export_config: ImportExportConfig | None = None,
        files_zip: ExportZipFile | None = None,
        storage: Storage | None = None,
        cache: dict | None = None,
    ) -> list[dict]:
        """
        Serialize the agent's triggers with their services.

        :param agent: The agent whose triggers are exported.
        :param import_export_config: How the agent is exported; it decides whether
            sensitive service values are redacted.
        :param files_zip: The zip file service files are written to.
        :param storage: The storage service files are read from.
        :param cache: A cache shared across the export.
        :return: The triggers, oldest first, each with its exported service.
        """

        service_handler = ServiceHandler()
        return [
            {
                "id": trigger.id,
                "name": trigger.name,
                "enabled": trigger.enabled,
                "message": trigger.message,
                "service": service_handler.export_service(
                    trigger.service.specific,
                    import_export_config=import_export_config,
                    files_zip=files_zip,
                    storage=storage,
                    cache=cache,
                ),
            }
            for trigger in self.list_triggers(agent)
        ]

    def import_triggers(
        self,
        agent: AgentApplication,
        serialized_triggers: list[dict],
        id_mapping: dict,
        import_export_config: ImportExportConfig | None = None,
        files_zip: ZipFile | None = None,
        storage: Storage | None = None,
        cache: dict | None = None,
    ) -> list[AgentTrigger]:
        """
        Copy triggers into the agent, each switched off: a copy that fired on its
        own would run and bill without anyone asking for it, and a snapshot
        restore can't be told apart from a duplicate. A missing name gets the
        type's default.

        :param agent: The agent the triggers are copied into.
        :param serialized_triggers: The triggers from ``export_triggers``.
        :param id_mapping: The export-to-import id map; ``agent_triggers`` and
            ``services`` are filled in.
        :param import_export_config: How the agent is imported.
        :param files_zip: The zip file service files are read from.
        :param storage: The storage service files are written to.
        :param cache: A cache shared across the import.
        :return: The created triggers, in the exported order.
        """

        trigger_ids = id_mapping.setdefault("agent_triggers", {})
        service_handler = ServiceHandler()
        triggers = []
        for serialized in serialized_triggers:
            service = service_handler.import_service(
                None,
                serialized["service"],
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                cache=cache,
                import_export_config=import_export_config,
            )
            name = serialized.get("name")
            trigger = AgentTrigger.objects.create(
                agent=agent,
                service=service,
                name=name[:AGENT_TRIGGER_NAME_MAX_LENGTH]
                if isinstance(name, str)
                else "",
                enabled=False,
                message=serialized.get("message") or "",
            )
            trigger_ids[serialized["id"]] = trigger.id
            triggers.append(trigger)
        return triggers
