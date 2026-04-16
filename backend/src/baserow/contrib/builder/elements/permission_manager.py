from typing import Any

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models import Q, QuerySet

from baserow.contrib.builder.elements.operations import ListElementsPageOperationType
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.operations import (
    DispatchBuilderWorkflowActionOperationType,
    ListBuilderWorkflowActionsPageOperationType,
)
from baserow.core.cache import global_cache
from baserow.core.graph.handler import BaseGraphHandler
from baserow.core.registries import PermissionManagerType
from baserow.core.subjects import AnonymousUserSubjectType
from baserow.core.user_sources.subjects import UserSourceUserSubjectType

from .models import Element

User = get_user_model()


# For now there can be up to three levels of nested elements.
# E.g. a RepeatElement might contain a ColumnElement, which might contain a
# HeadingElement.
# However, later this number could be dynamic depending on the page itself.
MAX_ELEMENT_NESTING_DEPTH = 3

ELEMENT_VISIBILITY_CACHE_KEY_PREFIX = "element_visibility"
ELEMENT_VISIBILITY_CACHE_TTL_SECONDS = 60 * 60  # 1 hour


class ElementVisibilityPermissionManager(PermissionManagerType):
    """This permission manager handle the element visibility permissions."""

    type = "element_visibility"
    supported_actor_types = [
        UserSourceUserSubjectType.type,
        AnonymousUserSubjectType.type,
    ]

    def auth_user_can_view_element(self, user, element):
        """
        Note: This method is currently only used by `check_multiple_permissions()`
        to check the user's permissions when dispatching a workflow action.

        Return True if the user should be allowed to view the element.
        Otherwise return False. The user type, user's role, and element's
        role_type are evaluated together to determine if the user should be
        allowed to view the element.

        Otherwise, the user's role and element's role_type are further evaluated.
            - If the role_type is 'allow_all', any user is allowed to view
                the element.
            - If the role_type is 'allow_all_except', any user is allowed
                to view the element, except for those users whose role is
                in the element's roles list.
            - If the role_type is 'disallow_all_except', all users are
                disallowed from viewing the element, unless the user's role
                is in the element's roles list.
        """

        # If the user type is `User` (e.g. Editor user), it won't have a role
        # or role_type. In which case, return True by default so that the
        # elements can be viewed in the editor.
        if isinstance(user, User):
            return True

        if element.role_type == Element.ROLE_TYPES.ALLOW_ALL:
            return True
        elif element.role_type == Element.ROLE_TYPES.ALLOW_ALL_EXCEPT:
            # Check if the user's role is disallowed
            return user.role not in element.roles
        elif element.role_type == Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT:
            # Check if the user's role is allowed
            return user.role in element.roles

        # Return False by default for safety
        return False

    def check_multiple_permissions(
        self,
        checks,
        workspace=None,
        include_trash=False,
    ):
        """
        If an element is not visible it should be impossible to dispatch an action
        related to this element.
        """

        result = {}

        for check in checks:
            if check.operation_name == DispatchBuilderWorkflowActionOperationType.type:
                if getattr(check.actor, "is_authenticated", False):
                    if (
                        check.context.element.visibility
                        == Element.VISIBILITY_TYPES.NOT_LOGGED
                    ):
                        result[check] = False
                    elif not self.auth_user_can_view_element(
                        check.actor, check.context.element
                    ):
                        result[check] = False
                else:
                    if (
                        check.context.element.visibility
                        == Element.VISIBILITY_TYPES.LOGGED_IN
                    ):
                        result[check] = False

        return result

    @classmethod
    def _get_visibility_version_cache_key(cls, page_id: int) -> str:
        """
        Returns the version-tracking key used to invalidate all per-actor
        visibility caches for a given page at once.

        :param page_id: The ID of the page whose version key to return.
        :return: The cache key string for the page's current version counter.
        """

        return f"{ELEMENT_VISIBILITY_CACHE_KEY_PREFIX}_version_{page_id}"

    @classmethod
    def _get_visibility_cache_key(cls, actor: Any, page_id: int) -> str:
        """
        Returns the per-actor cache key for the set of element IDs that are
        invisible to `actor` on the given page.

        Anonymous actors and authenticated actors share no key — and
        authenticated actors with different roles each get their own key —
        so that cached results are never mixed across actor types.

        :param actor: The actor whose visibility cache key to compute. May be
            an `AnonymousUser`, a `UserSourceUser`, or a Django `User`.
        :param page_id: The ID of the page.
        :return: The cache key string for this actor/page combination.
        """

        is_authenticated = getattr(actor, "is_authenticated", False)
        role = getattr(actor, "role", "") if is_authenticated else ""
        auth_segment = f"auth_{role}" if is_authenticated else "anon"
        return f"{ELEMENT_VISIBILITY_CACHE_KEY_PREFIX}_{page_id}_{auth_segment}"

    @classmethod
    def invalidate_page_element_visibility_cache(cls, page_id: int) -> None:
        """
        Bumps the version counter for `page_id`, causing every per-actor
        cache entry for that page to miss on the next read. Call this whenever
        an element on the page is created, updated, moved, or deleted.

        :param page_id: The ID of the page whose cache entries to invalidate.
        """

        global_cache.invalidate(
            invalidate_key=cls._get_visibility_version_cache_key(page_id)
        )

    def _should_exclude_element(
        self,
        actor: Any,
        element_id: int,
        element_map: dict[int, dict],
        parent_map: dict[int, int],
    ) -> bool:
        """
        Returns `True` if `element_id` — or any of its ancestors up to
        `MAX_ELEMENT_NESTING_DEPTH` levels — is invisible to `actor`
        according to visibility type and role configuration.

        For authenticated actors an element is excluded when its
        `visibility` is `NOT_LOGGED`, when `role_type` is
        `ALLOW_ALL_EXCEPT` and the actor's role is in the roles list, or
        when `role_type` is `DISALLOW_ALL_EXCEPT` and the actor's role is
        *not* in the roles list. For anonymous actors an element is excluded
        only when its `visibility` is `LOGGED_IN`.

        :param actor: The actor whose visibility is being evaluated.
        :param element_id: The ID of the element to check.
        :param element_map: Mapping of element ID → element value dict
            (keys: `id`, `visibility`, `role_type`, `roles`).
        :param parent_map: Mapping of child element ID → parent element ID,
            as returned by `BaseGraphHandler.get_parent_map()`.
        :return: `True` if the element should be excluded from the queryset.
        """

        is_authenticated = getattr(actor, "is_authenticated", False)
        current_id = element_id
        depth = 0

        while current_id is not None and depth <= MAX_ELEMENT_NESTING_DEPTH:
            elem = element_map.get(current_id)
            if elem is None:
                break

            if is_authenticated:
                if elem["visibility"] == Element.VISIBILITY_TYPES.NOT_LOGGED:
                    return True
                if elem[
                    "role_type"
                ] == Element.ROLE_TYPES.ALLOW_ALL_EXCEPT and actor.role in (
                    elem["roles"] or []
                ):
                    return True
                if elem[
                    "role_type"
                ] == Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT and actor.role not in (
                    elem["roles"] or []
                ):
                    return True
            else:
                if elem["visibility"] == Element.VISIBILITY_TYPES.LOGGED_IN:
                    return True

            current_id = parent_map.get(current_id)
            depth += 1

        return False

    def _compute_excluded_element_ids(self, actor: Any, page: Page) -> frozenset[int]:
        """
        Queries all elements for `page`, builds the ancestor map from the
        page graph, and returns the frozenset of element IDs invisible to
        `actor`.

        This is the uncached computation; call `_get_excluded_element_ids`
        to benefit from the global cache.

        :param actor: The actor whose visibility is being evaluated.
        :param page: The page whose elements are being filtered.
        :return: Frozenset of element IDs that `actor` is not allowed to see.
        """

        elements = list(
            Element.objects.filter(page=page).values(
                "id", "visibility", "role_type", "roles"
            )
        )
        element_map = {e["id"]: e for e in elements}
        parent_map = BaseGraphHandler.build_parent_map(page.graph)
        return frozenset(
            eid
            for eid in element_map
            if self._should_exclude_element(actor, eid, element_map, parent_map)
        )

    def _get_excluded_element_ids(self, actor: Any, page: Page) -> frozenset[int]:
        """
        Returns the cached frozenset of element IDs on `page` that are
        invisible to `actor`, computing and caching the result on a miss.

        The cache is invalidated via `invalidate_page_element_visibility_cache`
        whenever elements on the page change.

        :param actor: The actor whose visibility is being evaluated.
        :param page: The page whose elements are being filtered.
        :return: Frozenset of element IDs that `actor` is not allowed to see.
        """

        return global_cache.get(
            self._get_visibility_cache_key(actor, page.id),
            default=lambda: self._compute_excluded_element_ids(actor, page),
            invalidate_key=self._get_visibility_version_cache_key(page.id),
            timeout=ELEMENT_VISIBILITY_CACHE_TTL_SECONDS,
        )

    def _get_excluded_ids_for_element_queryset(
        self, actor: Any, queryset: QuerySet
    ) -> set[int]:
        """
        Fetches all elements for the pages referenced by `queryset` in a single
        combined query (including each page's graph via JOIN), then computes and
        returns the union of excluded element IDs across those pages for `actor`.

        Results are cached per-page in `global_cache` so that a subsequent call
        from `_get_excluded_ids_for_action_queryset` can benefit from cache hits.

        :param actor: The actor whose visibility is being evaluated.
        :param queryset: An `Element` queryset, already filtered by page
            visibility. Its `page_id` values determine which pages to check.
        :return: Set of element IDs that `actor` is not allowed to see.
        """

        # Single query: fetch all elements for the affected pages, annotated
        # with the page's graph so get_parent_map() needs no extra DB round-trips.
        all_elements = list(
            Element.objects.filter(
                page_id__in=queryset.values("page_id").distinct()
            ).values("id", "visibility", "role_type", "roles", "page_id", "page__graph")
        )

        if not all_elements:
            return set()

        # Group elements by page_id.
        by_page: dict[int, dict] = {}
        for elem in all_elements:
            pid = elem["page_id"]
            if pid not in by_page:
                by_page[pid] = {"graph": elem["page__graph"], "elements": []}
            by_page[pid]["elements"].append(elem)

        excluded: set[int] = set()
        for page_id, data in by_page.items():
            element_map = {e["id"]: e for e in data["elements"]}
            parent_map = BaseGraphHandler.build_parent_map(data["graph"])
            page_excluded = frozenset(
                eid
                for eid in element_map
                if self._should_exclude_element(actor, eid, element_map, parent_map)
            )
            # Store the result in the per-page global cache so that the
            # action queryset helper can benefit from cache hits.  On a
            # cache miss the pre-computed frozenset is stored directly; on
            # a hit the cached value is returned and used (ensuring the
            # element and action steps stay consistent with each other).
            excluded |= global_cache.get(
                self._get_visibility_cache_key(actor, page_id),
                default=page_excluded,
                invalidate_key=self._get_visibility_version_cache_key(page_id),
                timeout=ELEMENT_VISIBILITY_CACHE_TTL_SECONDS,
            )

        return excluded

    def _get_excluded_ids_for_action_queryset(
        self, actor: Any, queryset: QuerySet
    ) -> set[int]:
        """
        Collects the distinct elements referenced by the workflow-action
        `queryset`, groups them by page, and returns the set of element IDs
        that `actor` cannot see — which in turn blocks the linked actions.

        :param actor: The actor whose visibility is being evaluated.
        :param queryset: A `BuilderWorkflowAction` queryset, already filtered
            by page visibility. Its `element_id` values are examined.
        :return: Set of element IDs (not action IDs) that `actor` cannot see.
        """

        elements = Element.objects.filter(
            id__in=queryset.values("element_id").distinct()
        ).select_related("page")

        page_to_elem_ids: dict[Any, set[int]] = {}
        for element in elements:
            page_to_elem_ids.setdefault(element.page, set()).add(element.id)

        excluded: set[int] = set()
        for page, elem_ids in page_to_elem_ids.items():
            page_excluded = self._get_excluded_element_ids(actor, page)
            excluded |= elem_ids & page_excluded
        return excluded

    def exclude_elements_with_page_visibility(
        self,
        queryset: QuerySet,
        actor: AbstractUser,
    ) -> QuerySet:
        """
        Update the queryset by excluding all Elements that the user isn't
        allowed to view, based on the Page visibility settings.
        """

        if not getattr(actor, "is_authenticated", False):
            return queryset.exclude(page__visibility=Page.VISIBILITY_TYPES.LOGGED_IN)

        return queryset.exclude(
            page__role_type=Page.ROLE_TYPES.ALLOW_ALL_EXCEPT,
            page__roles__contains=actor.role,
        ).exclude(
            Q(page__role_type=Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT)
            & ~Q(page__roles__contains=actor.role),
        )

    def filter_queryset(
        self,
        actor,
        operation_name: str,
        queryset,
        workspace=None,
    ):
        """Filters out invisible elements and their workflow actions."""

        if operation_name == ListElementsPageOperationType.type:
            queryset = self.exclude_elements_with_page_visibility(queryset, actor)
            excluded_ids = self._get_excluded_ids_for_element_queryset(actor, queryset)
            return queryset.exclude(id__in=excluded_ids)

        elif operation_name == ListBuilderWorkflowActionsPageOperationType.type:
            queryset = self.exclude_elements_with_page_visibility(queryset, actor)
            excluded_element_ids = self._get_excluded_ids_for_action_queryset(
                actor, queryset
            )
            return queryset.exclude(element_id__in=excluded_element_ids)

        return queryset
