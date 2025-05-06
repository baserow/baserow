from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.nodes.models import (
    AutomationServiceNode,
    LocalBaserowCreateRowActionNode,
    LocalBaserowRowCreatedTriggerNode,
)
from baserow.contrib.automation.nodes.registries import (
    AutomationNodeType,
    automation_node_type_registry,
)
from baserow.contrib.automation.types import AutomationNodeDict
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowRowCreatedTriggerServiceType,
    LocalBaserowUpsertRowServiceType,
)
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.registries import service_type_registry


def service_backed_automation_nodes():
    """
    Returns all Automation Node types which are backed by a service.

    This is done by checking if the Automation Node type is a subclass of the
    base `AutomationServiceNodeActionType` class.

    :return: A list of Automation Node types backed by a service.
    """

    return [
        automation_node_type
        for automation_node_type in automation_node_type_registry.get_all()
        if issubclass(automation_node_type.__class__, AutomationServiceNodeActionType)
    ]


class AutomationServiceNodeActionType(AutomationNodeType):
    service_type = None


class AutomationServiceNodeTriggerType(AutomationNodeType):
    service_type = None
    request_serializer_field_names = []

    class SerializedDict(AutomationNodeDict):
        service_id: int

    @property
    def serializer_field_names(self):
        return super().serializer_field_names + ["service", "workflow", "order"]

    @property
    def allowed_fields(self):
        return super().allowed_fields + ["service", "workflow", "order"]

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: AutomationServiceNode = None,
    ):
        """
        Responsible for preparing the service based trigger node. By default,
        the only step is to pass any `service` data into the service.

        :param values: The full trigger node values to prepare.
        :param user: The user on whose behalf the change is made.
        :param instance: A `AutomationServiceNode` subclass instance.
        :return: The modified trigger node values, prepared.
        """

        service_type = service_type_registry.get(self.service_type)

        if not instance:
            # If we haven't received a trigger node instance, we're preparing
            # as part of creating a new node. If this happens, we need to create
            # a new service.
            service = ServiceHandler().create_service(service_type)
        else:
            service = instance.service.specific

        # If we received any service values, prepare them.
        service_values = values.pop("service", None) or {}
        prepared_service_values = service_type.prepare_values(
            service_values, user, service
        )

        # Update the service instance with any prepared service values.
        ServiceHandler().update_service(
            service_type, service, **prepared_service_values
        )

        values["service"] = service
        return super().prepare_values(values, user, instance)


class LocalBaserowUpsertRowNodeType(AutomationServiceNodeActionType):
    type = "upsert_row"
    service_type = LocalBaserowUpsertRowServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_upsert_row_service()
        return {"service": service}


class LocalBaserowCreateRowNodeType(LocalBaserowUpsertRowNodeType):
    type = "create_row"
    model_class = LocalBaserowCreateRowActionNode


class LocalBaserowRowCreatedNodeType(AutomationServiceNodeTriggerType):
    type = "row_created"
    model_class = LocalBaserowRowCreatedTriggerNode
    service_type = LocalBaserowRowCreatedTriggerServiceType.type
