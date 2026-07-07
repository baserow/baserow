from collections import defaultdict
from copy import deepcopy
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
from django.db import transaction
from django.db.models import QuerySet

from baserow.contrib.builder.elements.exceptions import (
    ElementDoesNotExist,
    ElementTypeDeactivated,
)
from baserow.contrib.builder.elements.models import ContainerElement, Element
from baserow.contrib.builder.elements.permission_manager import (
    ElementVisibilityPermissionManager,
)
from baserow.contrib.builder.elements.registries import (
    ElementType,
    ElementTypeSubClass,
    element_type_registry,
)
from baserow.contrib.builder.elements.types import (
    ElementForUpdate,
    ElementsAndWorkflowActions,
)
from baserow.contrib.builder.formula_importer import import_formula
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.models import BuilderWorkflowAction
from baserow.contrib.builder.workflow_actions.registries import (
    builder_workflow_action_type_registry,
)
from baserow.core.cache import local_cache
from baserow.core.db import specific_iterator
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.graph.types import GraphPointPosition, GraphPointPositionType
from baserow.core.storage import ExportZipFile
from baserow.core.utils import MirrorDict, extract_allowed

old_element_type_map = {"dropdown": "choice"}

DeferredImportCallback = Callable[[Element, Dict[str, Any], Dict[str, Any]], None]


class ElementHandler:
    allowed_fields_create = [
        "visibility",
        "visibility_condition",
        "role_type",
        "roles",
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
        element: Element,
        page: Page,
        use_element_cache: bool = True,
        predicate: Optional[Callable[[Element], bool]] = None,
    ) -> List[Element]:
        """
        Returns a list of all the ancestors of the given element. The ancestry
        results are cached in the dispatch context to avoid multiple queries in
        the same HTTP request.

        :param element: The element we want to query.
        :param page: The page that holds the elements.
        :param use_element_cache: Whether to use the cached elements on the page or not.
        :param predicate: An optional predicate to filter the ancestors.
        :return: A list of the ancestors of the given element.
        """

        elements = self.get_elements(page, use_cache=use_element_cache)
        grouped_elements = {}
        for element in elements:
            # Pre-populate the page relation so that parent_element_id lookups
            # (which call _get_graph() → self.page) don't trigger extra queries.
            element.page = page
            grouped_elements[element.id] = element
        element = grouped_elements[element.id]

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
        element: Element,
        target_type: Type[ElementTypeSubClass],
    ) -> Optional[Element]:
        """
        Returns the first ancestor of the given type belonging to this element.

        :param element: The element we want to query.
        :param target_type: The type of the element to find.
        :return: The first ancestor of the given type or None if not found.
        """

        if isinstance(element.get_type(), target_type):
            return element

        for ancestor in self.get_ancestors(element, element.page):
            if isinstance(ancestor.get_type(), target_type):
                return ancestor

        return None

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

    def _get_elements_cache_key(self, page: Page, specific: bool) -> str:
        return f"ab_get_{page.id}_elements_{specific}"

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

        def _get_elements(base_queryset=base_queryset):
            if base_queryset is None:
                base_queryset = Element.objects.all()

            queryset = base_queryset.filter(page=page)
            return self._query_elements(queryset, specific=specific)

        if use_cache and base_queryset is None:
            return local_cache.get(
                self._get_elements_cache_key(page, specific),
                _get_elements,
            )
        return _get_elements()

    def heal_orphan_elements(self, page: Page) -> Dict[str, Any]:
        """
        Reconcile `page.graph` with the elements that actually exist in the
        database, repairing drift that can appear during a non-zero-downtime deploy
        when older code mutates element rows without touching the graph. Keeping the
        graph the single source of truth means downstream operations (move, delete,
        …) never have to special-case a missing or dangling graph entry.

        Two kinds of drift are reconciled:

        - "orphans": rows present in the DB but absent from the graph (e.g. created
          by old code). They are inserted where a newly added element would land:

          - Unshared page: appended to the end of the page's root chain.
          - Shared page: appended to the end of the first shared element (the
            Header/Footer container at the root of the shared page).

        - "stale points": ids still referenced by the graph whose row no longer
          exists (e.g. hard-deleted by old code). They are spliced out via
          `prune_points` so a traversal can never resolve a missing point (which
          would otherwise raise and 500 the editor's element list).

        :param page: The page whose graph should be reconciled.
        :return: A graph "patch" — the top-level graph entries that changed, keyed by
            point id, each holding its full new value. Empty when nothing changed.
            Because the graph is a flat dict, a client can apply it with a shallow
            merge (`{...graph, ...patch}`). Note a pruned stale key is not in the
            patch (a shallow merge can't express a deletion), but its now-relinked
            predecessor is, so the stale key is left unreferenced — harmless, and the
            client drops it on the next full graph sync.
        """

        root_key = page.get_graph().GRAPH_ROOT_KEY

        def compute_drift(graph) -> tuple[set, set]:
            graph_ids = {int(k) for k in graph if k != root_key}
            db_ids = set(Element.objects.filter(page=page).values_list("id", flat=True))
            # (orphans missing from the graph, stale points missing from the DB).
            return db_ids - graph_ids, graph_ids - db_ids

        # Fast path: nothing to reconcile (the steady state). Avoid locking/writes.
        orphan_ids, stale_ids = compute_drift(page.get_graph().graph)
        if not orphan_ids and not stale_ids:
            return {}

        # Re-check under a row lock so concurrent reads can't race on the same graph.
        with transaction.atomic():
            locked_page = Page.objects.select_for_update().get(id=page.id)
            graph_handler = locked_page.get_graph()
            orphan_ids, stale_ids = compute_drift(graph_handler.graph)
            if not orphan_ids and not stale_ids:
                return {}

            # Snapshot before mutating so we can return only what changed.
            before = deepcopy(graph_handler.graph)

            # Prune stale points first so orphan placement (which traverses the
            # graph, e.g. append → get_last_position) can't walk into a missing
            # point part-way through.
            if stale_ids:
                graph_handler.prune_points(stale_ids)

            # On a shared page, append orphans to the first shared element (the root
            # Header/Footer container); otherwise append to the end of the page.
            container = None
            if locked_page.shared:
                root_id = graph_handler.graph.get(root_key)
                container = (
                    graph_handler.get_point(root_id) if root_id is not None else None
                )

            for orphan in Element.objects.filter(id__in=orphan_ids).order_by("id"):
                if container is not None:
                    graph_handler.insert(
                        orphan, container, GraphPointPosition.CHILD, ""
                    )
                else:
                    graph_handler.append(orphan)

            after = graph_handler.graph
            patch = {k: v for k, v in after.items() if before.get(k) != v}

        # Reflect the healed graph on the caller's page and drop any cached elements.
        page.graph = locked_page.graph
        self.invalidate_element_cache(page)

        self._report_graph_heal(page, orphan_ids, stale_ids, patch)

        return patch

    def _report_graph_heal(
        self,
        page: Page,
        healed_ids: set,
        pruned_ids: set,
        graph_patch: Dict[str, Any],
    ) -> None:
        """
        Surface a graph reconciliation in Sentry so we know it happened. Drift means
        the page graph diverged from the DB — typically element rows written or
        hard-deleted by older code during a non-zero-downtime deploy — and has now
        been repaired. Reported at "warning" level (it signals an upstream
        inconsistency, even though it's self-corrected), with the counts, ids and
        the applied patch.
        """

        import sentry_sdk

        with sentry_sdk.new_scope() as scope:
            scope.set_context(
                "graph_heal",
                {
                    "page_id": page.id,
                    "builder_id": page.builder_id,
                    "shared": page.shared,
                    "healed_element_count": len(healed_ids),
                    "healed_element_ids": sorted(healed_ids),
                    "pruned_stale_count": len(pruned_ids),
                    "pruned_stale_ids": sorted(pruned_ids),
                    "graph_patch": graph_patch,
                },
            )
            sentry_sdk.capture_message(
                f"Healed {len(healed_ids)} orphan element(s) and pruned "
                f"{len(pruned_ids)} stale point(s) from the graph of builder "
                f"page {page.id}.",
                level="warning",
            )

    def _get_builder_elements_cache_key(self, builder_id: int, specific: bool) -> str:
        return f"ab_get_{builder_id}_builder_elements_{specific}"

    def get_builder_elements(
        self,
        builder: Builder | int,
        base_queryset: Optional[QuerySet] = None,
        specific: bool = True,
        use_cache: bool = True,
    ) -> Union[QuerySet[Element], Iterable[Element]]:
        """
        Gets all the elements of a given builder.

        :param builder: The builder (or builder Id) that holds the pages that hold
          the elements.
        :param base_queryset: The base queryset to use to build the query.
        :param specific: Whether to return the generic elements or the specific
            instances.
        :return: The elements of that builder.
        """

        def _get_elements():
            queryset = (
                base_queryset if base_queryset is not None else Element.objects.all()
            )
            queryset = queryset.filter(page__builder=builder).select_related(
                "page__builder__workspace"
            )
            elements = self._query_elements(queryset, specific=specific)

            if use_cache and base_queryset is None:
                # We populate the per page cache with the result
                elements_per_page = defaultdict(list)
                grouped_elements = []
                for element in elements:
                    grouped_elements.append(element)
                    elements_per_page[element.page].append(element)

                for page, page_elements in elements_per_page.items():
                    local_cache.get(
                        self._get_elements_cache_key(page, specific),
                        page_elements,
                    )

            return elements

        if use_cache and base_queryset is None:
            return local_cache.get(
                self._get_builder_elements_cache_key(
                    builder.id if not isinstance(builder, int) else builder, specific
                ),
                _get_elements,
            )

        return _get_elements()

    def invalidate_element_cache(self, page: Page):
        """
        Invalidates the element, graph parent and visibility cache. To be used when we
        add or remove an element from the page (and from the graph).

        :param page: The target page cache.
        """

        local_cache.delete(self._get_elements_cache_key(page, True))
        local_cache.delete(self._get_elements_cache_key(page, False))
        local_cache.delete(
            BaseGraphHandler.generate_previous_position_map_cache_key(page)
        )
        ElementVisibilityPermissionManager.invalidate_builder_element_visibility_cache(
            page.builder_id
        )

    def create_element(
        self,
        element_type: ElementType,
        page: Page,
        reference_element: Element | None = None,
        position: GraphPointPositionType = "south",
        place_in_container: str = "",
        **kwargs,
    ) -> Element:
        """
        Creates a new element for a page.

        :param element_type: The type of the element.
        :param page: The page the element exists in.
        :param reference_element: The element reference element for the position.
        :param position: The position relative to the reference element.
        :param place_in_container: The place inside a container element, if any.
        :param kwargs: Additional attributes of the element.
        :return: The created element.
        """

        if element_type.is_deactivated(page.builder.workspace):
            raise ElementTypeDeactivated()

        allowed_values = extract_allowed(
            kwargs, self.allowed_fields_create + element_type.allowed_fields
        )
        allowed_values["page"] = page
        allowed_values = element_type.prepare_value_for_db(allowed_values)

        model_class = cast(Element, element_type.model_class)
        element = model_class(**allowed_values)
        element.save()

        element_type.after_create(element, kwargs)

        self.invalidate_element_cache(page)

        return element

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

        self.invalidate_element_cache(element.page)

        element.get_type().after_update(element, kwargs, element_changes)

        return element

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

        new_place_in_container = str(
            element_type.get_new_place_in_container(container_element, places)
        )

        return container_element.page.get_graph().merge_children_into_place(
            container_element, places, new_place_in_container
        )

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

        duplication = self._duplicate_element_recursive(
            element, id_mapping, element, GraphPointPosition.SOUTH
        )
        self.invalidate_element_cache(element.page)

        return duplication

    def _duplicate_element_recursive(
        self,
        element: Element,
        id_mapping,
        reference_element: Element | None = None,
        position: GraphPointPosition = GraphPointPosition.SOUTH,
    ) -> ElementsAndWorkflowActions:
        """
        Duplicates an element and all of its children.

        This method is separate from `duplicate_element` since it has additional params
        only required for the recursive calls.

        :param element: The element being duplicated
        :param id_mapping: The id_mapping dict used for export/import process
        :return: A list of duplicated elements
        """

        page = element.page
        element_type = element_type_registry.get_by_model(element)

        serialized = element_type.export_serialized(element)

        element_duplicated = self.import_element(
            element.page,
            serialized,
            id_mapping,
        )
        page.get_graph().insert(
            element_duplicated,
            reference_element,
            position,
            element.place_in_container if position == GraphPointPosition.CHILD else "",
        )

        workflow_actions_duplicated = self._duplicate_workflow_actions_of_element(
            element, id_mapping
        )

        elements_and_workflow_actions_duplicated = ElementsAndWorkflowActions(
            elements=[element_duplicated],
            workflow_actions=workflow_actions_duplicated,
        )

        # The first child duplicated into a given place becomes the head of that
        # slot (inserted as a CHILD of the duplicated parent); every subsequent
        # child in the same place chains SOUTH of the previously duplicated
        # sibling. This reproduces the original slot order faithfully and is
        # independent of how insert(..., CHILD, ...) orders multiple children
        # (which prepends, to stay the inverse of get_position).
        last_duplicated_in_place: Dict[str, Element] = {}
        for child in element.get_child_points():
            place = child.place_in_container
            if place in last_duplicated_in_place:
                child_reference = last_duplicated_in_place[place]
                child_position = GraphPointPosition.SOUTH
            else:
                child_reference = element_duplicated
                child_position = GraphPointPosition.CHILD
            children_duplicated = self._duplicate_element_recursive(
                child.specific, id_mapping, child_reference, child_position
            )
            last_duplicated_in_place[place] = children_duplicated["elements"][0]
            elements_and_workflow_actions_duplicated["elements"] += children_duplicated[
                "elements"
            ]
            elements_and_workflow_actions_duplicated["workflow_actions"] += (
                children_duplicated["workflow_actions"]
            )

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

    def _postprocess_imported_element(
        self,
        element_type: ElementType,
        created_instance: Element,
        id_mapping: Dict[str, Dict[int, int]],
        deferred_import_callback: Optional[DeferredImportCallback] = None,
    ):
        """
        Run the import post-processing for direct element imports.

        The bulk page import path calls these hooks centrally after all elements have
        been created and the graph has been migrated. Direct callers don't have that
        later phase, so the handler owns it here.
        """

        import_context = self.get_import_context_addition(
            created_instance.id, {created_instance.id: created_instance}
        )

        if deferred_import_callback is not None:
            deferred_import_callback(created_instance, id_mapping, import_context)

        updated_models = element_type.import_formulas(
            created_instance,
            id_mapping,
            import_formula,
            **import_context,
        )
        for model in updated_models:
            model.save()

    def import_element(
        self,
        page: Page,
        serialized_element: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict] = None,
        deferred_import_callbacks: Optional[Dict[int, DeferredImportCallback]] = None,
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
        :param deferred_import_callbacks: When provided, import post-processing is
            deferred and callbacks are collected in this dict keyed by element id.
        :return: the newly created instance.
        """

        if "builder_page_elements" not in id_mapping:
            id_mapping["builder_page_elements"] = {}

        element_type_name = serialized_element["type"]
        if element_type_name in old_element_type_map:
            # We met an old element type name. Let's migrate it.
            element_type_name = old_element_type_map[element_type_name]

        element_type = element_type_registry.get(element_type_name)

        deferred_import_callback = element_type.before_import(
            serialized_element,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        created_instance = element_type.import_serialized(
            page,
            serialized_element,
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            cache=cache,
            **kwargs,
        )

        id_mapping["builder_page_elements"][serialized_element["id"]] = (
            created_instance.id
        )

        if deferred_import_callbacks is None:
            self._postprocess_imported_element(
                element_type,
                created_instance,
                id_mapping,
                deferred_import_callback=deferred_import_callback,
            )
        elif deferred_import_callback is not None:
            deferred_import_callbacks[created_instance.id] = deferred_import_callback

        return created_instance
