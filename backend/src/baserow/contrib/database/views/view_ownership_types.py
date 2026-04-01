from typing import List, Optional, Set

from django.contrib.auth.models import AbstractUser

from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.operations import (
    ReadViewDefaultValuesOperationType,
    UpdateViewOperationType,
)
from baserow.contrib.database.views.registries import ViewOwnershipType
from baserow.core.handler import CoreHandler


class CollaborativeViewOwnershipType(ViewOwnershipType):
    """
    Represents views that are shared between all users that can access
    a specific table.
    """

    type = "collaborative"

    def change_ownership_type(self, user: AbstractUser, view: View) -> View:
        view.ownership_type = self.type
        # The previous permission check (when updating the view) was done using
        # the old ownership_type. Verify that the user has permission to update
        # the view with the new one as well:
        CoreHandler().check_permissions(
            user,
            UpdateViewOperationType.type,
            workspace=view.table.database.workspace,
            context=view,
        )
        view.owned_by = user
        return view

    def prepare_views_for_user(
        self,
        user: Optional[AbstractUser],
        views: List[View],
        includes: Optional[Set[str]] = None,
    ) -> List[View]:
        if not views or user is None:
            return views

        # Skip work entirely when default_row_values is not requested.
        if includes is not None and "default_row_values" not in includes:
            return views

        # All collaborative views in the same table share the same permissions,
        # so a single check using the first view is sufficient.
        can_read_default_values = CoreHandler().check_permissions(
            user,
            ReadViewDefaultValuesOperationType.type,
            workspace=views[0].table.database.workspace,
            context=views[0],
            raise_permission_exceptions=False,
        )
        for view in views:
            if not hasattr(view, "_prefetched_objects_cache"):
                view._prefetched_objects_cache = {}
            if not can_read_default_values:
                view._prefetched_objects_cache["view_default_values"] = []
            elif "view_default_values" not in view._prefetched_objects_cache:
                view._prefetched_objects_cache["view_default_values"] = list(
                    view.view_default_values.all()
                )

        return views
