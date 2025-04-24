from typing import Any, Dict

from django.contrib.auth.models import AbstractUser

from baserow.contrib.automation.nodes.models import AutomationNode
from baserow.contrib.automation.types import AutomationNodeDict
from baserow.core.registry import (
    CustomFieldsRegistryMixin,
    EasyImportExportMixin,
    Instance,
    InstanceWithFormulaMixin,
    ModelInstanceMixin,
    ModelRegistryMixin,
    PublicCustomFieldsInstanceMixin,
    Registry,
)

AUTOMATION_NODES = "automation_nodes"


class AutomationNodeType(
    InstanceWithFormulaMixin,
    EasyImportExportMixin,
    ModelInstanceMixin,
    PublicCustomFieldsInstanceMixin,
    Instance,
):
    parent_property_name = "workflow"
    id_mapping_name = AUTOMATION_NODES

    class SerializedDict(AutomationNodeDict):
        ...

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: AutomationNode = None,
    ):
        """
        The prepare_values hook gives the possibility to change the provided values
        that just before they are going to be used to create or update the instance. For
        example if an ID is provided, it can be converted to a model instance. Or to
        convert a certain date string to a date object. It's also an opportunity to add
        specific validations.

        :param values: The provided values.
        :param user: The user on whose behalf the change is made.
        :param instance: The current instance if it exists.
        :return: The updated values.
        """

        return values


class AutomationNodeTypeRegistry(
    Registry,
    ModelRegistryMixin,
    CustomFieldsRegistryMixin,
):
    """Contains all registered automation node types."""

    name = "automation_node_type"


automation_node_type_registry = AutomationNodeTypeRegistry()
