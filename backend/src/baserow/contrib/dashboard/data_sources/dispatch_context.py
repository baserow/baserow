from typing import TYPE_CHECKING, Optional

from django.http import HttpRequest

from baserow.core.services.dispatch_context import DispatchContext

if TYPE_CHECKING:
    from baserow.contrib.dashboard.widgets.models import Widget


class DashboardDispatchContext(DispatchContext):
    own_properties = [
        "widget",
    ]

    def __init__(
        self,
        request: HttpRequest,
        widget: Optional["Widget"] = None,
    ):
        self.request = request
        self.widget = widget

        super().__init__()

    def range(self, service):
        offset, count = 0, None
        return [offset, count]

    def is_publicly_searchable(self):
        return False

    def search_query(self):
        return None

    def searchable_fields(self):
        return []

    def is_publicly_filterable(self):
        return False

    def filters(self):
        return None

    def is_publicly_sortable(self):
        return False

    def sortings(self):
        return None

    def public_allowed_properties(self):
        return None

    def validate_filter_search_sort_fields(self):
        ...
