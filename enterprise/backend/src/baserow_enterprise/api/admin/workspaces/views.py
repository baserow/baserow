from drf_spectacular.utils import extend_schema
from rest_framework.permissions import IsAdminUser

from baserow.api.admin.views import APIListingView
from baserow.core.models import Workspace

from .serializers import AdminWorkspaceSerializer


class AdminWorkspaceListView(APIListingView):
    permission_classes = (IsAdminUser,)
    serializer_class = AdminWorkspaceSerializer
    search_fields = ["name"]
    default_order_by = "name"

    def get_queryset(self, request):
        return Workspace.objects.filter(template__isnull=True)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_list_workspaces_as_options",
        description=(
            "Lists all workspaces. This endpoint is intended for admin-level "
            "features that need a workspace picker (e.g. audit log, data scanner)."
        ),
        **APIListingView.get_extend_schema_parameters(
            "workspaces", serializer_class, search_fields, {}
        ),
    )
    def get(self, request):
        return super().get(request)
