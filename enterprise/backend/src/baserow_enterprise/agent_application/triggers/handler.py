from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.contrib.integrations.core.models import (
    CoreHTTPTriggerService,
    CoreInboundEmailTriggerService,
    CorePeriodicService,
)
from baserow.contrib.integrations.core.utils import calculate_next_periodic_run
from baserow.core.integrations.models import Integration
from baserow.core.services.exceptions import ServiceTypeDoesNotExist
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import (
    TriggerServiceTypeMixin,
    service_type_registry,
)

from ..exceptions import AgentTriggerDoesNotExist
from ..models import AgentApplication, AgentTrigger
from ..signals import agent_trigger_created, agent_trigger_updated
from .registries import agent_trigger_type_registry


def check_service_table_in_workspace(prepared_values: dict, application) -> None:
    """
    A table outside the application's workspace would feed that workspace's
    rows into this one's conversations, readable by everyone who may read
    chats here, for as long as the creator happens to be a member there.

    :raises DRFValidationError: When the resolved table belongs elsewhere.
    """

    table = prepared_values.get("table")
    if table is not None and table.database.workspace_id != application.workspace_id:
        raise DRFValidationError(
            detail="The table must belong to the application's workspace.",
            code="invalid_table",
        )
    target = prepared_values.get("agent_application")
    if target is not None and target.workspace_id != application.workspace_id:
        raise DRFValidationError(
            detail="The agent must belong to the application's workspace.",
            code="invalid_agent_application",
        )


def schedule_periodic_service(service) -> None:
    """
    Agent triggers have no publish step, so the first run of a periodic
    service is scheduled when it is created or edited; without `next_run_at`
    the scheduler treats it as due at its next tick.
    """

    if not isinstance(service, CorePeriodicService):
        return
    service.next_run_at = calculate_next_periodic_run(
        interval=service.interval,
        minute=service.minute,
        hour=service.hour,
        day_of_week=service.day_of_week,
        day_of_month=service.day_of_month,
        tz=service.timezone,
    )
    service.save(update_fields=["next_run_at"])


class AgentTriggerHandler:
    def list_triggers(self, application: AgentApplication) -> QuerySet:
        return AgentTrigger.objects.filter(application=application).select_related(
            "service"
        )

    def get_trigger(self, trigger_id: int) -> AgentTrigger:
        try:
            return AgentTrigger.objects.select_related(
                "application__workspace", "service"
            ).get(
                id=trigger_id,
                application__trashed=False,
                application__workspace__trashed=False,
            )
        except AgentTrigger.DoesNotExist:
            raise AgentTriggerDoesNotExist(
                f"The trigger with id {trigger_id} does not exist."
            )

    def _validate_service_type(self, service_type_str: str):
        try:
            service_type = service_type_registry.get(service_type_str)
        except ServiceTypeDoesNotExist as exc:
            raise DRFValidationError(
                detail=f"The service type {service_type_str} does not exist.",
                code="invalid_service_type",
            ) from exc

        if not isinstance(service_type, TriggerServiceTypeMixin):
            raise DRFValidationError(
                detail=f"The service type {service_type_str} is not a trigger.",
                code="invalid_service_type",
            )

        # Raises when no agent trigger type is mapped to this service type.
        agent_trigger_type_registry.get_by_service_type(service_type_str)

        return service_type

    def _validate_integration(self, application: AgentApplication, values: dict):
        integration_id = values.pop("integration_id", None)
        if integration_id is None:
            return values

        integration = Integration.objects.filter(
            id=integration_id, application=application
        ).first()
        if integration is None:
            raise DRFValidationError(
                detail=f"The integration {integration_id} does not belong to the "
                "application.",
                code="invalid_integration",
            )

        values["integration"] = integration
        return values

    def create_trigger(
        self,
        user: AbstractUser,
        application: AgentApplication,
        service_type_str: str,
        service_values: Optional[dict] = None,
        enabled: bool = True,
    ) -> AgentTrigger:
        service_type = self._validate_service_type(service_type_str)
        service_values = dict(service_values or {})
        service_values = self._validate_integration(application, service_values)
        prepared_values = service_type.prepare_values(service_values, user)
        check_service_table_in_workspace(prepared_values, application)

        service = ServiceHandler().create_service(service_type, **prepared_values)
        self._publish_service(service)
        schedule_periodic_service(service)

        trigger = AgentTrigger.objects.create(
            application=application, service=service, enabled=enabled
        )
        agent_trigger_created.send(self, trigger=trigger, user=user)
        return trigger

    def _publish_service(self, service) -> None:
        """
        Agent triggers are live as soon as they exist (the agent's active
        switch and the trigger's enabled flag gate the runs), unlike
        automation triggers that only listen once their workflow is
        published. The core webhook endpoint only resolves published HTTP
        trigger services and the inbound email address only published email
        trigger services, so mark them published right away.
        """

        if (
            isinstance(
                service, (CoreHTTPTriggerService, CoreInboundEmailTriggerService)
            )
            and not service.is_public
        ):
            service.is_public = True
            service.save(update_fields=["is_public"])

    def update_trigger(
        self,
        user: AbstractUser,
        trigger: AgentTrigger,
        service_values: Optional[dict] = None,
        enabled: Optional[bool] = None,
    ) -> AgentTrigger:
        if service_values is not None:
            service = trigger.service.specific
            service_type = service.get_type()
            service_values = self._validate_integration(
                trigger.application, dict(service_values)
            )
            prepared_values = service_type.prepare_values(
                service_values, user, instance=service
            )
            check_service_table_in_workspace(prepared_values, trigger.application)
            ServiceHandler().update_service(service_type, service, **prepared_values)
            schedule_periodic_service(service)

        if enabled is not None and enabled != trigger.enabled:
            trigger.enabled = enabled
            trigger.save(update_fields=["enabled", "updated_on"])

        agent_trigger_updated.send(self, trigger=trigger, user=user)
        return trigger

    def trash_trigger(self, user: AbstractUser, trigger: AgentTrigger) -> None:
        """
        Moves the trigger to the trash so the deletion can be undone. A
        trashed trigger never fires: every trigger lookup goes through the
        default manager, which excludes trashed rows.
        """

        from baserow.core.trash.handler import TrashHandler

        application = trigger.application
        TrashHandler.trash(user, application.workspace, application, trigger)

    def delete_trigger(self, trigger: AgentTrigger) -> None:
        """Permanently deletes the trigger and its service."""

        service = trigger.service.specific
        trigger.delete()
        ServiceHandler().delete_service(service.get_type(), service)
