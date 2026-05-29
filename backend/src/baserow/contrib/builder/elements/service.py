from typing import TYPE_CHECKING, List

from django.contrib.auth.models import AbstractUser
from django.utils import translation

from rest_framework.exceptions import ValidationError

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
from baserow.core.graph.exceptions import GraphPointReferencePointInvalid
from baserow.core.graph.types import GraphPointPosition, GraphPointPositionType
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
            Element.objects.filter(page=page),
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
            Element.objects.filter(page__builder=builder),
            workspace=builder.workspace,
        )

        return self.handler.get_builder_elements(builder, base_queryset=user_elements)

    def _check_position(
        self,
        element_type: ElementType,
        page: Page,
        reference_element: Element | None,
        position: GraphPointPositionType,
        place_in_container: str = "",
    ):
        """
        Validates the position.
        """

        # Determine if the new element will be root-level on the page.
        # CHILD always has a parent; NORTH/SOUTH share the parent of the reference.
        if position == GraphPointPosition.CHILD:
            will_be_root = False
        elif reference_element is None:
            will_be_root = True
        else:
            will_be_root = reference_element.get_parent_point() is None

        if (
            will_be_root
            and getattr(element_type, "is_multi_page_element", False) != page.shared
        ):
            raise ValidationError(
                "This element type can't be added as root of a "
                f"{'an unshared' if element_type.is_multi_page_element else 'the shared'} "
                "page."
            )

        if reference_element is None:
            return

        if reference_element.page_id != page.id:
            raise ElementNotInSamePage(
                f"The reference element {reference_element.id} doesn't exist"
            )

        if (
            reference_element.get_type().is_container
            and position == GraphPointPosition.CHILD
        ):
            element_type.validate_place(
                page, reference_element, place_in_container, position
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
        position: GraphPointPositionType = "south",
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
        output = kwargs.pop("place_in_container", "") or ""

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

        # Confirm the position triplet is valid for this reference.
        self._check_position(element_type, page, reference_element, position, output)

        with translation.override(user.profile.language):
            new_element = self.handler.create_element(
                element_type,
                page,
                position=position,
                reference_element=reference_element,
                place_in_container=output,
                **kwargs,
            )

        if reference_element is None:
            page.get_graph().append(new_element)
        else:
            page.get_graph().insert(new_element, reference_element, position, output)

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
        Moves an element in the page at the place defined by the position triplet.

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

        # Confirm the position triplet is valid for this reference.
        self._check_position(
            element_type, target_page, reference_element, position, place_in_container
        )

        # Check if the type has any before-move requirements.
        element_type.before_move(element, reference_element, position)

        source_graph = element.page.get_graph()

        # We extract the current element position
        # to restore it if we undo the operation.
        [
            previous_reference_element_id,
            previous_position,
            previous_output,
        ] = source_graph.get_position(element)

        previous_reference_element = (
            self.handler.get_element(previous_reference_element_id)
            if previous_reference_element_id
            else None
        )

        is_cross_page_move = target_page.id != source_graph.instance.id

        source_graph.move(
            element,
            reference_element,
            position,
            place_in_container,
            target_graph=target_page.get_graph(),
        )

        if target_page.id != element.page.id:
            element.page = target_page
            element.save(update_fields=["page"])

        # Check if the type has any after-move logic. Pass source_graph so `after_move`
        # can look up children even though the graph has already been mutated.
        element_type.after_move(element, source_graph)

        if is_cross_page_move:
            # move() used keep_info=True to preserve the source-graph entry for
            # after_move traversal above. Now that after_move is done, those
            # stale entries must be removed so that the source page's graph
            # stays consistent (prevents orphaned "X": {} nodes that would
            # later break export/import or graph traversal).
            source_graph.remove_isolated_point(element)

        self.handler.invalidate_element_cache(element.page)

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

        elements_and_workflow_actions_duplicated = self.handler.duplicate_element(
            element
        )

        elements_created.send(
            self,
            elements=elements_and_workflow_actions_duplicated["elements"],
            workflow_actions=elements_and_workflow_actions_duplicated[
                "workflow_actions"
            ],
            user=user,
            page=page,
        )

        return elements_and_workflow_actions_duplicated
