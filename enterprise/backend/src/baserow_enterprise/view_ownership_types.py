from django.contrib.auth.models import AbstractUser

from baserow_premium.license.handler import LicenseHandler

from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.operations import CreateViewFilterOperationType
from baserow.contrib.database.views.registries import ViewOwnershipType
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import RBAC


class RestrictedViewOwnershipType(ViewOwnershipType):
    """
    Represents view that are shared between all users, but users without the
    permissions to create/update/delete filters will not be able to see the rows not
    matching the filters. This is used to give some users only access to part of the
    rows in a table.
    """

    type = "restricted"

    def change_ownership_type(self, user: AbstractUser, view: View) -> View:
        # It's not possible to change to and from restricted view type because that
        # could accidentally expose or restrict data.
        raise PermissionDenied()

    def view_created(self, user: AbstractUser, view: "View", workspace: Workspace):
        LicenseHandler.raise_if_user_doesnt_have_feature(RBAC, user, workspace)

    def enforce_apply_filters(self, user, view):
        # If the user does not have permissions to create filters in the view, then it
        # means that the user has the editor role or lower. In that case, the user might
        # not have access to the full table, so the view filters are enforced. The user
        # can't change the view filters and can't see them, so they will only have
        # access to the filtered data. This allows giving the user only access to the
        # desired rows.
        return user is not None and not CoreHandler().check_permissions(
            user,
            CreateViewFilterOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
            raise_permission_exceptions=False,
        )

    def prepare_views_for_user(self, user, views):
        if len(views) == 0 or user is None:
            return views

        permission_checks = {}
        for view in views:
            permission_checks[view.id] = PermissionCheck(
                user,
                CreateViewFilterOperationType.type,
                context=view,
            )

        check_results = CoreHandler().check_multiple_permissions(
            permission_checks.values(), workspace=views[0].table.database.workspace
        )

        for view in views:
            check_result = check_results[permission_checks[view.id]]
            # If the user does not have create view filter permissions for the provided
            # view, then the filters are omitted because the they're forcefully applied
            # so that the user can only see the rows that match the filter.
            if not check_result:
                if not hasattr(view, "_prefetched_objects_cache"):
                    view._prefetched_objects_cache = {}
                view._prefetched_objects_cache["viewfilter_set"] = []
                view._prefetched_objects_cache["filter_groups"] = []

        return views

    def can_modify_rows(self, view, row_ids=None):
        if not row_ids:
            return True

        # Check if all the provided row_ids actually exist in the filtered queryset.
        # We don't want to allow modifying rows that are outside the filters because
        # that is not where the user has access to.
        model = view.table.get_model()
        filter_qs = ViewHandler().apply_filters(view, model.objects)
        rows_in_view = filter_qs.filter(id__in=row_ids).values("id")
        rows_outside_view = model.objects.filter(id__in=row_ids).exclude(
            id__in=rows_in_view
        )
        return not rows_outside_view.exists()
