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
from baserow.core.registries import PermissionManagerType
from baserow.core.subjects import AnonymousUserSubjectType
from baserow.core.user_sources.subjects import UserSourceUserSubjectType

from .models import Element

User = get_user_model()


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
    def _get_visibility_version_cache_key(cls, builder_id: int) -> str:
        """
        Returns the version-tracking key used to invalidate all per-role
        visibility caches for a given builder at once.

        :param builder_id: The ID of the builder whose version key to return.
        :return: The cache key string for the builder's current version counter.
        """

        return f"{ELEMENT_VISIBILITY_CACHE_KEY_PREFIX}_version_{builder_id}"

    @classmethod
    def _get_visibility_cache_key(cls, role: str | None, builder_id: int) -> str:
        """
        Returns the per-role cache key for the set of element IDs that are
        invisible to `role` in the given builder.

        Anonymous actors and authenticated actors share no key — and
        authenticated actors with different roles each get their own key —
        so that cached results are never mixed across actor types.

        :param role: The role whose visibility cache key to compute. May be
            None or a string.
        :param builder_id: The ID of the builder.
        :return: The cache key string for this role/builder combination.
        """

        is_authenticated = role is not None
        auth_segment = f"auth_{role}" if is_authenticated else "anon"
        return f"{ELEMENT_VISIBILITY_CACHE_KEY_PREFIX}_{builder_id}_{auth_segment}"

    @classmethod
    def invalidate_builder_element_visibility_cache(cls, builder_id: int) -> None:
        """
        Invalidate cache for `builder_id`, causing every per-role
        cache entry for that builder to miss on the next read. Call this whenever
        an element in the builder is created, updated, moved, or deleted.

        :param builder_id: The ID of the builder whose cache entries to invalidate.
        """

        global_cache.invalidate(
            invalidate_key=cls._get_visibility_version_cache_key(builder_id)
        )

    def is_element_hidden(self, element, role, cache=None):
        """
        Return whether `element` is hidden for the given `role`, including any
        visibility restrictions inherited from parent elements.
        """

        cache = cache if cache is not None else {}

        if element.id in cache:
            return cache[element.id]

        is_authenticated = role is not None
        roles = element.roles or []
        result = False

        if is_authenticated:
            if element.visibility == Element.VISIBILITY_TYPES.NOT_LOGGED:
                result = True

            elif (
                element.role_type == Element.ROLE_TYPES.ALLOW_ALL_EXCEPT
                and role in roles
            ):
                result = True

            elif (
                element.role_type == Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT
                and role not in roles
            ):
                result = True
        else:
            if element.visibility == Element.VISIBILITY_TYPES.LOGGED_IN:
                result = True

        for parent in element.get_parent_points():
            if self.is_element_hidden(parent, role, cache):
                result = True
                break

        cache[element.id] = result
        return result

    def get_hidden_element_ids(self, role, builder_ids):
        """
        Returns the hidden element IDs for the provided builder IDs.
        """

        from baserow.contrib.builder.elements.handler import ElementHandler

        builder_ids = list(builder_ids)
        hidden_ids = []
        cache = {}

        for builder_id in builder_ids:
            cache_key = self._get_visibility_cache_key(role, builder_id)
            invalidate_key = self._get_visibility_version_cache_key(builder_id)

            hidden_ids.extend(
                global_cache.get(
                    cache_key,
                    invalidate_key=invalidate_key,
                    default=lambda builder_id=builder_id: [
                        e.id
                        for e in ElementHandler().get_builder_elements(builder_id)
                        if self.is_element_hidden(e, role, cache)
                    ],
                    timeout=ELEMENT_VISIBILITY_CACHE_TTL_SECONDS,
                )
            )

        return hidden_ids

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
            page__roles__contains=[actor.role],
        ).exclude(
            Q(page__role_type=Page.ROLE_TYPES.DISALLOW_ALL_EXCEPT)
            & ~Q(page__roles__contains=[actor.role]),
        )

    def filter_queryset(
        self,
        actor,
        operation_name: str,
        queryset,
        workspace=None,
    ):
        """Filters out invisible elements and their workflow actions."""

        actor_role = (
            getattr(actor, "role", None)
            if getattr(actor, "is_authenticated", False)
            else None
        )

        if operation_name == ListElementsPageOperationType.type:
            queryset = self.exclude_elements_with_page_visibility(queryset, actor)

            builder_ids = set(
                list(queryset.values_list("page__builder_id", flat=True).distinct())
            )
            excluded_ids = self.get_hidden_element_ids(actor_role, builder_ids)

            return queryset.exclude(id__in=excluded_ids)

        elif operation_name == ListBuilderWorkflowActionsPageOperationType.type:
            queryset = self.exclude_elements_with_page_visibility(queryset, actor)
            builder_ids = set(
                list(queryset.values_list("page__builder_id", flat=True).distinct())
            )
            excluded_element_ids = self.get_hidden_element_ids(actor_role, builder_ids)
            return queryset.exclude(element_id__in=excluded_element_ids)

        return queryset
