from functools import partial
from typing import TYPE_CHECKING, Any, Dict, List, Optional, Union

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet

from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.views.models import OWNERSHIP_TYPE_PERSONAL

from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.operations import (
    CanReceiveNotificationOnSubmitFormViewOperationType,
    CreateAndUsePersonalViewOperationType,
    CreateViewDecorationOperationType,
    CreateViewFilterGroupOperationType,
    CreateViewFilterOperationType,
    CreateViewGroupByOperationType,
    CreateViewRowOperationType,
    CreateViewSortOperationType,
    DeleteViewDecorationOperationType,
    DeleteViewFilterGroupOperationType,
    DeleteViewFilterOperationType,
    DeleteViewGroupByOperationType,
    DeleteViewOperationType,
    DeleteViewRowOperationType,
    DeleteViewSortOperationType,
    DuplicateViewOperationType,
    ListAggregationsViewOperationType,
    ListViewDecorationOperationType,
    ListViewFilterOperationType,
    ListViewGroupByOperationType,
    ListViewsOperationType,
    ListViewSortOperationType,
    ReadAggregationsViewOperationType,
    ReadViewDecorationOperationType,
    ReadViewFieldOptionsOperationType,
    ReadViewFilterGroupOperationType,
    ReadViewFilterOperationType,
    ReadViewGroupByOperationType,
    ReadViewOperationType,
    ReadViewRowOperationType,
    ReadViewSortOperationType,
    RestoreViewOperationType,
    UpdateViewDecorationOperationType,
    UpdateViewFieldOptionsOperationType,
    UpdateViewFilterGroupOperationType,
    UpdateViewFilterOperationType,
    UpdateViewGroupByOperationType,
    UpdateViewOperationType,
    UpdateViewPublicOperationType,
    UpdateViewRowOperationType,
    UpdateViewSlugOperationType,
    UpdateViewSortOperationType,
)
from baserow.core.cache import local_cache
from baserow.core.exceptions import PermissionDenied, PermissionException
from baserow.core.handler import CoreHandler
from baserow.core.registries import PermissionManagerType, object_scope_type_registry
from baserow.core.subjects import UserSubjectType
from baserow.core.types import Actor, PermissionCheck

User = get_user_model()


if TYPE_CHECKING:
    from django.contrib.auth.models import AbstractUser

    from baserow.core.models import Workspace


class ViewOwnershipPermissionManagerType(PermissionManagerType):
    type = "view_ownership"
    supported_actor_types = [UserSubjectType.type]

    def __init__(self):
        # Background: Baserow can be configured using
        # BASEROW_PERSONAL_VIEW_LOWEST_ROLE_ALLOWED to allow viewers and/or commenters
        # and/or editors to make their own personal views. This permission manager
        # has logic that allows these users to perform operations they normally wouldn't
        # be able to, IF they are performing them on their own personal views AND the
        # operation is a safe one to allow them to do (it doesn't allow them to edit
        # or expose the data in anyway).
        #
        # Only add operations to the list below if it is fine for a viewer who has
        # made their own personal view to be able to execute that operation on their
        # own personal view even if that user is only a viewer on the table itself.
        #
        # Some operations on views should never be executable for
        # a viewer/commenter/editor on their own personal view, such as publicly
        # sharing that view. If your new operation is like that, see the second list
        # below.
        self.view_ops_allowed_on_own_accessible_personal_view = [
            CreateViewSortOperationType.type,
            ReadViewSortOperationType.type,
            UpdateViewSortOperationType.type,
            UpdateViewFieldOptionsOperationType.type,
            DeleteViewSortOperationType.type,
            ReadViewOperationType.type,
            UpdateViewOperationType.type,
            CanReceiveNotificationOnSubmitFormViewOperationType.type,
            DeleteViewOperationType.type,
            DuplicateViewOperationType.type,
            CreateViewFilterOperationType.type,
            ReadViewFilterOperationType.type,
            UpdateViewFilterOperationType.type,
            DeleteViewFilterOperationType.type,
            CreateViewGroupByOperationType.type,
            ReadViewGroupByOperationType.type,
            UpdateViewGroupByOperationType.type,
            DeleteViewGroupByOperationType.type,
            RestoreViewOperationType.type,
            ReadAggregationsViewOperationType.type,
            ListAggregationsViewOperationType.type,
            ListViewFilterOperationType.type,
            ListViewSortOperationType.type,
            ListViewGroupByOperationType.type,
            ReadViewFieldOptionsOperationType.type,
            CreateViewFilterGroupOperationType.type,
            ReadViewFilterGroupOperationType.type,
            UpdateViewFilterGroupOperationType.type,
            DeleteViewFilterGroupOperationType.type,
            CreateViewDecorationOperationType.type,
            UpdateViewDecorationOperationType.type,
            DeleteViewDecorationOperationType.type,
            ReadViewRowOperationType.type,
            CreateViewRowOperationType.type,
            UpdateViewRowOperationType.type,
            DeleteViewRowOperationType.type,
        ]
        # This list controls operations that for personal views, should only be allowed
        # to be performed by the creator of the personal view BUT should only be
        # allowed if the user can normally perform that operation on a normal
        # collaborative view.
        #
        # For example, we don't ever want someone who can make a personal view to be
        # able to share that view publicly
        self.view_ops_allowed_only_if_user_has_underlying_permission = [
            UpdateViewSlugOperationType.type,
            UpdateViewPublicOperationType.type,
            # Don't allow viewers to make view decorations as premium feature
            ListViewDecorationOperationType.type,
            CreateViewDecorationOperationType.type,
            ReadViewDecorationOperationType.type,
            UpdateViewDecorationOperationType.type,
            DeleteViewDecorationOperationType.type,
        ]
        self.ops_checked_by_this_manager = (
            self.view_ops_allowed_on_own_accessible_personal_view
            + self.view_ops_allowed_only_if_user_has_underlying_permission
        )

        super().__init__()

    def get_permissions_object(
        self, actor: Actor, workspace: Optional["Workspace"] = None
    ) -> Any:
        # For the frontend to run permission management checks for this manager
        # we need to return anything from this function.
        return {}

    def check_multiple_permissions(
        self,
        checks: List[PermissionCheck],
        workspace: "Workspace",
        include_trash: bool = False,
    ) -> Dict[PermissionCheck, Union[bool, PermissionException]]:
        """
        check_multiple_permissions() impl for view ownership checks.

        There are other instances that this method cannot check:
        - CreateViewDecorationOperationType is currently implemented via view_created
          signal since the permission system doesn't allow to pass richer context.
        - ListViewsOperationType and ReadViewsOrderOperationType operations invoke
          filter_queryset() method and hence don't need to be checked.
        """

        result_by_check = {}
        for check in checks:
            actor, operation_name, context = check
            if (
                operation_name not in self.ops_checked_by_this_manager
                or not workspace
                or not context
            ):
                continue

            premium = local_cache.get(
                f"has_premium_permission_{actor.id}_{workspace.id}",
                partial(LicenseHandler.user_has_feature, PREMIUM, actor, workspace),
            )

            view_scope_type = object_scope_type_registry.get("database_view")
            view = object_scope_type_registry.get_parent(
                context, at_scope_type=view_scope_type
            )

            if premium:
                if view.ownership_type == OWNERSHIP_TYPE_PERSONAL:
                    if view.owned_by_id != actor.id:
                        result_by_check[check] = PermissionDenied(
                            "The user doesn't own this personal view"
                        )
                    elif (
                        operation_name
                        in self.view_ops_allowed_on_own_accessible_personal_view
                    ):
                        # We have premium and the user is trying to do something to
                        # their own personal view. However, we can't just pass through
                        # the check to lower permission managers as they do not know
                        # that an editor should be able to update only their own
                        # personal views. Instead, we replace the operation being
                        # check with the
                        # CreateAndUsePersonalViewOperationType and recursively check
                        # that the user has this operation.
                        #
                        # This way we ensure the user still
                        # actually is an editor/commenter/viewer on the table but still
                        # allow them to do these operations they don't normally have
                        # on their own personal view.
                        result_by_check[check] = CoreHandler().check_permissions(
                            actor,
                            CreateAndUsePersonalViewOperationType.type,
                            workspace,
                            view.table,
                            include_trash=include_trash,
                            raise_permission_exceptions=False,
                        )
                    else:
                        # The user is trying to perform an operation on their personal
                        # view, but these operations we only want to allow if they
                        # actually have the permission for that operation on normal
                        # views also. So we don't set a result in result_by_check and
                        # allow the lower permission managers to take over and decide.
                        #
                        # We want to do this for some operations as they are dangerous
                        # and should not be allowed by everyone who can make personal
                        # views. For example a editor of a table
                        # should not be able to share their personal views publicly
                        # but a builder of a table should be able to.
                        pass
            else:
                if view.ownership_type == OWNERSHIP_TYPE_PERSONAL:
                    result_by_check[check] = PermissionDenied(
                        "The user doesn't have the authorization to see personal views"
                    )

        return result_by_check

    def filter_queryset(
        self,
        actor: "AbstractUser",
        operation_name: str,
        queryset: QuerySet,
        workspace: Optional["Workspace"] = None,
    ) -> QuerySet:
        """
        filter_queryset() impl for view ownership filtering.

        :param actor: The actor whom we want to filter the queryset for.
            Generally a `User` but can be a Token.
        :param operation: The operation name for which we want to filter the queryset
            for.
        :param workspace: An optional workspace into which the operation takes place.
        :param context: An optional context object related to the current operation.
        :return: The queryset potentially filtered.
        """

        if not isinstance(actor, User):
            return queryset

        if operation_name != ListViewsOperationType.type:
            return queryset

        if not workspace:
            return queryset

        premium = local_cache.get(
            f"has_premium_permission_{actor.id}_{workspace.id}",
            lambda: LicenseHandler.user_has_feature(PREMIUM, actor, workspace),
        )

        if premium:
            allowed_tables = CoreHandler().filter_queryset(
                actor,
                CreateAndUsePersonalViewOperationType.type,
                Table.objects.filter(database__workspace=workspace),
                workspace=workspace,
            )

            return queryset.filter(
                ~Q(ownership_type=OWNERSHIP_TYPE_PERSONAL)
                | (
                    Q(ownership_type=OWNERSHIP_TYPE_PERSONAL)
                    & Q(owned_by=actor)
                    & Q(table__in=allowed_tables)
                )
            )
        else:
            return queryset.exclude(ownership_type=OWNERSHIP_TYPE_PERSONAL)
