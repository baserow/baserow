from rest_framework.permissions import BasePermission

from baserow.contrib.dashboard.models import Dashboard


class IsAuthenticatedOrTemplateDashboardRead(BasePermission):
    """
    Lets signed-out visitors read the dashboard of a template workspace, so that a
    wrong permission manager answer can't expose any other dashboard.
    """

    def has_permission(self, request, view):
        if request.user and request.user.is_authenticated:
            return True
        if request.method != "GET":
            return False

        dashboard = (
            Dashboard.objects.select_related("workspace")
            .filter(id=view.kwargs["dashboard_id"])
            .first()
        )
        return bool(
            dashboard
            and dashboard.workspace
            and dashboard.workspace.get_template_types()
        )
