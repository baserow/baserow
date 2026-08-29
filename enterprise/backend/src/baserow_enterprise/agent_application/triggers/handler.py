from typing import Optional

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from rest_framework.exceptions import ValidationError as DRFValidationError

from baserow.core.integrations.models import Integration
from baserow.core.services.exceptions import ServiceTypeDoesNotExist
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import (
    TriggerServiceTypeMixin,
    service_type_registry,
)

from ..exceptions import AgentTriggerDoesNotExist
from ..models import AgentApplication, AgentTrigger
from .registries import agent_trigger_type_registry


class AgentTriggerHandler:
    def list_triggers(self, application: AgentApplication) -> QuerySet:
        return AgentTrigger.objects.filter(application=application).select_related(
            "service"
        )

    def get_trigger(self, trigger_id: int) -> AgentTrigger:
        try:
            return AgentTrigger.objects.select_related(
                "application__workspace", "service"
            ).get(id=trigger_id)
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

        service = ServiceHandler().create_service(service_type, **prepared_values)

        return AgentTrigger.objects.create(
            application=application, service=service, enabled=enabled
        )

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
            ServiceHandler().update_service(service_type, service, **prepared_values)

        if enabled is not None and enabled != trigger.enabled:
            trigger.enabled = enabled
            trigger.save(update_fields=["enabled", "updated_on"])

        return trigger

    def delete_trigger(self, trigger: AgentTrigger) -> None:
        service = trigger.service.specific
        trigger.delete()
        ServiceHandler().delete_service(service.get_type(), service)
