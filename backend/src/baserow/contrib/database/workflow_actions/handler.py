from typing import TYPE_CHECKING, Iterable, List, Optional, Type

from django.db.models import QuerySet

from baserow.contrib.database.data_providers.registries import (
    database_data_provider_type_registry,
)
from baserow.contrib.database.fields.models import ButtonField
from baserow.contrib.database.workflow_actions.exceptions import (
    WorkflowActionNotInField,
)
from baserow.contrib.database.workflow_actions.models import DatabaseWorkflowAction
from baserow.contrib.database.workflow_actions.registries import (
    database_workflow_action_type_registry,
)
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.registry import Registry
from baserow.core.services.handler import ServiceHandler
from baserow.core.services.types import DispatchResult
from baserow.core.utils import extract_allowed
from baserow.core.workflow_actions.exceptions import WorkflowActionDoesNotExist
from baserow.core.workflow_actions.handler import WorkflowActionHandler
from baserow.core.workflow_actions.registries import WorkflowActionType

if TYPE_CHECKING:
    from baserow.contrib.database.workflow_actions.dispatch_context import (
        DatabaseDispatchContext,
    )


class DatabaseWorkflowActionHandler(WorkflowActionHandler):
    @property
    def model(self) -> Type[DatabaseWorkflowAction]:
        return DatabaseWorkflowAction

    @property
    def registry(self) -> Registry:
        return database_workflow_action_type_registry

    def get_workflow_actions(
        self, field: ButtonField, base_queryset: Optional[QuerySet] = None
    ) -> Iterable[DatabaseWorkflowAction]:
        """
        Returns a button field's actions, in order, as specific instances.

        :param field: The button field the actions belong to.
        :param base_queryset: A queryset with filters already applied.
        :return: The field's workflow actions.
        """

        if base_queryset is None:
            base_queryset = self.model.objects

        return super().get_all_workflow_actions(base_queryset.filter(field=field))

    def create_workflow_action(
        self, workflow_action_type: WorkflowActionType, **kwargs
    ) -> DatabaseWorkflowAction:
        """
        Applies the next `order` in the field's scope when one is not given.

        :param workflow_action_type: The action's type.
        :return: The newly created workflow action instance.
        """

        if "order" not in kwargs:
            kwargs["order"] = DatabaseWorkflowAction.get_last_order(kwargs["field"])

        return super().create_workflow_action(workflow_action_type, **kwargs).specific

    def get_workflow_action_for_update(
        self, workflow_action_id: int
    ) -> DatabaseWorkflowAction:
        """
        Returns an action with its row locked, so two writers cannot change the
        same action's type at once.

        :param workflow_action_id: The id of the workflow action.
        :raises WorkflowActionDoesNotExist: When the id belongs to no action.
        :return: The workflow action instance.
        """

        try:
            return (
                self.model.objects.select_for_update()
                .get(id=workflow_action_id)
                .specific
            )
        except self.model.DoesNotExist:
            raise WorkflowActionDoesNotExist()

    def change_workflow_action_type(
        self,
        workflow_action: DatabaseWorkflowAction,
        workflow_action_type: WorkflowActionType,
        **prepared_values,
    ) -> DatabaseWorkflowAction:
        """
        Swaps an action's type in place, the way a field type change does, so
        the action keeps its id and its place in the order.

        :param workflow_action: The action whose type changes.
        :param workflow_action_type: The type it becomes.
        :return: The action, now an instance of the new type's model.
        """

        workflow_action = workflow_action.specific
        # `pre_delete` disposes a deleted action's service, but it is connected
        # to the root model and only the type's own row is deleted below.
        old_service = getattr(workflow_action, "service", None)

        workflow_action.change_polymorphic_type_to(workflow_action_type.model_class)

        allowed_values = extract_allowed(
            prepared_values, workflow_action_type.allowed_fields
        )
        for key, value in allowed_values.items():
            setattr(workflow_action, key, value)

        workflow_action.save()

        if old_service is not None:
            old_service = old_service.specific
            ServiceHandler().delete_service(old_service.get_type(), old_service)

        return workflow_action

    def order_workflow_actions(
        self,
        field: ButtonField,
        order: List[int],
        base_qs: Optional[QuerySet] = None,
    ) -> List[int]:
        """
        Assigns a new order to a button field's actions.

        :param field: The button field the actions belong to.
        :param order: The new order of the workflow actions.
        :param base_qs: A queryset with filters already applied.
        :raises WorkflowActionNotInField: When an id is not one of the field's.
        :return: The new full order.
        """

        if base_qs is None:
            base_qs = DatabaseWorkflowAction.objects.filter(field=field)

        try:
            return DatabaseWorkflowAction.order_objects(base_qs, order)
        except IdDoesNotExist as error:
            raise WorkflowActionNotInField(error.not_existing_id)

    def dispatch_workflow_action(
        self,
        workflow_action: DatabaseWorkflowAction,
        dispatch_context: "DatabaseDispatchContext",
    ) -> DispatchResult:
        """
        Dispatches a single workflow action. Permission checks and sequencing
        live in the service layer; this is the plain execution step.

        :param workflow_action: The action to dispatch.
        :param dispatch_context: The context carrying the actor and clicked row.
        :return: The result of dispatching the action.
        """

        dispatch_result = workflow_action.get_type().dispatch(
            workflow_action, dispatch_context
        )

        # Where `previous_action` keeps this result for the actions after it
        # (ADR 006 section 3).
        for data_provider in database_data_provider_type_registry.get_all():
            data_provider.post_dispatch(
                dispatch_context, workflow_action, dispatch_result
            )

        return dispatch_result
