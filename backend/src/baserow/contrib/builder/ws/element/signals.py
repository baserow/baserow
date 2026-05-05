from typing import List

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.builder.api.elements.serializers import ElementSerializer
from baserow.contrib.builder.elements import signals as element_signals
from baserow.contrib.builder.elements.models import Element
from baserow.contrib.builder.elements.object_scopes import BuilderElementObjectScopeType
from baserow.contrib.builder.elements.operations import (
    ListElementsPageOperationType,
    ReadElementOperationType,
)
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.object_scopes import BuilderPageObjectScopeType
from baserow.core.graph.types import GraphPointPosition
from baserow.ws.tasks import broadcast_to_permitted_users


@receiver(element_signals.element_created)
def element_created(
    sender, element: Element, user: AbstractUser, before_id=None, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            element.page.builder.workspace_id,
            ReadElementOperationType.type,
            BuilderElementObjectScopeType.type,
            element.id,
            {
                "type": "element_created",
                "element": element_type_registry.get_serializer(
                    element, ElementSerializer
                ).data,
                "before_id": before_id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(element_signals.elements_created)
def elements_created(
    sender, elements: List[Element], page: Page, user: AbstractUser, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            page.builder.workspace_id,
            ListElementsPageOperationType.type,
            BuilderPageObjectScopeType.type,
            page.id,
            {
                "type": "elements_created",
                "elements": [
                    element_type_registry.get_serializer(
                        element, ElementSerializer
                    ).data
                    for element in elements
                ],
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(element_signals.element_updated)
def element_updated(sender, element: Element, user: AbstractUser, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            element.page.builder.workspace_id,
            ReadElementOperationType.type,
            BuilderElementObjectScopeType.type,
            element.id,
            {
                "type": "element_updated",
                "element": element_type_registry.get_serializer(
                    element, ElementSerializer
                ).data,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(element_signals.element_moved)
def element_moved(
    sender,
    element: Element,
    position: GraphPointPosition,
    reference_element: Element,
    user: AbstractUser,
    **kwargs,
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            element.page.builder.workspace_id,
            ReadElementOperationType.type,
            BuilderElementObjectScopeType.type,
            element.id,
            {
                "type": "element_moved",
                "element_id": element.id,
                "position": position,
                "reference_element_id": reference_element.id
                if reference_element
                else None,
                "place_in_container": element.place_in_container,
                "page_id": element.page.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(element_signals.element_deleted)
def element_deleted(sender, page: Page, element_id: int, user: AbstractUser, **kwargs):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            page.builder.workspace_id,
            ListElementsPageOperationType.type,
            BuilderPageObjectScopeType.type,
            page.id,
            {
                "type": "element_deleted",
                "element_id": element_id,
                "page_id": page.id,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(element_signals.elements_moved)
def elements_moved(
    sender, page: Page, elements: List[Element], user: AbstractUser = None, **kwargs
):
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            page.builder.workspace_id,
            ListElementsPageOperationType.type,
            BuilderPageObjectScopeType.type,
            page.id,
            {
                "type": "elements_moved",
                "page_id": page.id,
                "elements": [
                    element_type_registry.get_serializer(
                        element, ElementSerializer
                    ).data
                    for element in elements
                ],
            },
            getattr(user, "web_socket_id", None),
        )
    )
