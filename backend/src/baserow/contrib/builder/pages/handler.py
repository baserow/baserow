from collections import defaultdict
from typing import Any, Dict, List, Optional
from zipfile import ZipFile

from django.core.files.storage import Storage
from django.db import IntegrityError
from django.db.models import QuerySet

from baserow.contrib.builder.constants import IMPORT_SERIALIZED_IMPORTING
from baserow.contrib.builder.data_sources.handler import DataSourceHandler
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.types import ElementDictSubClass
from baserow.contrib.builder.models import Builder
from baserow.contrib.builder.pages.constants import (
    ILLEGAL_PATH_SAMPLE_CHARACTER,
    PAGE_PATH_PARAM_PREFIX,
    PATH_PARAM_REGEX,
    QUERY_PARAM_EXACT_MATCH_REGEX,
)
from baserow.contrib.builder.pages.exceptions import (
    DuplicatePageParams,
    DuplicatePathParamsInPath,
    InvalidQueryParamName,
    PageDoesNotExist,
    PageNameNotUnique,
    PageNotInBuilder,
    PagePathNotUnique,
    PathParamNotDefined,
    PathParamNotInPath,
    SharedPageIsReadOnly,
)
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.pages.types import (
    PagePathParams,
    PageQueryParam,
    PageQueryParams,
)
from baserow.contrib.builder.types import PageDict
from baserow.contrib.builder.workflow_actions.handler import (
    BuilderWorkflowActionHandler,
)
from baserow.core.cache import global_cache
from baserow.core.exceptions import IdDoesNotExist
from baserow.core.psycopg import is_unique_violation_error
from baserow.core.storage import ExportZipFile
from baserow.core.user_sources.user_source_user import UserSourceUser
from baserow.core.utils import ChildProgressBuilder, MirrorDict, find_unused_name

BUILDER_PAGE_IS_PUBLISHED_CACHE_TTL_SECONDS = 60 * 60


class PageHandler:
    def get_page(self, page_id: int, base_queryset: Optional[QuerySet] = None) -> Page:
        """
        Gets a page by ID.

        :param page_id: The ID of the page
        :param base_queryset: Can be provided to already filter or apply performance
            improvements to the queryset when it's being executed
        :raises PageDoesNotExist: If the page doesn't exist
        :return: The model instance of the Page
        """

        if base_queryset is None:
            base_queryset = Page.objects

        try:
            return base_queryset.select_related("builder__workspace").get(id=page_id)
        except Page.DoesNotExist:
            raise PageDoesNotExist()

    def get_shared_page(self, builder: Builder) -> Page:
        """
        Returns the shared page for the given builder.
        """

        return Page.objects.select_related("builder__workspace").get(
            builder=builder, shared=True
        )

    def get_pages(self, builder, base_queryset: Optional[QuerySet] = None):
        """
        Returns all the page in the current builder.
        """

        if base_queryset is None:
            base_queryset = Page.objects.all()

        return base_queryset.filter(builder=builder).select_related(
            "builder__workspace"
        )

    def create_shared_page(self, builder: Builder) -> Page:
        """
        Creates the shared page of the given builder.

        :param builder: The ID of the builder we want to create the shared page.
        :return: The model instance of the shared Page
        """

        return self.create_page(
            builder, name="__shared__", path="__shared__", shared=True
        )

    def create_page(
        self,
        builder: Builder,
        name: str,
        path: str,
        path_params: PagePathParams = None,
        query_params: PageQueryParam = None,
        shared: bool = False,
    ) -> Page:
        """
        Creates a new page.

        :param builder: The builder the page belongs to
        :param name: The name of the page
        :param path: The path of the page
        :param path_params: The params of the path provided
        :param query_params: The query params of the page provided
        :param shared: If this is the shared page. They should be only one shared page
          per builder application.
        :return: The newly created page instance
        """

        last_order = Page.get_last_order(builder)
        path_params = path_params or []
        query_params = query_params or []

        self.is_page_path_valid(path, path_params, raises=True)
        self.is_page_path_unique(builder, path, raises=True)

        try:
            page = Page.objects.create(
                builder=builder,
                name=name,
                order=last_order,
                path=path,
                path_params=path_params,
                query_params=query_params,
                shared=shared,
            )
        except IntegrityError as e:
            if "unique constraint" in e.args[0] and "name" in e.args[0]:
                raise PageNameNotUnique(name=name, builder_id=builder.id)
            if "unique constraint" in e.args[0] and "path" in e.args[0]:
                raise PagePathNotUnique(path=path, builder_id=builder.id)
            raise e

        return page

    def delete_page(self, page: Page):
        """
        Deletes the page provided.

        :param page: The page that must be deleted
        """

        if page.shared:
            raise SharedPageIsReadOnly()

        page.delete()

    def update_page(self, page: Page, **kwargs) -> Page:
        """
        Updates fields of a page.

        :param page: The page that should be updated
        :param kwargs: The fields that should be updated with their corresponding value
        :return: The updated page
        """

        if page.shared:
            raise SharedPageIsReadOnly()

        if "path" in kwargs or "path_params" in kwargs:
            path = kwargs.get("path", page.path)
            path_params = kwargs.get("path_params", page.path_params)

            self.is_page_path_valid(path, path_params, raises=True)
            self.is_page_path_unique(
                page.builder,
                path,
                base_queryset=Page.objects.exclude(
                    id=page.id
                ),  # We don't want to conflict with the current page
                raises=True,
            )
        if "query_params" in kwargs:
            query_params = kwargs.get("query_params")
            self.validate_query_params(
                kwargs.get("path", page.path),
                kwargs.get("path_params", page.path_params),
                query_params,
            )

        for key, value in kwargs.items():
            setattr(page, key, value)

        try:
            page.save()
        except IntegrityError as e:
            if is_unique_violation_error(e) and "name" in e.args[0]:
                raise PageNameNotUnique(name=page.name, builder_id=page.builder_id)
            if is_unique_violation_error(e) and "path" in e.args[0]:
                raise PagePathNotUnique(path=page.path, builder_id=page.builder_id)
            raise e

        return page

    def order_pages(
        self, builder: Builder, order: List[int], base_qs=None
    ) -> List[int]:
        """
        Assigns a new order to the pages in a builder application.
        You can provide a base_qs for pre-filter the pages affected by this change.

        :param builder: The builder that the pages belong to
        :param order: The new order of the pages
        :param base_qs: A QS that can have filters already applied
        :raises PageNotInBuilder: If the page is not part of the provided builder
        :return: The new order of the pages
        """

        if base_qs is None:
            base_qs = Page.objects_without_shared.filter(builder=builder)

        try:
            full_order = Page.order_objects(base_qs, order)
        except IdDoesNotExist as error:
            raise PageNotInBuilder(error.not_existing_id)

        return full_order

    @classmethod
    def get_page_public_records_cache_key(
        cls, page_id: int, user: UserSourceUser, record_name: str
    ):
        """
        Generates the cache key used by the public elements, data sources and workflow
        actions endpoints. If the `user` is authenticated, and they have a role, we will
        include the role in the cache key.

        :param page_id: the ID of the public page being requested.
        :param user: the `UserSourceUser` performing the HTTP request.
        :param record_name: one of "elements", "data_sources" or "workflow_actions".
            Used to differentiate between public view endpoints.
        :return: the cache key.
        """

        role = f"_{user.role}" if not user.is_anonymous and user.role else ""
        return f"ab_public_page_{page_id}{role}_{record_name}_records"

    def is_published_page(self, public_page_id: int) -> bool:
        """
        Returns whether this public page ID points to a published domain
        application or not.

        :param public_page_id: The ID of the public page.
        :return: whether this public page ID is published or not.
        """

        return global_cache.get(
            f"ab_public_page_{public_page_id}_published",
            default=lambda: self._is_published_application_page(public_page_id),
            timeout=BUILDER_PAGE_IS_PUBLISHED_CACHE_TTL_SECONDS,
        )

    def _is_published_application_page(self, public_page_id: int) -> bool:
        """
        Given a *public* page ID, is responsible for returning the published domain
        application it's associated with.

        :param public_page_id: The ID of the public page.
        :return: The published domain application associated with the public page.
        """

        return (
            Builder.objects.filter(page__id=public_page_id)
            .exclude(published_from=None)
            .exists()
        )

    def duplicate_page(
        self, page: Page, progress_builder: Optional[ChildProgressBuilder] = None
    ):
        """
        Duplicates an existing page instance.

        :param page: The page that is being duplicated
        :param progress_builder: A progress object that can be used to report progress
        :raises ValueError: When the provided page is not an instance of Page.
        :return: The duplicated page
        """

        if page.shared:
            raise SharedPageIsReadOnly()

        start_progress, export_progress, import_progress = 10, 30, 60
        progress = ChildProgressBuilder.build(progress_builder, child_total=100)
        progress.increment(by=start_progress)

        builder = page.builder

        exported_page = self.export_page(page)

        # Set a unique name for the page to import back as a new one.
        exported_page["name"] = self.find_unused_page_name(builder, page.name)
        exported_page["path"] = self.find_unused_page_path(builder, page.path)
        exported_page["order"] = Page.get_last_order(builder)

        progress.increment(by=export_progress)

        id_mapping = defaultdict(lambda: MirrorDict())
        id_mapping["builder_pages"] = MirrorDict()
        id_mapping["builder_elements"] = {}
        id_mapping["builder_workflow_actions"] = {}

        shared_data_sources = DataSourceHandler().get_data_sources(
            page=page.builder.shared_page
        )
        # Populate data_sources id_mapping with existing data sources as we want
        # to keep the same Id for these.
        id_mapping["builder_data_sources"] = {
            ds.id: ds.id for ds in shared_data_sources
        }

        new_page_clone = self.import_page(
            builder,
            exported_page,
            progress=progress.create_child_builder(represents_progress=import_progress),
            id_mapping=id_mapping,
        )

        return new_page_clone

    def find_unused_page_name(self, builder: Builder, proposed_name: str) -> str:
        """
        Finds an unused name for a page in a builder.

        :param builder: The builder that the page belongs to.
        :param proposed_name: The name that is proposed to be used.
        :return: A unique name to use.
        """

        existing_pages_names = list(builder.page_set.values_list("name", flat=True))
        return find_unused_name([proposed_name], existing_pages_names, max_length=255)

    def find_unused_page_path(self, builder: Builder, proposed_path: str) -> str:
        """
        Find an unused path for a page in a builder.

        :param builder: The builder that the page belongs to.
        :param proposed_path: The path that is proposed to be used.
        :return: A unique path to use
        """

        page_path = proposed_path
        if page_path.endswith("/"):
            page_path = page_path[:-1]

        existing_paths = list(builder.page_set.values_list("path", flat=True))
        return find_unused_name(
            [page_path], existing_paths, max_length=255, suffix="/{0}"
        )

    def is_page_path_valid(
        self, path: str, path_params: PagePathParams, raises: bool = False
    ) -> bool:
        """
        Checks if a path object is constructed correctly. If there is a mismatch
        between the path itself and the path params for example, it becomes an invalid
        path.

        :param path: The path in question
        :param path_params: The param definitions of the path provided
        :param raises: If true, raises exceptions instead of returning a boolean
        :raises PathParamNotInPath: If the path param is not in the path
        :raises PathParamNotDefined: If a param in the path was not defined as a path
            param in the path_params provided
        :return: If the path is valid
        """

        path_param_names = [p["name"] for p in path_params]

        # Make sure all path params are also in the path
        for path_param_name in path_param_names:
            if f"{PAGE_PATH_PARAM_PREFIX}{path_param_name}" not in path:
                if raises:
                    raise PathParamNotInPath(path, path_param_name)
                return False

        path_params_in_path = PATH_PARAM_REGEX.findall(path)
        unique_path_params_in_path = set(path_params_in_path)

        if len(unique_path_params_in_path) != len(path_params_in_path):
            duplicate_path_param_names = [
                name
                for name in path_param_names
                if name not in unique_path_params_in_path
            ]
            if raises:
                raise DuplicatePathParamsInPath(path, duplicate_path_param_names)
            return False

        for path_param_in_path in path_params_in_path:
            param_name = path_param_in_path[1:]

            if param_name not in path_param_names:
                if raises:
                    raise PathParamNotDefined(path, param_name, path_param_names)
                return False

        return True

    def validate_query_params(
        self, path: str, path_params: PagePathParams, query_params: PageQueryParams
    ) -> bool:
        """
        Validates the query parameters of a page.

        :param path: The path of the page.
        :param path_params: The path parameters defined for the page.
        :param query_params: The query parameters to validate.
        :raises InvalidQueryParamName: If a query parameter name doesn't match the
            required format.
        :raises DuplicatePageParams: If a query parameter is defined multiple times
            or clashes with path parameters.
        :return: True if validation passes.
        """

        # Extract path param names for checking duplicates
        path_param_names = [p["name"] for p in path_params]

        # Get list of query param names
        query_param_names = [p["name"] for p in query_params]

        # Check for duplicates within query params
        seen_params = set()
        for param_name in query_param_names:
            # Validate query param name format using regex
            if not QUERY_PARAM_EXACT_MATCH_REGEX.match(param_name):
                raise InvalidQueryParamName(query_param_name=param_name)

            # Check if param name already seen or conflicts with path param
            if param_name in seen_params or param_name in path_param_names:
                raise DuplicatePageParams(
                    param=param_name,
                    query_param_names=query_param_names,
                    path_param_names=path_param_names,
                )

            seen_params.add(param_name)

        return True

    def is_page_path_unique(
        self,
        builder: Builder,
        path: str,
        base_queryset: QuerySet = None,
        raises: bool = False,
    ) -> bool:
        """
        Checks if a page path is unique.

        :param builder: The builder that the page belongs to
        :param path: The path it is trying to set
        :param raises: If true will raise an exception when the path isn't unique
        :return: If the path is unique
        """

        queryset = Page.objects if base_queryset is None else base_queryset

        existing_paths = queryset.filter(builder=builder).values_list("path", flat=True)

        path_generalised = self.generalise_path(path)
        for existing_path in existing_paths:
            if self.generalise_path(existing_path) == path_generalised:
                if raises:
                    raise PagePathNotUnique(path=path, builder_id=builder.id)
                return False
        return True

    def generalise_path(self, path: str) -> str:
        """
        Returns a generalised version of a path. This can be useful if we are trying to
        understand if 2 paths are equivalent even if their path params have different
        names.

        For 2 paths to be equivalent they need to have the same static parts of the path
        and the same amount and position of path parameters.

        Equivalent:
        /product/:id, /product/:new
        /product/:id/hello/:new, /product/:new/hello/:id

        Not equivalent:
        /product/:id, /product/:id/:new
        /product/:id/hello/:new, /product/:id/:new/hello

        By replacing all the path parameters in the path with an illegal path character
        we can make sure that we can match 2 paths and, they will be the same string if
        they are indeed a duplicate given the above rules.

        :param path: The path that is being generalised
        :return: The generalised path
        """

        return PATH_PARAM_REGEX.sub(ILLEGAL_PATH_SAMPLE_CHARACTER, path)

    def export_page(
        self,
        page: Page,
        files_zip: Optional[ExportZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
    ) -> PageDict:
        """
        Serializes the given page.

        :param page: The instance to serialize.
        :param files_zip: A zip file to store files in necessary.
        :param storage: Storage to use.
        :return: The serialized version.
        """

        # Get serialized version of all elements of the current page
        serialized_elements = [
            ElementHandler().export_element(
                e, files_zip=files_zip, storage=storage, cache=cache
            )
            for e in ElementHandler().get_elements(page=page)
        ]

        # Get serialized versions of all workflow actions of the current page
        serialized_workflow_actions = [
            BuilderWorkflowActionHandler().export_workflow_action(
                wa, files_zip=files_zip, storage=storage, cache=cache
            )
            for wa in BuilderWorkflowActionHandler().get_workflow_actions(page=page)
        ]

        # Get serialized version of all data_sources for the current page
        serialized_data_sources = [
            DataSourceHandler().export_data_source(
                ds, files_zip=files_zip, storage=storage, cache=cache
            )
            for ds in DataSourceHandler().get_data_sources(page=page)
        ]

        return PageDict(
            id=page.id,
            name=page.name,
            order=page.order,
            path=page.path,
            path_params=page.path_params,
            query_params=page.query_params,
            shared=page.shared,
            elements=serialized_elements,
            data_sources=serialized_data_sources,
            workflow_actions=serialized_workflow_actions,
            visibility=page.visibility,
            role_type=page.role_type,
            roles=page.roles,
        )

    def _ops_count_for_import_page(
        self,
        serialized_pages: List[Dict[str, Any]],
    ) -> int:
        """
        Count number of steps for the operation. Used to track task progress.
        """

        return (
            len(serialized_pages["elements"])
            + len(serialized_pages["data_sources"])
            + len(serialized_pages["workflow_actions"])
            + 1
        )

    def import_pages(
        self,
        builder: Builder,
        serialized_pages: List[Dict[str, Any]],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
    ):
        """
        Import multiple pages at once. Especially useful when we have dependencies
        between element of the page. Page are imported first then other part of
        the page.

        :param builder: The builder instance the new page should belong to.
        :param serialized_pages: The serialized version of the pages.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :param progress: A progress object that can be used to report progress.
        :param cache: A cache to use for the import.
        :return: the newly created instances.
        """

        if cache is None:
            cache = {}

        child_total = sum(self._ops_count_for_import_page(p) for p in serialized_pages)
        progress = ChildProgressBuilder.build(progress, child_total=child_total)

        imported_pages = []
        for serialized_page in serialized_pages:
            page_instance = self.import_page_only(
                builder,
                serialized_page,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                progress=progress,
                cache=cache,
            )
            imported_pages.append([page_instance, serialized_page])

        for page_instance, serialized_page in imported_pages:
            self.import_data_sources(
                page_instance,
                serialized_page["data_sources"],
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                progress=progress,
                cache=cache,
            )

        for page_instance, serialized_page in imported_pages:
            self.import_elements(
                page_instance,
                serialized_page["elements"],
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                progress=progress,
                cache=cache,
            )

        for page_instance, serialized_page in imported_pages:
            self.import_workflow_actions(
                page_instance,
                serialized_page["workflow_actions"],
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                progress=progress,
                cache=cache,
            )

        return [i[0] for i in imported_pages]

    def import_page(
        self,
        builder: Builder,
        serialized_page: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
    ):
        """
        Creates an instance using the serialized version previously exported with
        `.export_page'.

        :param builder: The builder instance the new page should belong to.
        :param serialized_page: The serialized version of the page.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :param progress: A progress object that can be used to report progress.
        :param cache: A cache to use for the import.
        :return: the newly created instance.
        """

        return self.import_pages(
            builder,
            [serialized_page],
            id_mapping,
            files_zip=files_zip,
            storage=storage,
            progress=progress,
            cache=cache,
        )[0]

    def import_page_only(
        self,
        builder: Builder,
        serialized_page: Dict[str, Any],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        cache: Optional[Dict[str, any]] = None,
        progress: Optional[ChildProgressBuilder] = None,
    ):
        if "builder_pages" not in id_mapping:
            id_mapping["builder_pages"] = {}

        shared = serialized_page.get("shared", False)

        if shared:
            # The shared page has already been created at builder creation. Let's
            # reuse that one.
            page_instance = builder.shared_page
            page_instance.name = serialized_page["name"]
            page_instance.order = serialized_page["order"]
            page_instance.path = serialized_page["path"]
            page_instance.path_params = serialized_page["path_params"]
        else:
            # Note: serialized pages exported before the page visibility feature
            # will not contain the `visibility`, `role_type` or `roles` keys,
            # so we use the default values for all three values instead.
            page_instance = Page.objects.create(
                builder=builder,
                name=serialized_page["name"],
                order=serialized_page["order"],
                path=serialized_page["path"],
                path_params=serialized_page["path_params"],
                query_params=serialized_page.get("query_params", []),
                shared=False,
                visibility=serialized_page.get("visibility", Page.VISIBILITY_TYPES.ALL),
                role_type=serialized_page.get("role_type", Page.ROLE_TYPES.ALLOW_ALL),
                roles=serialized_page.get("roles", []),
            )

        id_mapping["builder_pages"][serialized_page["id"]] = page_instance.id

        progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        return page_instance

    def import_data_sources(
        self,
        page: Page,
        serialized_data_sources: List[Dict],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
    ):
        """
        Import all page data sources.

        :param page: the page the elements should belong to.
        :param serialized_data_sources: the list of serialized elements.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :return: the newly created instance list.
        """

        for serialized_data_source in serialized_data_sources:
            DataSourceHandler().import_data_source(
                page,
                serialized_data_source,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                cache=cache,
            )
            progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

    def import_elements(
        self,
        page: Page,
        serialized_elements: List[ElementDictSubClass],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
    ):
        """
        Import all page elements, dealing with the potential incorrect order regarding
        element hierarchy: the parents need to be imported first.

        :param page: the page the elements should belong to.
        :param serialized_elements: the list of serialized elements.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :param progress: A progress object that can be used to report progress.
        :param cache: A cache to use for the import.
        :return: the newly created instance list.
        """

        # For element we can have a hierarchy and we can have a parent element that is
        # needs to be created before the child element.
        # That why we are iterating until all elements are created.
        imported_elements = []

        # Sort the serialized elements so that we import:
        # Containers first
        # Form elements second
        # Everything else after that.
        def element_priority_sort(element_to_sort):
            return element_type_registry.get(
                element_to_sort["type"]
            ).import_element_priority

        prioritized_elements = sorted(
            serialized_elements, key=element_priority_sort, reverse=True
        )

        # True if we have imported at least one element on last iteration
        was_imported = True
        while was_imported:
            was_imported = False

            for serialized_element in prioritized_elements:
                parent_element_id = serialized_element["parent_element_id"]
                # check that the element has not already been imported in a
                # previous pass or if the parent doesn't exist yet.
                if serialized_element["id"] not in id_mapping.get(
                    "builder_page_elements", {}
                ) and (
                    parent_element_id is None
                    or parent_element_id in id_mapping.get("builder_page_elements", {})
                ):
                    imported_element = ElementHandler().import_element(
                        page,
                        serialized_element,
                        id_mapping,
                        files_zip=files_zip,
                        storage=storage,
                        cache=cache,
                    )

                    imported_elements.append(imported_element)

                    was_imported = True
                    if progress:
                        progress.increment(state=IMPORT_SERIALIZED_IMPORTING)

        return imported_elements

    def import_workflow_actions(
        self,
        page: Page,
        serialized_workflow_actions: List[Dict],
        id_mapping: Dict[str, Dict[int, int]],
        files_zip: Optional[ZipFile] = None,
        storage: Optional[Storage] = None,
        progress: Optional[ChildProgressBuilder] = None,
        cache: Optional[Dict[str, any]] = None,
        **kwargs,
    ):
        """
        Import all page workflow_actions.

        :param page: the page the elements should belong to.
        :param serialized_workflow_actions: the list of serialized actions.
        :param id_mapping: A map of old->new id per data type
            when we have foreign keys that need to be migrated.
        :param files_zip: Contains files to import if any.
        :param storage: Storage to get the files from.
        :return: the newly created instance list.
        """

        # Sort action because we might have formula that use previous actions
        serialized_workflow_actions.sort(key=lambda action: action["order"])

        for serialized_workflow_action in serialized_workflow_actions:
            BuilderWorkflowActionHandler().import_workflow_action(
                page,
                serialized_workflow_action,
                id_mapping,
                files_zip=files_zip,
                storage=storage,
                cache=cache,
                **kwargs,
            )
            progress.increment(state=IMPORT_SERIALIZED_IMPORTING)
