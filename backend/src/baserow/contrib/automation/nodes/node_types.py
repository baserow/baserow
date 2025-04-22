from typing import Dict
from typing import Any, Union

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.nodes.registries import AutomationNodeType, automation_node_type_registry
from baserow.contrib.automation.nodes.models import (
    LocalBaserowCreateRowActionNode,
    LocalBaserowUpdateRowActionNode,
    LocalBaserowRowCreatedTriggerNode,
    LocalBaserowRowUpdatedTriggerNode,
)
from baserow.contrib.integrations.local_baserow.service_types import (
    LocalBaserowUpsertRowServiceType,
    LocalBaserowRowCreatedTriggerServiceType,
    LocalBaserowRowUpdatedTriggerServiceType,
)
from baserow.core.services.registries import service_type_registry
from baserow.core.services.handler import ServiceHandler


def service_backed_automation_nodes():
    """
    Returns all Automation Node types which are backed by a service.

    This is done by checking if the Automation Node type is a subclass of the
    base `AutomationNodeServiceActionType` class.

    :return: A list of Automation Node types backed by a service.
    """

    return [
        automation_node_type
        for automation_node_type in automation_node_type_registry.get_all()
        if issubclass(automation_node_type.__class__, AutomationNodeServiceActionType)
    ]


class AutomationNodeServiceActionType(AutomationNodeType):
    service_type = None


class AutomationNodeServiceTriggerType(AutomationNodeType):
    service_type = None
    allowed_fields = ["order"]

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: Union[
            LocalBaserowRowCreatedTriggerNode, LocalBaserowRowUpdatedTriggerNode
        ] = None,
    ):
        """
        Responsible for preparing the service based trigger node. By default,
        the only step is to pass any `service` data into the service.

        :param values: The full trigger node values to prepare.
        :param user: The user on whose behalf the change is made.
        :param instance: A `ServiceTriggerNode` subclass instance.
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


class UpsertRowNodeType(AutomationNodeServiceActionType):
    type = "upsert_row"
    service_type = LocalBaserowUpsertRowServiceType.type

    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, int]:
        service = pytest_data_fixture.create_local_baserow_upsert_row_service()
        return {"service": service}


class CreateRowNodeType(UpsertRowNodeType):
    type = "create_row"
    model_class = LocalBaserowCreateRowActionNode


class UpdateRowNodeType(UpsertRowNodeType):
    type = "update_row"
    model_class = LocalBaserowUpdateRowActionNode


class RowCreatedNodeType(AutomationNodeServiceTriggerType):
    type = "row_created"
    model_class = LocalBaserowRowCreatedTriggerNode
    service_type = LocalBaserowRowCreatedTriggerServiceType.type


class RowUpdatedNodeType(AutomationNodeServiceTriggerType):
    type = "row_updated"
    model_class = LocalBaserowRowUpdatedTriggerNode
    service_type = LocalBaserowRowUpdatedTriggerServiceType.type
