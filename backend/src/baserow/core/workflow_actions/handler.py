from abc import ABC, abstractmethod
from typing import Dict, Iterable, Optional, Type, cast

from django.core.files.storage import Storage
from django.db.models import QuerySet

from baserow.core.db import specific_iterator
from baserow.core.registry import Registry
from baserow.core.storage import ExportZipFile
from baserow.core.utils import extract_allowed
from baserow.core.workflow_actions.exceptions import WorkflowActionDoesNotExist
from baserow.core.workflow_actions.models import WorkflowAction
from baserow.core.workflow_actions.registries import WorkflowActionType


class WorkflowActionHandler(ABC):
    """
    This is an abstract handler, each module that wants to use workflow actions will
    need to implement their own handler.
    """

    @property
    @abstractmethod
    def model(self) -> Type[WorkflowAction]:
        pass

    @property
    @abstractmethod
    def registry(self) -> Registry:
        pass

    def get_workflow_action(self, workflow_action_id: int) -> WorkflowAction:
        """
        Returns a workflow action from the database.

        The queryset here is not optional since every module needs to provide their
        own model at least.

        :param workflow_action_id: The ID of the workflow action.
        :return: The workflow action instance.
        """

        try:
            return self.model.objects.get(id=workflow_action_id).specific
        except self.model.DoesNotExist:
            raise WorkflowActionDoesNotExist()

    def get_all_workflow_actions(
        self, base_queryset: Optional[QuerySet] = None
    ) -> Iterable[WorkflowAction]:
        """
        Gets all the workflow actions of the defined model.

        :param base_queryset: A query set that lets you prefilter the results
        :return: A list of workflow actions
        """

        if base_queryset is None:
            base_queryset = self.model.objects

        return specific_iterator(
            base_queryset,
            per_content_type_queryset_hook=(
                lambda action, queryset: self.registry.get_by_model(
                    action
                ).enhance_queryset(queryset)
            ),
        )

    def create_workflow_action(
        self, workflow_action_type: WorkflowActionType, **prepared_values
    ) -> WorkflowAction:
        """
        Creates a new workflow action of the given type.

        :param workflow_action_type: The type of the new workflow action
        :param prepared_values: Any fields that need to be set for that specific type
        :return: The created workflow action
        """

        allowed_prepared_values = extract_allowed(
            prepared_values, workflow_action_type.allowed_fields
        )

        model_class = cast(WorkflowAction, workflow_action_type.model_class)

        workflow_action = model_class(**allowed_prepared_values)
        workflow_action.save()

        return workflow_action

    def delete_workflow_action(self, workflow_action: WorkflowAction):
        """
        Deletes a given workflow action.

        :param workflow_action: The workflow action to be deleted
        """

        workflow_action.delete()

    def update_workflow_action(
        self, workflow_action: WorkflowAction, **prepared_values
    ) -> WorkflowAction:
        """
        Update an existing workflow action.

        :param workflow_action: The workflow action you want to update.
        :param prepared_values: The updates you wish to perform on the workflow action.
        :return: The updated workflow action.
        """

        has_type_changed = (
            "type" in prepared_values
            and prepared_values["type"] != workflow_action.get_type().type
        )

        if has_type_changed:
            workflow_action_type = self.registry.get(prepared_values["type"])
        else:
            workflow_action_type = workflow_action.get_type()

        allowed_prepared_values = extract_allowed(
            prepared_values, workflow_action_type.allowed_fields
        )

        if has_type_changed:
            self.delete_workflow_action(workflow_action)
            workflow_action = self.create_workflow_action(
                workflow_action_type, **allowed_prepared_values
            )
        else:
            for key, value in allowed_prepared_values.items():
                setattr(workflow_action, key, value)

            workflow_action.save()

        return workflow_action.specific

    def export_workflow_action(
        self,
        workflow_action,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ):
        """
        Serializes the given workflow action.

        :param workflow_action: The action instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :return: The serialized version.
        """

        return workflow_action.get_type().export_serialized(
            workflow_action, files_zip=files_zip, storage=storage, cache=cache
        )
