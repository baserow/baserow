from typing import TYPE_CHECKING, List

from django.contrib.auth.models import AbstractUser
from django.utils import translation

from baserow.contrib.builder.elements.exceptions import (
    ElementDoesNotExist,
    ElementNotInSamePage,
)
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
    ElementMove,
    ElementsAndWorkflowActions,
)
from baserow.contrib.builder.pages.exceptions import PageNotInBuilder
from baserow.contrib.builder.pages.models import Page
from baserow.core.exceptions import CannotCalculateIntermediateOrder
from baserow.core.graph.exceptions import GraphPointReferencePointInvalid
from baserow.core.graph.types import GraphPointPositionType
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

    def _check_position(
        self,
        page: Page,
        reference_element: Element | None,
        position: GraphPointPositionType,
    ):
        """
        Validates the position.
        """

        if reference_element is None:
            return

        if reference_element.page_id != page.id:
            raise ElementNotInSamePage(
                f"The reference element {reference_element.id} doesn't exist"
            )

        if position == "child" and not reference_element.get_type().is_container:
            raise GraphPointReferencePointInvalid(
                f"The reference node {reference_element.id} can't have child"
            )

    def create_element(
        self,
        user: AbstractUser,
        element_type: ElementType,
        page: Page,
        reference_element_id: int | None = None,
        position: GraphPointPositionType = "south",  # south, child
        **kwargs,
    ) -> Element:
        """
        Creates a new element for a page given the user permissions.

        :param user: The user trying to create the element.
        :param element_type: The type of the element.
        :param page: The page the element exists in.
        :param reference_element_id: The element reference element for the position.
        :param position: The position relative to the reference element.
        :param kwargs: Additional attributes of the element.
        :return: The created element.
        """

        CoreHandler().check_permissions(
            user,
            CreateElementOperationType.type,
            workspace=page.builder.workspace,
            context=page,
        )

        # We currently only support one value for the output, other than
        # a blank string, and that's the place inside a container.
        instance_output = kwargs.pop("place_in_container", "")

        try:
            reference_element = (
                self.handler.get_element(reference_element_id)
                if reference_element_id
                else None
            )
        except ElementDoesNotExist as e:
            raise GraphPointReferencePointInvalid(
                f"The reference element {reference_element_id} doesn't exist"
            ) from e

        # Verify the combination of the reference element, and the position.
        self._check_position(page, reference_element, position)

        try:
            with translation.override(user.profile.language):
                new_element = self.handler.create_element(element_type, page, **kwargs)
        except CannotCalculateIntermediateOrder:
            self.recalculate_full_orders(user, page)
            # If the `find_intermediate_order` fails with a
            # `CannotCalculateIntermediateOrder`, it means that it's not possible
            # calculate an intermediate fraction. Therefore, must reset all the
            # orders of the elements (while respecting their original order),
            # so that we can then can find the fraction any many more after.
            new_element = self.handler.create_element(element_type, page, **kwargs)

        page.get_graph().insert(
            new_element, reference_element, position, instance_output
        )

        element_created.send(
            self,
            element=new_element,
            user=user,
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
        target_page: Page,
        element: ElementForUpdate,
        place_in_container: str,
        reference_element_id: int | None,
        position: GraphPointPositionType,
    ) -> ElementMove:
        """
        Moves an element in the page before another element. If the `before` element is
        omitted the element is moved at the end of the page.

        :param user: The user who is moving the element.
        :param target_page: The page this element will move to.
        :param element: The element to move.
        :param place_in_container: The new place in container of the element.
        :param reference_element_id: The element the new position is relative to.
        :param position: The new position relative to the reference element.
        :return: The `ElementMove` object, containing our previous position/reference.
        """

        element_type = element.get_type()

        CoreHandler().check_permissions(
            user,
            UpdateElementOperationType.type,
            workspace=element.page.builder.workspace,
            context=element,
        )

        try:
            reference_element = (
                self.handler.get_element(reference_element_id)
                if reference_element_id
                else None
            )
        except ElementDoesNotExist as e:
            raise GraphPointReferencePointInvalid(
                f"The reference element {reference_element_id} doesn't exist"
            ) from e

        # Check we are on the same builder.
        if target_page.builder != element.page.builder:
            raise PageNotInBuilder()

        # Validate the reference element's place (e.g. if a `place_in_container` is
        # provided that is too large for the number this container supports), then
        # check the position/reference element combination is valid.
        element_type.validate_place(target_page, reference_element, place_in_container)
        self._check_position(target_page, reference_element, position)

        # Check if the type has any before-move requirements.
        element_type.before_move(element, reference_element, position)

        # We extract the current element position
        # to restore it if we undo the operation.
        [
            previous_reference_element_id,
            previous_position,
            previous_output,
        ] = target_page.get_graph().get_position(element)

        previous_reference_element = (
            self.handler.get_element(previous_reference_element_id)
            if previous_reference_element_id
            else None
        )

        target_page.get_graph().move(
            element, reference_element, position, place_in_container
        )

        element_moved.send(
            self,
            element=element,
            position=position,
            reference_element=reference_element,
            user=user,
        )

        return ElementMove(
            element=element,
            previous_output=previous_output,
            previous_position=previous_position,
            previous_reference_element=previous_reference_element,
        )

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
