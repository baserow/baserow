from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db.models import Q, QuerySet

from baserow.contrib.builder.elements.operations import ListElementsPageOperationType
from baserow.contrib.builder.pages.models import Page
from baserow.contrib.builder.workflow_actions.operations import (
    DispatchBuilderWorkflowActionOperationType,
    ListBuilderWorkflowActionsPageOperationType,
)
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

    def exclude_elements_with_role(
        self,
        queryset: QuerySet,
        role_type: Element.ROLE_TYPES,
        role: str,
        prefix: str = "",
    ) -> QuerySet:
        """
        Update the queryset by excluding all Elements that match a particular
        role_type *and* role.

        The prefix is to support Elements that are a child of a different
        Instance, e.g. when a BuilderWorkflowAction queryset is passed in,
        we want to filter against the Element foreign key, not the action
        itself.

        The queryset exclusion logic is repeated to support the maximum level
        of element nesting.
        """

        query = Q()
        for level in range(MAX_ELEMENT_NESTING_DEPTH):
            path = prefix + "parent_element__" * level
            query |= Q(**{f"{path}role_type": role_type}) & Q(
                **{f"{path}roles__contains": role}
            )

        queryset = queryset.exclude(query)

        return queryset

    def exclude_elements_without_role(
        self,
        queryset: QuerySet,
        role_type: Element.VISIBILITY_TYPES,
        role: str,
        prefix: str = "",
    ) -> QuerySet:
        """
        Update the queryset by excluding all Elements that match a particular
        role_type but *not* the role.

        The prefix is to support Elements that are a child of a different
        Instance, e.g. when a BuilderWorkflowAction queryset is passed in,
        we want to filter against the Element foreign key, not the action
        itself.

        The queryset exclusion logic is repeated to support the maximum level
        of element nesting.
        """

        query = Q()
        for level in range(MAX_ELEMENT_NESTING_DEPTH):
            path = prefix + "parent_element__" * level
            query |= Q(**{f"{path}role_type": role_type}) & ~Q(
                **{f"{path}roles__contains": role}
            )

        queryset = queryset.exclude(query)

        return queryset

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

    def exclude_elements_with_visibility(
        self,
        queryset: QuerySet,
        visibility_type: Element.VISIBILITY_TYPES,
        prefix: str = "",
    ) -> QuerySet:
        """
        Update the queryset by excluding all Elements that match a particular
        visibility_type.

        The prefix is to support Elements that are a child of a different
        Instance, e.g. when a BuilderWorkflowAction instance is passed in
        we want to filter against its element foreign key, not the action
        itself.

        The queryset exclusion logic is repeated to support the maximum level
        of element nesting.
        """

        query = Q()
        for level in range(MAX_ELEMENT_NESTING_DEPTH):
            path = prefix + "parent_element__" * level
            query |= Q(**{f"{path}visibility": visibility_type})

        queryset = queryset.exclude(query)

        return queryset

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
            if getattr(actor, "is_authenticated", False):
                queryset = self.exclude_elements_with_visibility(
                    queryset, Element.VISIBILITY_TYPES.NOT_LOGGED
                )
                queryset = self.exclude_elements_with_role(
                    queryset, Element.ROLE_TYPES.ALLOW_ALL_EXCEPT, actor.role
                )
                queryset = self.exclude_elements_without_role(
                    queryset, Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT, actor.role
                )

                return queryset
            else:
                return self.exclude_elements_with_visibility(
                    queryset, Element.VISIBILITY_TYPES.LOGGED_IN
                )
        elif operation_name == ListBuilderWorkflowActionsPageOperationType.type:
            queryset = self.exclude_elements_with_page_visibility(queryset, actor)

            prefix = "element__"
            if getattr(actor, "is_authenticated", False):
                queryset = self.exclude_elements_with_visibility(
                    queryset, Element.VISIBILITY_TYPES.NOT_LOGGED, prefix=prefix
                )
                queryset = self.exclude_elements_with_role(
                    queryset,
                    Element.ROLE_TYPES.ALLOW_ALL_EXCEPT,
                    actor.role,
                    prefix=prefix,
                )
                queryset = self.exclude_elements_without_role(
                    queryset,
                    Element.ROLE_TYPES.DISALLOW_ALL_EXCEPT,
                    actor.role,
                    prefix=prefix,
                )

                return queryset
            else:
                return self.exclude_elements_with_visibility(
                    queryset, Element.VISIBILITY_TYPES.LOGGED_IN, prefix=prefix
                )

        return queryset
