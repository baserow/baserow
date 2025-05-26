from abc import ABC, abstractmethod
from typing import Any, Dict, Type

from django.contrib.auth.models import AbstractUser

from baserow.core.registry import (
    EasyImportExportMixin,
    Instance,
    InstanceWithFormulaMixin,
    ModelInstanceMixin,
)
from baserow.core.services.dispatch_context import DispatchContext
from baserow.core.services.types import DispatchResult
from baserow.core.workflow_actions.models import WorkflowAction
from baserow.core.workflow_actions.types import WorkflowActionDictSubClass


class WorkflowActionType(
    InstanceWithFormulaMixin,
    EasyImportExportMixin,
    ModelInstanceMixin,
    Instance,
    ABC,
):
    SerializedDict: Type[WorkflowActionDictSubClass]

    def serialize_property(
        self,
        workflow_action: WorkflowAction,
        prop_name: str,
        files_zip=None,
        storage=None,
        cache=None,
    ):
        """
        You can customize the behavior of the serialization of a property with this
        hook.
        """

        if prop_name == "type":
            return self.type

        return super().serialize_property(
            workflow_action,
            prop_name,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
        )

    def prepare_values(
        self,
        values: Dict[str, Any],
        user: AbstractUser,
        instance: WorkflowAction = None,
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

    @abstractmethod
    def get_pytest_params(self, pytest_data_fixture) -> Dict[str, Any]:
        """
        Returns a sample of params for this type. This can be used to create
        workflow actions.

        :param pytest_data_fixture: A Pytest data fixture which can be used to
            create related objects when the import / export functionality is tested.
        """

    def get_pytest_params_serialized(
        self, pytest_params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Responsible for returning the pytest params in a serialized format.
        :param pytest_params: The result of `get_pytest_params`.
        """

        return pytest_params

    @abstractmethod
    def dispatch(
        self, workflow_action: "WorkflowAction", dispatch_context: DispatchContext
    ) -> DispatchResult:
        """Dispatches the provided workflow action."""

        ...
