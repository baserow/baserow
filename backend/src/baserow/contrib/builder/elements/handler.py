from collections import defaultdict
from typing import (
    Any,
    Callable,
    Dict,
    Iterable,
    List,
    Optional,
    Tuple,
    Type,
    Union,
    cast,
)
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db.models import QuerySet

from baserow.contrib.builder.elements.exceptions import (
    ElementDoesNotExist,
    ElementNotInSamePage,
    ElementTypeDeactivated,
)
from baserow.contrib.builder.elements.models import ContainerElement, Element
from baserow.contrib.builder.elements.registries import (
    ElementType,
    ElementTypeSubClass,
    element_type_registry,
)
from baserow.contrib.builder.elements.types import (
    ElementForUpdate,
    ElementsAndWorkflowActions,
)
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.core.db import specific_iterator
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.storage import ExportZipFile
from baserow.core.utils import MirrorDict, extract_allowed

old_element_type_map = {"dropdown": "choice"}


class ElementHandler:
    allowed_fields_create = [
        "parent_element_id",
        "place_in_container",
        "visibility",
        "visibility_condition",
        "css_classes",
        "styles",
        "style_border_top_color",
        "style_border_top_size",
        "style_padding_top",
        "style_margin_top",
        "style_border_bottom_color",
        "style_border_bottom_size",
        "style_padding_bottom",
        "style_margin_bottom",
        "style_border_left_color",
        "style_border_left_size",
        "style_padding_left",
        "style_margin_left",
        "style_border_right_color",
        "style_border_right_size",
        "style_padding_right",
        "style_margin_right",
        "style_background_radius",
        "style_border_radius",
        "style_background",
        "style_background_color",
        "style_background_file",
        "style_background_mode",
        "style_width",
        "style_width_child",
    ]

    allowed_fields_update = [
        "parent_element_id",
        "place_in_container",
        "css_classes",
        "visibility",
        "visibility_condition",
        "styles",
        "style_border_top_color",
        "style_border_top_size",
        "style_padding_top",
        "style_margin_top",
        "style_border_bottom_color",
        "style_border_bottom_size",
        "style_padding_bottom",
        "style_margin_bottom",
        "style_border_left_color",
        "style_border_left_size",
        "style_padding_left",
        "style_margin_left",
        "style_border_right_color",
        "style_border_right_size",
        "style_padding_right",
        "style_margin_right",
        "style_background_radius",
        "style_border_radius",
        "style_background",
        "style_background_color",
        "style_background_file",
        "style_background_mode",
        "style_width",
        "style_width_child",
        "role_type",
        "roles",
    ]

    def get_element(
        self, element_id: int, base_queryset: Optional[QuerySet] = None
    ) -> Element:
        """
        Returns an element instance from the database.

        :param element_id: The ID of the element.
        :param base_queryset: The base queryset to use to build the query.
        :raises ElementDoesNotExist: If the element can't be found.
        :return: The element instance.
        """

        queryset = base_queryset if base_queryset is not None else Element.objects.all()

        try:
            element = (
                queryset.select_related("page__builder__workspace")
                .get(id=element_id)
                .specific
            )
        except Element.DoesNotExist:
            raise ElementDoesNotExist()

        return element

    def get_element_property_options(
        self, element: Element
    ) -> Dict[str, Dict[str, bool]]:
        """
        Return a dict where keys are the schema_property (e.g. "field_1") for
        every property option if the element supports it. The values are the
        searchable, sortable, filterable values.
        """

        return {
            po.schema_property: {
                "filterable": po.filterable,
                "sortable": po.sortable,
                "searchable": po.searchable,
            }
            for po in element.property_options.all()
        }

    def get_ancestors(
        self,
        element_id: int,
        page: Page,
        use_element_cache: bool = True,
        predicate: Optional[Callable[[Element], bool]] = None,
    ) -> List[Element]:
        """
        Returns a list of all the ancestors of the given element. The ancestry
        results are cached in the dispatch context to avoid multiple queries in
        the same HTTP request.

        :param element_id: The ID of the element.
        :param page: The page that holds the elements.
        :param use_element_cache: Whether to use the cached elements on the page or not.
        :param predicate: An optional predicate to filter the ancestors.
        :return: A list of the ancestors of the given element.
        """

        elements = self.get_elements(page, use_cache=use_element_cache)
        grouped_elements = {element.id: element for element in elements}
        element = grouped_elements[element_id]

        ancestry = []
        while element.parent_element_id is not None:
            element = grouped_elements[element.parent_element_id]
            if predicate is None or (
                isinstance(predicate, Callable) and predicate(element)
            ):
                ancestry.append(element)

        return ancestry

    def get_first_ancestor_of_type(
        self,
        element_id: int,
        target_type: Type[ElementTypeSubClass],
    ) -> Optional[Element]:
        """
        Returns the first ancestor of the given type belonging to this element.

        :param element_id: The ID of the element.
        :param target_type: The type of the element to find.
        :return: The first ancestor of the given type or None if not found.
        """

        element = ElementHandler().get_element(element_id)
        if isinstance(element.get_type(), target_type):
            return element

        for ancestor in self.get_ancestors(element_id, element.page):
            if isinstance(ancestor.get_type(), target_type):
                return ancestor

    def get_element_for_update(
        self, element_id: int, base_queryset: Optional[QuerySet] = None
    ) -> ElementForUpdate:
        """
        Returns an element instance from the database that can be safely updated.

        :param element_id: The ID of the element.
        :param base_queryset: The base queryset to use to build the query.
        :raises ElementDoesNotExist: If the element can't be found.
        :return: The element instance.
        """

        queryset = base_queryset if base_queryset is not None else Element.objects.all()

        queryset = queryset.select_for_update(of=("self",))

        return self.get_element(
            element_id,
            base_queryset=queryset,
        )

    def _query_elements(self, base_queryset: QuerySet, specific=True):
        """
        Query elements from the base queryset.

        :param base_queryset: The base QuerySet to query from.
        :param specific: A boolean flag to determine if a specific instances should
          be returned.
        :return: The queried elements based on the specified conditions.
        """

        if specific:
            elements = specific_iterator(
                base_queryset,
                per_content_type_queryset_hook=(
                    lambda element, queryset: element_type_registry.get_by_model(
                        element
                    ).enhance_queryset(queryset)
                ),
            )
        else:
            elements = base_queryset

        return elements

    def get_elements(
        self,
        page: Page,
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
        use_cache: bool = True,
    ) -> Union[QuerySet[Element], Iterable[Element]]:
        """
        Gets all the specific elements of a given page.

        :param page: The page that holds the elements.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Whether to return the generic elements or the specific
            instances.
        :param use_cache: Whether to use the cached elements on the page or not.
        :return: The elements of that page.
        """

        # Our cache key varies if we're using specific or generic elements.
        cache_key = "_page_elements" if not specific else "_page_elements_specific"

        # If a `base_queryset` is given, we can't use caching, clear
        # both cache keys in case the specific argument has changed.
        if base_queryset is not None:
            use_cache = False
            setattr(page, "_page_elements", None)
            setattr(page, "_page_elements_specific", None)

        elements_cache = getattr(page, cache_key, None)
        if use_cache and elements_cache is not None:
            return elements_cache

        queryset = base_queryset if base_queryset is not None else Element.objects.all()

        queryset = queryset.filter(page=page)

        elements = self._query_elements(queryset, specific=specific)

        if use_cache:
            setattr(page, cache_key, list(elements))

        return elements

    def get_builder_elements(
        self,
        builder: List[Page],
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
    ) -> Union[QuerySet[Element], Iterable[Element]]:
        """
        Gets all the elements of a given builder.

        :param builder: The builder that holds the pages that hold the elements.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Whether to return the generic elements or the specific
            instances.
        :return: The elements of that builder.
        """

        queryset = base_queryset if base_queryset is not None else Element.objects.all()

        queryset = queryset.filter(page__builder=builder)

        elements = self._query_elements(queryset, specific=specific)

        return elements

    def create_element(
        self,
        element_type: ElementType,
        page: Page,
        before: Optional[Element] = None,
        **kwargs,
    ) -> Element:
        """
        Creates a new element for a page.

        :param element_type: The type of the element.
        :param page: The page the element exists in.
        :param before: If provided and no order is provided, will place the new element
            before the given element.
        :param kwargs: Additional attributes of the element.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the element of the page must be
            recalculated in this case before calling this method again.
        :return: The created element.
        """

        if element_type.is_deactivated(page.builder.workspace):
            raise ElementTypeDeactivated()

        parent_element_id = kwargs.get("parent_element_id", None)
        place_in_container = kwargs.get("place_in_container", None)

        if before:
            order = Element.get_unique_order_before_element(
                before, parent_element_id, place_in_container
            )
        else:
            order = Element.get_last_order(page, parent_element_id, place_in_container)

        allowed_values = extract_allowed(
            kwargs, self.allowed_fields_create + element_type.allowed_fields
        )

        allowed_values["page"] = page
        allowed_values = element_type.prepare_value_for_db(allowed_values)

        model_class = cast(Element, element_type.model_class)

        element = model_class(order=order, **allowed_values)
        element.save()

        element_type.after_create(element, kwargs)

        return element

    def delete_element(self, element: Element):
        """
        Deletes an element.

        :param element: The to-be-deleted element.
        """

        element.get_type().before_delete(element)

        element.delete()

    def update_element(self, element: ElementForUpdate, **kwargs) -> Element:
        """
        Updates and element with values. Will also check if the values are allowed
        to be set on the element first.

        :param element: The element that should be updated.
        :param kwargs: The values that should be set on the element.
        :return: The updated element.
        """

        allowed_updates = extract_allowed(
            kwargs, self.allowed_fields_update + element.get_type().allowed_fields
        )

        allowed_updates = element.get_type().prepare_value_for_db(
            allowed_updates, instance=element
        )

        # Responsible for tracking the fields which changed in this update.
        # This will be passed to `element_type.after_update` so that granular
        # decisions can be made if certain field values changed.
        element_changes: Dict[str, Tuple] = {}

        for key, new_value in allowed_updates.items():
            prev_value = getattr(element, key)
            if prev_value != new_value:
                element_changes[key] = (prev_value, new_value)
            setattr(element, key, new_value)

        element.save()

        element.get_type().after_update(element, kwargs, element_changes)

        return element

    def move_element(
        self,
        element: ElementForUpdate,
        parent_element: Optional[Element],
        place_in_container: str,
        before: Optional[Element] = None,
    ) -> Element:
        """
        Moves the given element before the specified `before` element in the same page.

        :param element: The element to move.
        :param before: The element before which to move the `element`. If before is not
            specified, the element is moved at the end of the list.
        :param parent_element: The new parent element of the element.
        :param place_in_container: The new place in container of the element.
        :raises CannotCalculateIntermediateOrder: If it's not possible to find an
            intermediate order. The full order of the element of the page must be
            recalculated in this case before calling this method again.
        :return: The moved element.
        """

        parent_element_id = getattr(parent_element, "id", None)

        if parent_element is not None and place_in_container is not None:
            parent_element = parent_element.specific
            parent_element_type = element_type_registry.get_by_model(parent_element)
            parent_element_type.validate_place_in_container(
                place_in_container, parent_element
            )

        if before:
            element.order = Element.get_unique_order_before_element(
                before, parent_element_id, place_in_container
            )
        else:
            element.order = Element.get_last_order(
                element.page, parent_element_id, place_in_container
            )

        element.parent_element = parent_element
        element.place_in_container = place_in_container

        element.save()

        return element

    def order_elements(self, page: Page, order: List[int], base_qs=None) -> List[int]:
        """
        Assigns a new order to the elements on a page.
        You can provide a base_qs for pre-filter the elements affected by this change

        :param page: The page that the elements belong to
        :param order: The new order of the elements
        :param base_qs: A QS that can have filters already applied
        :raises ElementNotInSamePage: If the element is not part of the provided page
        :return: The new order of the elements
        """

        if base_qs is None:
            base_qs = Element.objects.filter(page=page)

        try:
            full_order = Element.order_objects(base_qs, order)
        except IdDoesNotExist:
            raise ElementNotInSamePage()

        return full_order

    def before_places_in_container_removed(
        self, container_element: ContainerElement, places: List[str]
    ) -> List[Element]:
        """
        This should be called before places in a container have been removed to make
        sure that all the elements that used to be in the removed containers are moved
        somewhere else.

        :param container_element: The container element affected
        :param places: The places that were removed
        :return: The elements that received a new order
        """

        element_type = element_type_registry.get_by_model(container_element)

        elements_being_moved = Element.objects.filter(
            parent_element=container_element,
            place_in_container__in=places,
        )

        element_count = elements_being_moved.count()

        if element_count == 0:
            return []

        new_place_in_container = element_type.get_new_place_in_container(
            container_element, places
        )

        new_order_values = Element.get_last_orders(
            container_element.page,
            container_element.id,
            new_place_in_container,
            amount=element_count,
        )

        elements_being_moved = element_type.apply_order_by_children(
            elements_being_moved
        )
        elements_being_moved = list(elements_being_moved)

        to_update = []
        for element in elements_being_moved:
            # Add order values in the same order
            element.order = new_order_values.pop(0)
            element.place_in_container = new_place_in_container
            to_update.append(element)

        Element.objects.bulk_update(to_update, ["order", "place_in_container"])

        return elements_being_moved

    def recalculate_full_orders(
        self,
        page: Page,
    ):
        """
        Recalculates the order to whole numbers of all elements of the given page.
        """

        Element.recalculate_full_orders(queryset=Element.objects.filter(page=page))

    def get_element_workflow_actions(
        self, element: Element
    ) -> Iterable[BuilderWorkflowAction]:
        """
        Get all the workflow actions that belong to an element
        :param element: The element associated with the workflow actions
        :return: All the workflow actions associated
        """

        return specific_iterator(element.builderworkflowaction_set.all())

    def duplicate_element(self, element: Element) -> ElementsAndWorkflowActions:
        """
        Duplicate an element in a recursive fashion. If the element has any children
        they will also be imported using the same method and so will their children
        and so on.

        :param element: The element that should be duplicated
        :return: All the elements that were created in the process
        """

        # We are just creating new elements here so other data id should remain
        id_mapping = defaultdict(lambda: MirrorDict())

        return self._duplicate_element_recursive(element, id_mapping)

    def _duplicate_element_recursive(
        self, element: Element, id_mapping
    ) -> ElementsAndWorkflowActions:
        """
        Duplicates an element and all of its children.

        This method is separate from `duplicate_element` since it has additional params
        only required for the recursive calls.

        :param element: The element being duplicated
        :param id_mapping: The id_mapping dict used for export/import process
        :return: A list of duplicated elements
        """

        element_type = element_type_registry.get_by_model(element)

        serialized = element_type.export_serialized(element)

        next_element = (
            element.page.element_set.filter(
                parent_element_id=element.parent_element_id,
                place_in_container=element.place_in_container,
                order__gt=element.order,
            )
            .exclude(id=element.id)
            .first()
        )

        if next_element:
            # The duplicated element will be inserted right after the current one
            serialized["order"] = Element.get_unique_order_before_element(
                next_element,
                element.parent_element_id,
                element.place_in_container,
            )
        else:
            # The duplicated element will be inserted at the end of the page
            serialized["order"] = Element.get_last_order(
                element.page,
                element.parent_element_id,
                element.place_in_container,
            )

        element_duplicated = element_type.import_serialized(
            element.page, serialized, id_mapping
        )

        workflow_actions_duplicated = self._duplicate_workflow_actions_of_element(
            element, id_mapping
        )

        elements_and_workflow_actions_duplicated = {
            "elements": [element_duplicated],
            "workflow_actions": workflow_actions_duplicated,
        }

        for child in element.children.all():
            children_duplicated = self._duplicate_element_recursive(
                child.specific, id_mapping
            )
            elements_and_workflow_actions_duplicated["elements"] += children_duplicated[
                "elements"
            ]
            elements_and_workflow_actions_duplicated[
                "workflow_actions"
            ] += children_duplicated["workflow_actions"]

        return elements_and_workflow_actions_duplicated

    def _duplicate_workflow_actions_of_element(
        self,
        element: Element,
        id_mapping: Dict[str, Dict[int, int]],
    ) -> List[BuilderWorkflowAction]:
        """
        This helper function duplicates all the workflow actions associated with the
        element.

        :param element: The original element
        :param element_duplicated: The duplicated reference of the original element
        """

        workflow_actions_duplicated = []

        for workflow_action in self.get_element_workflow_actions(element):
            workflow_action_type = builder_workflow_action_type_registry.get_by_model(
                workflow_action
            )
            workflow_action_serialized = workflow_action_type.export_serialized(
                workflow_action
            )
            workflow_action_duplicated = workflow_action_type.import_serialized(
                element.page, workflow_action_serialized, id_mapping
            )

            workflow_actions_duplicated.append(workflow_action_duplicated)

        return workflow_actions_duplicated

    def export_element(
        self,
        element: Element,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
    ):
        """
        Serializes the given element.

        :param element: The instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :return: The serialized version.
        """

        return element.get_type().export_serialized(
            element, files_zip=files_zip, storage=storage, cache=cache
        )

    def get_import_context_addition(
        self,
        element_id: int,
        element_map: Dict[int, Element] = None,
    ) -> Dict[str, Any]:
        """
        Generates and return the import context for the given element and all its
        ancestors. This import context needs to be injected into all imported objects
        related to this element such as child elements, collection fields or workflow
        actions.

        :param element_id: The element_id to compute the context for.
        :param element_map: An optional map of already loaded elements to improve
          performances.
        :return: An object that can be used as import context.
        """

        if not element_id:
            return {}

        if not element_map:
            element_map = {}

        if element_id in element_map:
            current_element = element_map[element_id]
        else:
            # Fetch the element if we have no cache
            current_element = self.get_element(element_id)

        return self.get_import_context_addition(
            current_element.parent_element_id, element_map
        ) | current_element.get_type().import_context_addition(current_element)

    def import_element(
        self,
        page: Page,
        serialized_element: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
        **kwargs,
    ) -> Element:
        """
        Creates an instance using the serialized version previously exported with
        `.export_element`.

        :param page: The page instance the new element should belong to.
        :param serialized_element: The serialized version of the element.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :return: the newly created instance.
        """

        if "builder_page_elements" not in id_mapping:
            id_mapping["builder_page_elements"] = {}

        element_type = element_type_registry.get(serialized_element["type"])

        if element_type in old_element_type_map:
            # We met an old element type name. Let's migrate it.
            element_type = old_element_type_map[element_type]

        created_instance = element_type.import_serialized(
            page,
            serialized_element,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        id_mapping["builder_page_elements"][
            serialized_element["id"]
        ] = created_instance.id

        return created_instance
