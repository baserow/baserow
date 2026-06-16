from typing import List

from django.contrib.auth.models import AbstractUser
from django.db import transaction
from django.dispatch import receiver

from baserow.contrib.builder.api.elements.serializers import ElementSerializer
from baserow.contrib.builder.api.workflow_actions.serializers import (
    BuilderWorkflowActionSerializer,
)
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
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.core.db import specific_iterator
from baserow.ws.tasks import broadcast_to_permitted_users


@receiver(element_signals.element_created)
def element_created(
    sender, element: Element, user: AbstractUser, before_id=None, **kwargs
):
    # Read through the handler so we always get the authoritative in-memory
    # graph, regardless of which page instance the handler is bound to.
    graph = element.page.get_graph().graph
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
                "graph": graph,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(element_signals.elements_created)
def elements_created(
    sender,
    elements: List[Element],
    page: Page,
    user: AbstractUser,
    workflow_actions=None,
    **kwargs,
):
    graph = page.get_graph().graph
    serialized_workflow_actions = [
        builder_workflow_action_type_registry.get_serializer(
            wa, BuilderWorkflowActionSerializer
        ).data
        for wa in (workflow_actions or [])
    ]
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            page.builder.workspace_id,
            ListElementsPageOperationType.type,
            BuilderPageObjectScopeType.type,
            page.id,
            {
                "type": "elements_created",
                "page_id": page.id,
                "elements": [
                    element_type_registry.get_serializer(
                        element, ElementSerializer
                    ).data
                    for element in elements
                ],
                "workflow_actions": serialized_workflow_actions,
                "graph": graph,
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
    user: AbstractUser,
    source_page: Page = None,
    **kwargs,
):
    target_page = element.page
    target_graph = target_page.get_graph()

    payload = {
        "type": "element_moved",
        "page_id": target_page.id,
        "graph": target_graph.graph,
    }

    # On a cross-page move the element (and any descendants that travelled with
    # it) leaves the source page and joins the target page. A same-page move only
    # reorders the graph, so the receiving client already has every element. For
    # a cross-page move we additionally send the source page's refreshed graph and
    # the serialized moved elements so clients can relocate them: remove them from
    # the source page (if loaded) and add them to the target page.
    is_cross_page = source_page is not None and source_page.id != target_page.id
    if is_cross_page:
        moved_elements = [
            element,
            *(d.specific for d in target_graph.get_descendants(element)),
        ]
        # A workflow action's page follows its element (see ElementType.wrap_move),
        # so they travel with the moved subtree. Send them too, so clients relocate
        # the action records from the source page to the target page rather than
        # leaving them stranded (which makes them appear disassociated).
        moved_workflow_actions = specific_iterator(
            BuilderWorkflowAction.objects.filter(
                element_id__in=[e.id for e in moved_elements]
            )
        )
        payload["source_page_id"] = source_page.id
        payload["source_graph"] = source_page.get_graph().graph
        payload["elements"] = [
            element_type_registry.get_serializer(e, ElementSerializer).data
            for e in moved_elements
        ]
        payload["workflow_actions"] = [
            builder_workflow_action_type_registry.get_serializer(
                wa, BuilderWorkflowActionSerializer
            ).data
            for wa in moved_workflow_actions
        ]

    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            target_page.builder.workspace_id,
            ReadElementOperationType.type,
            BuilderElementObjectScopeType.type,
            element.id,
            payload,
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(element_signals.element_deleted)
def element_deleted(
    sender,
    page: Page,
    element_id: int,
    user: AbstractUser,
    descendant_ids: List[int] = None,
    **kwargs,
):
    # Send the relinked graph so other clients re-stitch the page (a deleted
    # element's siblings/children would otherwise be orphaned), and the full set
    # of deleted ids so they remove the whole subtree's records.
    graph = page.get_graph().graph
    element_ids = [element_id, *(descendant_ids or [])]
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            page.builder.workspace_id,
            ListElementsPageOperationType.type,
            BuilderPageObjectScopeType.type,
            page.id,
            {
                "type": "element_deleted",
                "element_id": element_id,
                "element_ids": element_ids,
                "page_id": page.id,
                "graph": graph,
            },
            getattr(user, "web_socket_id", None),
        )
    )


@receiver(element_signals.elements_moved)
def elements_moved(
    sender, page: Page, elements: List[Element], user: AbstractUser = None, **kwargs
):
    graph = page.get_graph().graph
    transaction.on_commit(
        lambda: broadcast_to_permitted_users.delay(
            page.builder.workspace_id,
            ListElementsPageOperationType.type,
            BuilderPageObjectScopeType.type,
            page.id,
            {
                "type": "elements_moved",
                "page_id": page.id,
                "graph": graph,
            },
            getattr(user, "web_socket_id", None),
        )
    )
