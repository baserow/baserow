import pytest

from baserow.api.services.serializers import (
    PolymorphicServiceRequestSerializer,
    PolymorphicServiceSerializer,
    PublicPolymorphicServiceSerializer,
)
from baserow.contrib.automation.api.nodes.serializers import (
    CreateAutomationNodeSerializer,
    UpdateAutomationNodeSerializer,
)
from baserow.contrib.automation.nodes.node_types import LocalBaserowGetRowNodeType
from baserow.contrib.automation.nodes.registries import automation_node_type_registry
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    CreateRowWorkflowActionType,
)
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.contrib.database.workflow_actions.workflow_action_types import (
    LocalBaserowCreateRowWorkflowActionType,
)


def service_field(serializer_class):
    return serializer_class().fields["service"]


@pytest.mark.parametrize(
    "registry,type_class,serializer_kwargs",
    [
        (builder_workflow_action_type_registry, CreateRowWorkflowActionType, {}),
        (
            database_workflow_action_type_registry,
            LocalBaserowCreateRowWorkflowActionType,
            {},
        ),
        (
            automation_node_type_registry,
            LocalBaserowGetRowNodeType,
            {"base_class": UpdateAutomationNodeSerializer},
        ),
    ],
)
def test_request_serializer_service_field_is_pinned_to_the_service_type(
    registry, type_class, serializer_kwargs
):
    instance_type = registry.get(type_class.type)

    serializer_class = instance_type.get_serializer_class(
        request_serializer=True, **serializer_kwargs
    )

    field = service_field(serializer_class)
    assert isinstance(field, PolymorphicServiceRequestSerializer)
    assert field.default_type_name is not None
    assert field.default_type_name == type_class.service_type


def test_response_serializer_service_field_is_untouched():
    instance_type = builder_workflow_action_type_registry.get(
        CreateRowWorkflowActionType.type
    )

    field = service_field(instance_type.get_serializer_class())

    assert type(field) is PolymorphicServiceSerializer
    assert field.default_type_name is None


def test_public_request_serializer_service_field_is_untouched():
    instance_type = builder_workflow_action_type_registry.get(
        CreateRowWorkflowActionType.type
    )

    field = service_field(
        instance_type.get_serializer_class(
            request_serializer=True, extra_params={"public": True}
        )
    )

    assert type(field) is PublicPolymorphicServiceSerializer


def test_request_serializer_without_a_service_field_gains_none():
    """
    An automation node is created without a service, and the create view
    documents per-type request serializers over that base, so the pinned
    field must not be declared where `service` isn't a field.
    """

    instance_type = automation_node_type_registry.get(LocalBaserowGetRowNodeType.type)

    serializer_class = instance_type.get_serializer_class(
        request_serializer=True, base_class=CreateAutomationNodeSerializer
    )

    assert "service" not in serializer_class().fields
