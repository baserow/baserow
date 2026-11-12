import json
from datetime import datetime
from typing import Any
from zipfile import ZipFile

from django.contrib.auth.models import AbstractUser
from django.core.files.storage import Storage
from django.db.models import Count, Exists, OuterRef, Q, QuerySet, Subquery
from django.db.models.functions import Coalesce

from baserow.contrib.agent.constants import (
    AGENT_RUN_TYPE,
    AGENT_TRIGGER_DEFAULT_BATCH_SIZE,
    AGENT_TRIGGER_MAX_BATCH_SIZE,
    AGENT_TRIGGER_NAME_MAX_LENGTH,
    AGENT_TRIGGER_TYPES_ENABLED,
)
from baserow.contrib.agent.formula_importer import import_formula
from baserow.contrib.agent.models import (
    AgentApplication,
    AgentConversation,
    AgentMessage,
    AgentReplyStatus,
    AgentTrigger,
)
from baserow.contrib.agent.signals import agent_conversation_activity
from baserow.contrib.agent.types import AgentTriggerTypeOptions, AgentTriggerUpdated
from baserow.contrib.agent.validators import AGENT_TEXT_MAX_LENGTH
from baserow.core.chat_runs.constants import ChatRunErrorCode
from baserow.core.chat_runs.models import ACTIVE_CHAT_RUN_STATUSES, ChatRun
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
from baserow.core.types import Subject

from .data_providers import AgentTriggerDispatchContext, rows_as_text
from .exceptions import (
    AgentTriggerDoesNotExist,
    AgentTriggerNoAccess,
    AgentTriggerTypeNotAvailable,
)
from .overlap import get_overlap_limits


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

    def default_on_overlap(
        self, service_type: TriggerServiceTypeMixin
    ) -> AgentTrigger.OnOverlap:
        """
        :param service_type: The service type of a trigger.
        :return: What a new trigger of the type does while its previous reply is
            going: skip when a later event makes up for a skipped one, like a
            schedule's next tick, else wait, so no event is lost.
        """

        if service_type.events_can_be_skipped:
            return AgentTrigger.OnOverlap.SKIP
        return AgentTrigger.OnOverlap.WAIT

    def create_trigger(
        self,
        agent: AgentApplication,
        service_type: TriggerServiceTypeMixin,
        prepared_service_values: dict,
        message: str | BaserowFormulaObject = "",
        enabled: bool = True,
        on_overlap: str | None = None,
        batch_size: int = AGENT_TRIGGER_DEFAULT_BATCH_SIZE,
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
        :param on_overlap: What a firing does while a reply of the trigger is still
            going, one of ``AgentTrigger.OnOverlap``, or None for the type's default.
        :param batch_size: How many records of a list payload one conversation
            receives.
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
            on_overlap=on_overlap or self.default_on_overlap(service_type),
            batch_size=batch_size,
        )
        self.arm(trigger)
        return trigger

    def update_trigger(
        self,
        trigger: AgentTrigger,
        enabled: bool | None = None,
        message: str | BaserowFormulaObject | None = None,
        prepared_service_values: dict | None = None,
        on_overlap: str | None = None,
        batch_size: int | None = None,
        name: str | None = None,
        service_type: TriggerServiceTypeMixin | None = None,
    ) -> AgentTriggerUpdated:
        """
        Update a trigger, re-arming its service when its values change or the
        trigger is switched on: arming also replaces any schedule a concurrent run
        wrote meanwhile. Values that change nothing aren't written, as saving the
        service could put back a run time a concurrent run already moved on.
        Switching it off cancels its queued replies. Another service type replaces
        the service with a new one of that type and clears the last skip, which
        the old type caused; the trigger keeps its id, so its conversations stay
        linked, and its other settings.

        :param trigger: The trigger to update.
        :param enabled: The new enabled state, or None to keep it.
        :param message: The new message formula, or None to keep it.
        :param prepared_service_values: The service values to set, already passed
            through ``prepare_values`` of the type the service ends up with, or
            None to leave the service as it is.
        :param on_overlap: The new overlap rule, or None to keep it.
        :param batch_size: The new batch size, or None to keep it.
        :param name: The new name, blank for the type's default, or None to keep
            it.
        :param service_type: The service type the trigger should have, or None to
            keep its own.
        :raises AgentTriggerTypeNotAvailable: When it would re-arm a trigger of a
            type that isn't available.
        :return: The updated trigger and the names of the parts that changed:
            ``name``, ``enabled``, ``message``, ``on_overlap``, ``batch_size``,
            ``type`` and ``service``.
        """

        replaced_service = None
        if (
            service_type is not None
            and service_type.type != trigger.service.get_type().type
        ):
            replaced_service = trigger.service.specific
            trigger.service = ServiceHandler().create_service(
                service_type, **(prepared_service_values or {})
            )
            service_changed = True
        else:
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
        if on_overlap is not None and on_overlap != trigger.on_overlap:
            trigger.on_overlap = on_overlap
            changed_fields.append("on_overlap")
        if batch_size is not None and batch_size != trigger.batch_size:
            trigger.batch_size = batch_size
            changed_fields.append("batch_size")
        saved_fields = [*changed_fields]
        if replaced_service is not None:
            trigger.last_skipped_on, trigger.last_skipped_reason = None, ""
            saved_fields += ["service", "last_skipped_on", "last_skipped_reason"]
            changed_fields.append("type")
        if saved_fields:
            trigger.save(update_fields=[*saved_fields, "updated_on"])
        if replaced_service is not None:
            ServiceHandler().delete_service(
                replaced_service.get_type(), replaced_service
            )
        if "enabled" in changed_fields and not trigger.enabled:
            self.cancel_queued_replies(trigger)
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

    def can_identity_read(
        self, trigger: AgentTrigger, identity: Subject | None
    ) -> bool:
        """
        :param trigger: The trigger, with its agent and service.
        :param identity: The agent's run identity, or None when it has none it can
            act as.
        :return: Whether the identity may read what the trigger's events carry; a
            type whose events carry no workspace data needs no identity.
        """

        service = trigger.service.specific
        return service.get_type().can_subject_read(
            service, identity, trigger.agent.workspace
        )

    def check_identity_can_read(
        self, trigger: AgentTrigger, identity: Subject | None
    ) -> None:
        """
        :param trigger: The trigger, with its agent and service.
        :param identity: The agent's run identity, or None when it has none it can
            act as.
        :raises AgentTriggerNoAccess: When the identity may not read what the
            trigger's events carry.
        """

        if not self.can_identity_read(trigger, identity):
            raise AgentTriggerNoAccess()

    def list_trigger_types(
        self, agent: AgentApplication, identity: Subject | None
    ) -> list[AgentTriggerTypeOptions]:
        """
        Describe each trigger type the agent may use: what its form may choose
        from for the agent's run identity, and the overlap rule a new trigger of
        it gets.

        :param agent: The agent, with its workspace.
        :param identity: The agent's run identity, or None when it has none it can
            act as.
        :return: One entry per available type, in registry order.
        """

        options = []
        for type_name in self.available_trigger_types(agent):
            service_type = service_type_registry.get(type_name)
            options.append(
                AgentTriggerTypeOptions(
                    type=type_name,
                    form_choices=service_type.get_form_choices(
                        identity, agent.workspace
                    ),
                    default_on_overlap=self.default_on_overlap(service_type),
                )
            )
        return options

    def payload_as_message(
        self, trigger: AgentTrigger, event_payload: dict[str, Any]
    ) -> str:
        """
        :param trigger: The trigger that fired, with its service.
        :param event_payload: The payload its service produced, or one batch of a
            list payload.
        :return: The payload as fenced JSON, which opens the conversation when the
            trigger's message has no text of its own: a list payload as its event
            values, then its rows as `trigger.rows` reads them.
        """

        service = trigger.service.specific
        service_type = service.get_type()
        data, rows = event_payload, ""
        if service_type.returns_list(service):
            data = service_type.get_event_context(service, event_payload)
            rows = rows_as_text(service, event_payload)
        payload = json.dumps(data, default=str, indent=2)
        return f"Trigger data:\n```json\n{payload}\n```{rows}"[:AGENT_TEXT_MAX_LENGTH]

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
            return self.payload_as_message(trigger, event_payload)
        return content[:AGENT_TEXT_MAX_LENGTH]

    def get_startable_triggers(self) -> QuerySet[AgentTrigger]:
        """
        Return the triggers whose queued replies may start: switched on and not
        trashed, in an agent and a workspace that aren't trashed. The others keep
        their queued replies, which resume after a restore.

        :return: The triggers.
        """

        return AgentTrigger.objects.filter(
            enabled=True, agent__trashed=False, agent__workspace__trashed=False
        )

    def cancel_queued_replies(self, trigger: AgentTrigger) -> None:
        """
        Cancel the trigger's queued replies, deleted conversations included, once
        nothing will start them: the trigger is switched off or deleted for good.
        They are marked ``not_started``, so they don't read as stopped mid-run. The
        readers of the other conversations are told.

        :param trigger: The trigger whose queued replies are cancelled.
        """

        replies = AgentMessage.objects.filter(
            conversation__trigger=trigger, status=AgentReplyStatus.QUEUED
        )
        conversations = list(
            AgentConversation.objects.filter(
                id__in=replies.values("conversation_id")
            ).select_related("agent")
        )
        replies.update(
            status=AgentReplyStatus.CANCELLED, error_code=ChatRunErrorCode.NOT_STARTED
        )
        for conversation in conversations:
            agent_conversation_activity.send(self, conversation=conversation, user=None)

    def _is_going(self) -> Q:
        """
        The condition a going reply meets: it waits for approvals, or it runs while
        its conversation has an active run. A reply its run left ``running`` when
        ending without saving it, for example on a database error, never holds its
        trigger back, nor does a reply in a deleted conversation.

        :return: The condition on ``AgentMessage``.
        """

        active_run = ChatRun.objects.filter(
            run_type=AGENT_RUN_TYPE,
            chat_id=OuterRef("conversation_id"),
            status__in=ACTIVE_CHAT_RUN_STATUSES,
        )
        return Q(conversation__trashed=False) & (
            Q(status=AgentReplyStatus.WAITING)
            | Q(Exists(active_run), status=AgentReplyStatus.RUNNING)
        )

    def count_going_replies(self, trigger: AgentTrigger) -> int:
        """
        :param trigger: The trigger whose conversations are looked at.
        :return: How many of its replies hold a run or wait for approvals.
        """

        return AgentMessage.objects.filter(
            self._is_going(), conversation__trigger=trigger
        ).count()

    def get_queued_replies(self, trigger: AgentTrigger) -> QuerySet[AgentMessage]:
        """
        Return the trigger's replies waiting, without a run, for its previous reply
        to end. Deleted conversations are left out: their replies wait until they
        are restored.

        :param trigger: The trigger whose conversations are looked at.
        :return: The queued replies, oldest first.
        """

        return AgentMessage.objects.filter(
            conversation__trigger=trigger,
            conversation__trashed=False,
            status=AgentReplyStatus.QUEUED,
        ).order_by("id")

    def count_queued_replies(self, trigger: AgentTrigger) -> int:
        """
        :param trigger: The trigger whose conversations are looked at.
        :return: How many of its replies are queued.
        """

        return self.get_queued_replies(trigger).count()

    def list_triggers_with_room_for_queued_replies(self) -> QuerySet[AgentTrigger]:
        """
        Find the triggers whose oldest queued reply can start now: one of their
        replies is queued and fewer are going than their overlap rule allows. One
        query, read from the index of replies still queued or going, however long
        the triggers' history is.

        :return: The startable triggers, by id, with their agent, workspace and
            service.
        """

        replies = AgentMessage.objects.filter(conversation__trigger=OuterRef("pk"))
        going = Coalesce(
            Subquery(
                replies.filter(self._is_going())
                .values("conversation__trigger")
                .annotate(count=Count("id"))
                .values("count")
            ),
            0,
        )
        has_room = Q()
        for on_overlap in AgentTrigger.OnOverlap.values:
            max_going = get_overlap_limits(on_overlap).max_going
            has_room |= Q(on_overlap=on_overlap) & (
                Q() if max_going is None else Q(going__lt=max_going)
            )
        return (
            self.get_startable_triggers()
            .select_related("agent__workspace", "service")
            .annotate(going=going)
            .filter(
                has_room,
                Exists(
                    replies.filter(
                        status=AgentReplyStatus.QUEUED, conversation__trashed=False
                    )
                ),
            )
        )

    def recent_conversation_times(
        self, trigger: AgentTrigger, since: datetime
    ) -> list[datetime]:
        """
        When the trigger started each of its conversations since a moment, deleted
        ones included, so deleting conversations never lifts a limit.

        :param trigger: The trigger.
        :param since: The oldest creation time counted.
        :return: The creation times, unordered.
        """

        return list(
            AgentConversation.objects_and_trash.filter(
                trigger=trigger, created_on__gte=since
            )
            .order_by()
            .values_list("created_on", flat=True)
        )

    def recent_agent_conversation_times(
        self, agent: AgentApplication, since: datetime
    ) -> list[datetime]:
        """
        When any trigger of the agent started a conversation since a moment,
        deleted conversations and trashed triggers included. Joining through the
        triggers reads the trigger and creation time index.

        :param agent: The agent.
        :param since: The oldest creation time counted.
        :return: The creation times, unordered.
        """

        return list(
            AgentConversation.objects_and_trash.filter(
                trigger__agent=agent, created_on__gte=since
            )
            .order_by()
            .values_list("created_on", flat=True)
        )

    def record_skip(
        self, trigger: AgentTrigger, reason: AgentTrigger.SkipReason, at: datetime
    ) -> None:
        """
        Save when and why a firing of the trigger started nothing, without signals
        or a new ``updated_on``.

        :param trigger: The trigger whose firing was skipped.
        :param reason: Why it was skipped.
        :param at: When it fired.
        """

        AgentTrigger.objects.filter(id=trigger.id).update(
            last_skipped_on=at, last_skipped_reason=reason
        )
        trigger.last_skipped_on, trigger.last_skipped_reason = at, reason

    def record_fired(self, trigger: AgentTrigger, at: datetime) -> None:
        """
        Save when a firing of the trigger last started or queued a conversation,
        which hides an older skip on its card.

        :param trigger: The trigger that fired.
        :param at: When it fired.
        """

        AgentTrigger.objects.filter(id=trigger.id).update(last_fired_on=at)
        trigger.last_fired_on = at

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
                "on_overlap": trigger.on_overlap,
                "batch_size": trigger.batch_size,
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
        restore can't be told apart from a duplicate. A missing or unknown overlap
        rule gets the type's default, a missing or invalid batch size 20 and a
        missing name the type's default. The message follows the imported ids,
        such as the fields of a row trigger's table.

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
            on_overlap = serialized.get("on_overlap")
            if on_overlap not in AgentTrigger.OnOverlap.values:
                on_overlap = self.default_on_overlap(service.get_type())
            batch_size = serialized.get("batch_size")
            if (
                not isinstance(batch_size, int)
                or not 1 <= batch_size <= AGENT_TRIGGER_MAX_BATCH_SIZE
            ):
                batch_size = AGENT_TRIGGER_DEFAULT_BATCH_SIZE
            name = serialized.get("name")
            trigger = AgentTrigger.objects.create(
                agent=agent,
                service=service,
                name=name[:AGENT_TRIGGER_NAME_MAX_LENGTH]
                if isinstance(name, str)
                else "",
                enabled=False,
                message=import_formula(
                    serialized.get("message") or "",
                    id_mapping,
                    service=service.specific,
                ),
                on_overlap=on_overlap,
                batch_size=batch_size,
            )
            trigger_ids[serialized["id"]] = trigger.id
            triggers.append(trigger)
        return triggers
