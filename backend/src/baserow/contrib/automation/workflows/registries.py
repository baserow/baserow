from abc import ABC
from decimal import Decimal

from baserow.contrib.automation.models import Automation, AutomationWorkflow
from baserow.contrib.automation.types import AutomationWorkflowDict
from baserow.contrib.automation.workflows.exceptions import (
    AutomationWorkflowTypeDoesNotExist,
)
from baserow.core.registry import (
    CustomFieldsInstanceMixin,
    CustomFieldsRegistryMixin,
    EasyImportExportMixin,
    Instance,
    ModelInstanceMixin,
    ModelRegistryMixin,
    Registry,
)

AUTOMATION_WORKFLOWS = "automation_workflows"


class WorkflowType(
    EasyImportExportMixin[AutomationWorkflow],
    CustomFieldsInstanceMixin,
    ModelInstanceMixin[AutomationWorkflow],
    Instance,
    ABC,
):
    SerializedDict = AutomationWorkflowDict
    parent_property_name = "automation"
    id_mapping_name = AUTOMATION_WORKFLOWS
    allowed_fields = ["name"]

    def before_create(self, automation: Automation):
        """
        Perform checks and operations before a workflow is created.

        :param automation: The automation where the workflow should be created.
        """

        pass

    def prepare_value_for_db(
        self, values: dict, instance: AutomationWorkflow | None = None
    ):
        """
        Hook into the moment a workflow is created or updated. If the workflow
        is updated, `instance` of the current workflow will be defined.

        :param values: The values that are being updated.
        :param instance: (optional) The existing instance that is being updated.
        """

        return values

    def export_prepared_values(self, instance: AutomationWorkflow):
        """
        Return a serializable dict of prepared values for the workflow attributes.

        It is called by undo/redo ActionHandler to store the values in a way that
        could be restored later.

        :param instance: The workflow instance to export values for.
        :return: A dict of prepared values.
        """

        values = {key: getattr(instance, key) for key in self.allowed_fields}
        return values

    def after_delete(self, instance: AutomationWorkflow):
        """
        Hook into the moment after a workflow is deleted.

        :param instance: The instance that was deleted.
        """

        pass

    def before_trashed(self, instance: AutomationWorkflow):
        """
        Hook into the process of trashing a workflow and do workflow type
        specific steps.

        :param instance: The instance that will be restored.
        """

        pass

    def before_restore(self, instance: AutomationWorkflow):
        """
        Hook into the process of restoring a workflow and do workflow type
        specific steps.

        :param instance: The instance that will be restored.
        """

        pass

    def deserialize_property(
        self,
        prop_name: str,
        value: any,
        id_mapping: dict[str, any],
        **kwargs,
    ) -> any:
        if prop_name == "order" and value:
            return Decimal(value)

        return super().deserialize_property(
            prop_name,
            value,
            id_mapping,
            **kwargs,
        )

    def serialize_property(
        self,
        instance: AutomationWorkflow,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        if prop_name == "order":
            return str(instance.order)

        return super().serialize_property(
            instance,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )


class AutomationWorkflowTypeRegistry(
    Registry[WorkflowType],
    ModelRegistryMixin[AutomationWorkflow, WorkflowType],
    CustomFieldsRegistryMixin,
):
    """
    Contains all registered workflow types.
    """

    name = "automation_workflow"
    does_not_exist_exception_class = AutomationWorkflowTypeDoesNotExist


automation_workflow_type_registry = AutomationWorkflowTypeRegistry()
