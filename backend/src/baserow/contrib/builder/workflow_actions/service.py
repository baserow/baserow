from typing import TYPE_CHECKING, Any, List

from django.contrib.auth.models import AbstractUser

from baserow.contrib.builder.data_sources.builder_dispatch_context import (
    BuilderDispatchContext,
)
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.exceptions import (
    BuilderWorkflowActionCannotBeDispatched,
)
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.contrib.builder.workflow_actions.models import (
    BuilderWorkflowAction,
    BuilderWorkflowServiceAction,
    WorkflowAction,
)
from baserow.contrib.builder.workflow_actions.operations import (
    CreateBuilderWorkflowActionOperationType,
    DeleteBuilderWorkflowActionOperationType,
    DispatchBuilderWorkflowActionOperationType,
    ListBuilderWorkflowActionsPageOperationType,
    OrderBuilderWorkflowActionOperationType,
    ReadBuilderWorkflowActionOperationType,
    UpdateBuilderWorkflowActionOperationType,
)
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.contrib.builder.workflow_actions.signals import (
    workflow_action_created,
    workflow_action_updated,
    workflow_actions_reordered,
)
from baserow.contrib.builder.workflow_actions.types import (
    UpdatedBuilderWorkflowAction,
)
from baserow.contrib.builder.workflow_actions.workflow_action_types import (
    BuilderWorkflowActionType,
)
from baserow.core.exceptions import PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.services.types import DispatchResult
from baserow.core.trash.handler import TrashHandler

if TYPE_CHECKING:
    from baserow.contrib.builder.models import Builder


class BuilderWorkflowActionService:
    def __init__(self):
        self.handler = BuilderWorkflowActionHandler()

    def get_workflow_action(
        self, user: AbstractUser, workflow_action_id: int
    ) -> WorkflowAction:
        """
        Returns an workflow_action instance from the database. Also checks the user
        permissions.

        :param user: The user trying to get the workflow_action
        :param workflow_action_id: The ID of the workflow_action
        :return: The workflow_action instance
        """

        workflow_action = self.handler.get_workflow_action(workflow_action_id)

        CoreHandler().check_permissions(
            user,
            ReadBuilderWorkflowActionOperationType.type,
            workspace=workflow_action.page.builder.workspace,
            context=workflow_action,
        )

        return workflow_action

    def get_workflow_actions(
        self,
        user: AbstractUser,
        page: Page,
    ) -> List[WorkflowAction]:
        """
        Gets all the workflow_actions of a given page visible to the given user.

        :param user: The user trying to get the workflow_actions.
        :param page: The page that holds the workflow_actions.
        :return: The workflow_actions of that page.
        """

        CoreHandler().check_permissions(
            user,
            ListBuilderWorkflowActionsPageOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        user_workflow_actions = CoreHandler().filter_queryset(
            user,
            ListBuilderWorkflowActionsPageOperationType.type,
            BuilderWorkflowAction.objects.filter(page=page),
            workspace=page.builder.workspace,
        )

        return self.handler.get_workflow_actions(
            page, base_queryset=user_workflow_actions
        )

    def get_builder_workflow_actions(
        self,
        user: AbstractUser,
        builder: "Builder",
    ) -> List[WorkflowAction]:
        """
        Gets all the workflow_actions of a given builder visible to the given user.

        :param user: The user trying to get the workflow_actions.
        :param builder: The builder instance that holds the workflow_actions.
        :return: The workflow_actions of that builder.
        """

        user_workflow_actions = CoreHandler().filter_queryset(
            user,
            ListBuilderWorkflowActionsPageOperationType.type,
            BuilderWorkflowAction.objects.filter(page__builder=builder),
            workspace=builder.workspace,
        )

        return self.handler.get_builder_workflow_actions(builder, user_workflow_actions)

    def create_workflow_action(
        self,
        user: AbstractUser,
        workflow_action_type: BuilderWorkflowActionType,
        page: Page,
        **kwargs,
    ) -> WorkflowAction:
        """
        Creates a new workflow_action for a page given the user permissions.

        :param user: The user trying to create the workflow_action.
        :param workflow_action_type: The type of the workflow_action.
        :param page: The page the workflow_action is associated with.
        :param kwargs: Additional attributes of the workflow_action.
        :return: The created workflow_action.
        """

        CoreHandler().check_permissions(
            user,
            CreateBuilderWorkflowActionOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        workflow_action_type.raise_if_deactivated(page.builder.workspace)

        prepared_values = workflow_action_type.prepare_values(kwargs, user)

        new_workflow_action = self.handler.create_workflow_action(
            workflow_action_type, page=page, **prepared_values
        )

        workflow_action_created.send(
            self,
            workflow_action=new_workflow_action,
            user=user,
        )

        return new_workflow_action

    def update_workflow_action(
        self, user: AbstractUser, workflow_action: WorkflowAction, **kwargs
    ) -> UpdatedBuilderWorkflowAction:
        """
        Updates and workflow_action with values. Will also check if the values are
        allowed to be set on the workflow_action first.

        :param user: The user trying to update the workflow_action.
        :param workflow_action: The workflow_action that should be updated.
        :param kwargs: Additional attributes of the workflow_action.
        :return: The updated workflow_action.
        """

        CoreHandler().check_permissions(
            user,
            UpdateBuilderWorkflowActionOperationType.type,
            workspace=workflow_action.page.builder.workspace,
            context=workflow_action,
        )

        has_type_changed = (
            "type" in kwargs and kwargs["type"] != workflow_action.get_type().type
        )

        if has_type_changed:
            workflow_action_type = builder_workflow_action_type_registry.get(
                kwargs["type"]
            )
        else:
            workflow_action_type = workflow_action.get_type()

        workflow_action_type.raise_if_deactivated(
            workflow_action.page.builder.workspace
        )

        # Capture the original values before `prepare_values` mutates the action's
        # service, so the update can be undone/redone.
        original_values = workflow_action.get_type().export_prepared_values(
            workflow_action
        )

        if has_type_changed:
            # When a workflow action's type changes, due our polymorphism, we need
            # to delete the existing action and create a new one of the new type.
            self.handler.delete_workflow_action(workflow_action)
            # We call `prepare_values` with the PATCHed payload, and then manually
            # add `page`, `element`, `order` & `event` data from the *previous*
            # workflow action as 1) they'll be the same and 2) they aren't present
            # in the payload.
            prepared_values = workflow_action_type.prepare_values(kwargs, user)
            prepared_values["page"] = workflow_action.page
            prepared_values["element"] = workflow_action.element
            prepared_values["order"] = workflow_action.order
            prepared_values["event"] = workflow_action.event
            workflow_action = self.handler.create_workflow_action(
                workflow_action_type, **prepared_values
            )
        else:
            prepared_values = workflow_action_type.prepare_values(
                kwargs, user, workflow_action
            )
            workflow_action = self.handler.update_workflow_action(
                workflow_action, **prepared_values
            )

        new_values = workflow_action.get_type().export_prepared_values(workflow_action)

        workflow_action_updated.send(self, workflow_action=workflow_action, user=user)

        return UpdatedBuilderWorkflowAction(
            workflow_action, original_values, new_values
        )

    def delete_workflow_action(
        self, user: AbstractUser, workflow_action: WorkflowAction
    ):
        """
        Deletes a workflow_action.

        :param user: The user trying to delete the workflow_action.
        :param workflow_action: The to-be-deleted workflow_action.
        """

        page = workflow_action.page

        CoreHandler().check_permissions(
            user,
            DeleteBuilderWorkflowActionOperationType.type,
            workspace=page.builder.workspace,
            context=workflow_action,
        )

        # Soft-delete (trash) the workflow action so it can be restored via undo. The
        # `workflow_action_deleted` realtime signal is emitted by the trashable item
        # type.
        builder = page.builder
        TrashHandler.trash(user, builder.workspace, builder, workflow_action)

    def order_workflow_actions(
        self,
        user: AbstractUser,
        page: Page,
        order: List[int],
        element: Element = None,
    ) -> List[int]:
        """
        Assigns a new order to the workflow actions in a builder application.

        :param user: The user trying to order the domains
        :param page: The page that the workflow actions belong to
        :param order: The new order of the workflow actions
        :param element: The element the page belongs to
        :return: The new order of the workflow actions
        """

        CoreHandler().check_permissions(
            user,
            OrderBuilderWorkflowActionOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        all_workflow_actions = BuilderWorkflowAction.objects.filter(
            page=page, element=element
        )

        user_workflow_actions = CoreHandler().filter_queryset(
            user,
            OrderBuilderWorkflowActionOperationType.type,
            all_workflow_actions,
            workspace=page.builder.workspace,
        )

        full_order = self.handler.order_workflow_actions(
            page, order, base_qs=user_workflow_actions, element=element
        )

        workflow_actions_reordered.send(
            self, page=page, element=element, order=full_order, user=user
        )

        return full_order

    def dispatch_action(
        self,
        user,
        workflow_action: BuilderWorkflowServiceAction,
        dispatch_context: BuilderDispatchContext,
    ) -> Any:
        """
        Dispatch the service related to the given workflow_action if the user
        has the permission.

        :param user: The current user.
        :param workflow_action: The workflow action's service to be dispatched.
        :param dispatch_context: The context used for the dispatch.
        :return: The result of dispatching the action mapped by workflow_action ID.
        :raises BuilderWorkflowActionCannotBeDispatched: If a `workflow_action` is
            provided that does not implement `BuilderWorkflowServiceAction`.
        """

        if not issubclass(workflow_action.__class__, BuilderWorkflowServiceAction):
            raise BuilderWorkflowActionCannotBeDispatched(
                f"WorkflowAction {workflow_action.id} is not meant to be dispatched."
            )

        CoreHandler().check_permissions(
            user,
            DispatchBuilderWorkflowActionOperationType.type,
            workspace=workflow_action.page.builder.workspace,
            context=workflow_action,
        )

        workflow_action.get_type().raise_if_deactivated(
            workflow_action.page.builder.workspace
        )

        update_sample_data = self._can_update_sample_data(
            user, workflow_action, dispatch_context
        )
        if update_sample_data:
            dispatch_context.use_sample_data = True
            dispatch_context.update_sample_data_for = [workflow_action.service.specific]

        try:
            result = self.handler.dispatch_workflow_action(
                workflow_action, dispatch_context
            )
        except Exception:
            if update_sample_data:
                workflow_action_updated.send(
                    self, workflow_action=workflow_action, user=user
                )
            raise

        if update_sample_data:
            workflow_action_updated.send(
                self, workflow_action=workflow_action, user=user
            )

        # Remove unfiltered fields
        allowed_field_names = dispatch_context.public_allowed_properties.get(
            "external", {}
        ).get(workflow_action.service.id, [])

        data = workflow_action.service.get_type().sanitize_result(
            workflow_action.service.specific, result.data, allowed_field_names
        )

        return DispatchResult(
            data=data,
            status=result.status,
        )

    def _can_update_sample_data(
        self,
        user,
        workflow_action: BuilderWorkflowServiceAction,
        dispatch_context: BuilderDispatchContext,
    ) -> bool:
        """
        Returns whether this dispatch may persist the service sample data.

        Only authenticated dispatches against draft builders with workflow-action
        update permission are allowed to refresh sample data. Published builder
        copies must not mutate their service sample data.
        """

        builder = workflow_action.page.builder

        if builder.is_published:
            return False

        try:
            CoreHandler().check_permissions(
                user,
                UpdateBuilderWorkflowActionOperationType.type,
                workspace=workflow_action.page.builder.workspace,
                context=workflow_action,
            )
        except PermissionException:
            return False

        return True
