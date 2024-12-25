from typing import TYPE_CHECKING, List, Optional

from django.contrib.auth.models import AbstractUser
from django.utils import translation

from baserow.contrib.builder.elements.exceptions import ElementNotInSamePage
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.operations import (
    CreateElementOperationType,
    DeleteElementOperationType,
    ListElementsPageOperationType,
    ReadElementOperationType,
    UpdateElementOperationType,
)
from baserow.contrib.builder.elements.registries import ElementType
from baserow.contrib.builder.elements.signals import (
    element_created,
    element_deleted,
    element_moved,
    element_orders_recalculated,
    element_updated,
    elements_created,
)
from baserow.contrib.builder.elements.types import (
    ElementForUpdate,
    ElementsAndWorkflowActions,
)
from baserow.contrib.builder.pages.models import Page
from baserow.core.exceptions import CannotCalculateIntermediateOrder
from baserow.core.handler import CoreHandler

if TYPE_CHECKING:
    from baserow.contrib.builder.models import Builder


class ElementService:
    def __init__(self):
        self.handler = ElementHandler()

    def get_element(self, user: AbstractUser, element_id: int) -> Element:
        """
        Returns an element instance from the database. Also checks the user permissions.

        :param user: The user trying to get the element
        :param element_id: The ID of the element
        :return: The element instance
        """

        element = self.handler.get_element(element_id)

        CoreHandler().check_permissions(
            user,
            ReadElementOperationType.type,
            workspace=element.page.builder.workspace,
            context=element,
        )

        return element

    def get_elements(self, user: AbstractUser, page: Page) -> List[Element]:
        """
        Gets all the elements of a given page visible to the given user.

        :param user: The user trying to get the elements.
        :param page: The page that holds the elements.
        :return: The elements of that page.
        """

        CoreHandler().check_permissions(
            user,
            ListElementsPageOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        user_elements = CoreHandler().filter_queryset(
            user,
            ListElementsPageOperationType.type,
            Element.objects.all(),
            workspace=page.builder.workspace,
        )

        return self.handler.get_elements(page, base_queryset=user_elements)

    def get_builder_elements(
        self, user: AbstractUser, builder: "Builder"
    ) -> List[Element]:
        """
        Gets all the elements of a given page visible to the given user.

        :param user: The user trying to get the elements.
        :param page: The page that holds the elements.
        :return: The elements of that page.
        """

        user_elements = CoreHandler().filter_queryset(
            user,
            ListElementsPageOperationType.type,
            Element.objects.all(),
            workspace=builder.workspace,
        )

        return self.handler.get_builder_elements(builder, base_queryset=user_elements)

    def create_element(
        self,
        user: AbstractUser,
        element_type: ElementType,
        page: Page,
        before: Optional[Element] = None,
        order: Optional[int] = None,
        **kwargs,
    ) -> Element:
        """
        Creates a new element for a page given the user permissions.

        :param user: The user trying to create the element.
        :param element_type: The type of the element.
        :param page: The page the element exists in.
        :param before: If set, the new element is inserted before this element.
        :param order: If set, the new element is inserted at this order ignoring before.
        :param kwargs: Additional attributes of the element.
        :return: The created element.
        """

        CoreHandler().check_permissions(
            user,
            CreateElementOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        # Check we are on the same page.
        if before and page.id != before.page_id:
            raise ElementNotInSamePage()

        try:
            with translation.override(user.profile.language):
                new_element = self.handler.create_element(
                    element_type, page, before=before, order=order, **kwargs
                )
        except CannotCalculateIntermediateOrder:
            self.recalculate_full_orders(user, page)
            # If the `find_intermediate_order` fails with a
            # `CannotCalculateIntermediateOrder`, it means that it's not possible
            # calculate an intermediate fraction. Therefore, must reset all the
            # orders of the elements (while respecting their original order),
            # so that we can then can find the fraction any many more after.
            before.refresh_from_db()
            new_element = self.handler.create_element(
                element_type, page, before=before, **kwargs
            )

        element_created.send(
            self,
            element=new_element,
            user=user,
            before_id=before.id if before else None,
        )

        return new_element

    def update_element(
        self, user: AbstractUser, element: ElementForUpdate, **kwargs
    ) -> Element:
        """
        Updates and element with values. Will also check if the values are allowed
        to be set on the element first.

        :param user: The user trying to update the element.
        :param element: The element that should be updated.
        :param values: The values that should be set on the element.
        :param kwargs: Additional attributes of the element.
        :return: The updated element.
        """

        CoreHandler().check_permissions(
            user,
            UpdateElementOperationType.type,
            workspace=element.page.builder.workspace,
            context=element,
        )

        element = self.handler.update_element(element, **kwargs)

        element_updated.send(self, element=element, user=user)

        return element

    def delete_element(self, user: AbstractUser, element: ElementForUpdate):
        """
        Deletes an element.

        :param user: The user trying to delete the element.
        :param element: The to-be-deleted element.
        """

        page = element.page

        CoreHandler().check_permissions(
            user,
            DeleteElementOperationType.type,
            workspace=element.page.builder.workspace,
            context=element,
        )

        self.handler.delete_element(element)

        element_deleted.send(self, element_id=element.id, page=page, user=user)

    def move_element(
        self,
        user: AbstractUser,
        element: ElementForUpdate,
        parent_element: Optional[Element],
        place_in_container: str,
        before: Optional[Element] = None,
    ) -> Element:
        """
        Moves an element in the page before another element. If the `before` element is
        omitted the element is moved at the end of the page.

        :param user: The user who move the element.
        :param element: The element we want to move.
        :param parent_element: The new parent element of the element.
        :param place_in_container: The new place in container of the element.
        :param before: The element before which we want to move the given element.
        :return: The element with an updated order.
        """

        CoreHandler().check_permissions(
            user,
            UpdateElementOperationType.type,
            workspace=element.page.builder.workspace,
            context=element,
        )

        # Check we are on the same page.
        if before and element.page_id != before.page_id:
            raise ElementNotInSamePage()

        try:
            element = self.handler.move_element(
                element, parent_element, place_in_container, before=before
            )
        except CannotCalculateIntermediateOrder:
            # If it's failing, we need to recalculate all orders then move again.
            self.recalculate_full_orders(user, element.page)
            # Refresh the before element as the order might have changed.
            before.refresh_from_db()
            element = self.handler.move_element(
                element, parent_element, place_in_container, before=before
            )

        element_moved.send(
            self,
            element=element,
            before=before,
            user=user,
        )

        return element

    def recalculate_full_orders(self, user: AbstractUser, page: Page):
        """
        Recalculates the order to whole numbers of all elements of the given page and
        send a signal.
        """

        self.handler.recalculate_full_orders(page)

        element_orders_recalculated.send(self, page=page)

    def duplicate_element(
        self, user: AbstractUser, element: Element
    ) -> ElementsAndWorkflowActions:
        """
        Duplicate an element in a recursive fashion. If the element has any children
        they will also be imported using the same method and so will their children
        and so on.

        :param user: The user that duplicates the element.
        :param element: The element that should be duplicated
        :return: All the elements that were created in the process
        """

        page = element.page

        CoreHandler().check_permissions(
            user,
            CreateElementOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        try:
            elements_and_workflow_actions_duplicated = self.handler.duplicate_element(
                element
            )
        except CannotCalculateIntermediateOrder:
            self.recalculate_full_orders(user, element.page)
            element.refresh_from_db()
            elements_and_workflow_actions_duplicated = self.handler.duplicate_element(
                element
            )

        elements_created.send(
            self,
            elements=elements_and_workflow_actions_duplicated["elements"],
            user=user,
            page=page,
        )

        return elements_and_workflow_actions_duplicated
