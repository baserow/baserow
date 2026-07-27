from typing import Iterable, List, Optional, Type

from django.db.models import QuerySet

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
from baserow.core.workflow_actions.handler import WorkflowActionHandler
from baserow.core.workflow_actions.registries import WorkflowActionType


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
