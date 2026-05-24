from typing import List, Optional, Set

from django.contrib.auth.models import AbstractUser
from django.db.models import QuerySet

from baserow.contrib.database.table.models import Table
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.operations import (
    CreateViewFilterOperationType,
    ReadViewDefaultValuesOperationType,
    ReadViewRowCommentsOperationType,
    UpdateViewFieldOptionsOperationType,
)
from baserow.contrib.database.views.registries import (
    ViewOwnershipType,
    view_type_registry,
)
from baserow.contrib.database.views.row_checker import FilteredViewRowChecker
from baserow.contrib.database.views.view_types import FormViewType
from baserow.core.exceptions import PermissionDenied
from baserow.core.handler import CoreHandler
from baserow.core.models import Workspace
from baserow.core.types import PermissionCheck
from baserow_enterprise.features import RBAC
from baserow_premium.license.handler import LicenseHandler


class RestrictedViewOwnershipType(ViewOwnershipType):
    """
    Represents view that are shared between all users, but users without the
    permissions to create/update/delete filters will not be able to see the rows not
    matching the filters. This is used to give some users only access to part of the
    rows in a table.
    """

    type = "restricted"

    def is_compatible_with_view_type(self, view_type) -> bool:
        # The form view is not related to showing data, so it does not make any sense to
        # have a restricted view ownership type.
        return view_type.type != FormViewType.type

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

    def get_hidden_field_ids_for_user(
        self, user: Optional[AbstractUser], view: View
    ) -> Set[int]:
        if user is None:
            return set()
        if CoreHandler().check_permissions(
            user,
            UpdateViewFieldOptionsOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
            raise_permission_exceptions=False,
        ):
            return set()
        view_type = view_type_registry.get_by_model(view.specific_class)
        return view_type.get_hidden_fields(view.specific)

    def prepare_views_for_user(
        self,
        user: Optional["AbstractUser"],
        views: List["View"],
        includes: Optional[Set[str]] = None,
    ) -> List["View"]:
        if len(views) == 0 or user is None:
            return views

        include_default_row_values = (
            includes is None or "default_row_values" in includes
        )
        include_sortings = includes is None or "sortings" in includes
        include_group_bys = includes is None or "group_bys" in includes
        include_decorations = includes is None or "decorations" in includes

        permission_checks = {}
        for view in views:
            permission_checks[f"filter{view.id}"] = PermissionCheck(
                user,
                CreateViewFilterOperationType.type,
                context=view,
            )
            permission_checks[f"update_field_options{view.id}"] = PermissionCheck(
                user,
                UpdateViewFieldOptionsOperationType.type,
                context=view,
            )
            if include_default_row_values:
                permission_checks[f"read_default_values{view.id}"] = PermissionCheck(
                    user,
                    ReadViewDefaultValuesOperationType.type,
                    context=view,
                )

        check_results = CoreHandler().check_multiple_permissions(
            permission_checks.values(), workspace=views[0].table.database.workspace
        )

        for view in views:
            if not hasattr(view, "_prefetched_objects_cache"):
                view._prefetched_objects_cache = {}

            filter_check_result = check_results[permission_checks[f"filter{view.id}"]]
            # If the user does not have create view filter permissions for the provided
            # view, then the filters are omitted because they're forcefully applied
            # so that the user can only see the rows that match the filter.
            if not filter_check_result:
                view._prefetched_objects_cache["viewfilter_set"] = []
                view._prefetched_objects_cache["filter_groups"] = []

            field_options_check_result = check_results[
                permission_checks[f"update_field_options{view.id}"]
            ]
            # If the user does not have update field options permissions for the
            # provided view, then the hidden fields are omitted because they should not
            # be exposed to the user.
            if not field_options_check_result:
                # Cache hidden field IDs to avoid repeated permission checks.
                view_type = view_type_registry.get_by_model(view.specific_class)
                # This could cause N number of queries, but if the views are fetched
                # using the `ViewHandler::list_views`, which is used when listing the
                # views via the API, it won't be a problem because everything is then
                # prefetched.
                hidden_field_ids = view_type.get_hidden_fields(view.specific)
                view._hidden_field_ids = hidden_field_ids

                # Remove sorts and group_bys that reference hidden fields so
                # that editors don't see them in the API response.
                if hidden_field_ids:
                    if include_sortings:
                        if "viewsort_set" not in view._prefetched_objects_cache:
                            view._prefetched_objects_cache["viewsort_set"] = list(
                                view.viewsort_set.all()
                            )
                        view._prefetched_objects_cache["viewsort_set"] = [
                            s
                            for s in view._prefetched_objects_cache["viewsort_set"]
                            if s.field_id not in hidden_field_ids
                        ]

                    if include_group_bys:
                        if "viewgroupby_set" not in view._prefetched_objects_cache:
                            view._prefetched_objects_cache["viewgroupby_set"] = list(
                                view.viewgroupby_set.all()
                            )
                        view._prefetched_objects_cache["viewgroupby_set"] = [
                            g
                            for g in view._prefetched_objects_cache["viewgroupby_set"]
                            if g.field_id not in hidden_field_ids
                        ]

                    if include_decorations:
                        # Remove all decorations for editors because decorations
                        # may have conditions referencing hidden fields, which
                        # would cause errors on the frontend.
                        view._prefetched_objects_cache["viewdecoration_set"] = []
            else:
                view._hidden_field_ids = None
                hidden_field_ids = set()

            # Determine which default row values to expose based on the user's
            # permissions. Builders and admins (who have UpdateViewFieldOptions) can
            # see all default values. Editors (who have ReadViewDefaultValues) can
            # see default values for visible fields only. Commenters and viewers
            # cannot see any default values.
            if include_default_row_values:
                if field_options_check_result:
                    # Builder or admin: expose all default values.
                    pass
                elif check_results[permission_checks[f"read_default_values{view.id}"]]:
                    # Editor: expose default values for visible fields only.
                    if hidden_field_ids:
                        if "view_default_values" not in view._prefetched_objects_cache:
                            view._prefetched_objects_cache["view_default_values"] = (
                                list(view.view_default_values.all())
                            )
                        view._prefetched_objects_cache["view_default_values"] = [
                            default_value
                            for default_value in view._prefetched_objects_cache[
                                "view_default_values"
                            ]
                            if default_value.field_id not in hidden_field_ids
                        ]
                else:
                    # Commenter or viewer: no default values.
                    view._prefetched_objects_cache["view_default_values"] = []

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

    def get_users_to_notify_for_row_comment(
        self,
        table: Table,
        row_id: int,
        users: List[AbstractUser],
    ) -> List[AbstractUser]:
        if not users:
            return []

        # Fetch all restricted views for this table in one query, with filters
        # prefetched so FilteredViewRowChecker can work efficiently.
        restricted_views_qs = (
            View.objects.filter(table=table, ownership_type=self.type)
            .select_related("table")
            .prefetch_related("viewfilter_set", "filter_groups", "table__field_set")
        )

        # Use FilteredViewRowChecker to determine in a single bulk query which
        # restricted views the commented row is visible in. When there are no restricted
        # views the checker will simply produce no results.
        model = table.get_model()
        checker = FilteredViewRowChecker(
            model,
            restricted_views_qs,
            only_include_views_which_want_realtime_events=False,
        )

        try:
            row = model.objects.get(id=row_id)
        except model.DoesNotExist:
            return []

        visible_views = checker.get_filtered_views_where_row_is_visible(row)
        if not visible_views:
            return []

        # Check ReadViewRowCommentsOperationType for each remaining user on each view
        # where the row is visible, in a single bulk call.
        workspace = table.database.workspace
        checks = []
        check_to_user = {}
        for user in users:
            for view in visible_views:
                check = PermissionCheck(
                    user, ReadViewRowCommentsOperationType.type, view
                )
                checks.append(check)
                check_to_user[check] = user

        check_results = CoreHandler().check_multiple_permissions(
            checks, workspace=workspace
        )

        allowed_user_ids = set()
        additional_users = []
        for check, result in check_results.items():
            if result is True:
                user = check_to_user[check]
                if user.id not in allowed_user_ids:
                    allowed_user_ids.add(user.id)
                    additional_users.append(user)

        return additional_users

    def enhance_list_fields_queryset(
        self, user: AbstractUser, view: View, queryset: QuerySet
    ) -> QuerySet:
        if CoreHandler().check_permissions(
            user,
            UpdateViewFieldOptionsOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
            raise_permission_exceptions=False,
        ):
            return queryset

        view_type = view_type_registry.get_by_model(view.specific_class)
        hidden_field_ids = view_type.get_hidden_fields(view.specific)
        if hidden_field_ids:
            return queryset.exclude(id__in=hidden_field_ids)
        return queryset
