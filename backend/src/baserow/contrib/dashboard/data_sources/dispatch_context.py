from typing import TYPE_CHECKING, Optional

from django.http import HttpRequest

from baserow.core.services.dispatch_context import DispatchContext

if TYPE_CHECKING:
    from baserow.contrib.dashboard.widgets.models import Widget


class DashboardDispatchContext(DispatchContext):
    own_properties = [
        "request",
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
