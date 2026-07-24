from urllib.parse import urljoin

from django.conf import settings

from rest_framework.request import Request

from baserow.contrib.database.api.views.errors import (
    ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    ERROR_VIEW_DOES_NOT_EXIST,
)
from baserow.contrib.database.api.views.utils import get_public_view_authorization_token
from baserow.contrib.database.views.exceptions import (
    NoAuthorizationToPubliclySharedView,
    ViewDoesNotExist,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import View
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.abuse_reports.registries import (
    AbuseReportResourceType,
    ReportedResource,
)


class DatabaseViewAbuseReportResourceType(AbuseReportResourceType):
    type = "database_view"
    api_exceptions_map = {
        ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
        NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    }

    def resolve(self, request: Request, identifier: str) -> ReportedResource:
        view = ViewHandler().get_public_view_by_slug(
            request.user,
            identifier,
            authorization_token=get_public_view_authorization_token(request),
        )
        if not view.public:
            raise ViewDoesNotExist("The view is not publicly shared.")
        return ReportedResource(
            resource_id=view.id,
            name=view.name,
            workspace=view.table.database.workspace,
            public_url=self._get_public_url(view),
        )

    def _get_public_url(self, view: View) -> str:
        view_type = view_type_registry.get_by_model(view.specific_class)
        base_url = (
            settings.BASEROW_EMBEDDED_SHARE_URL or settings.PUBLIC_WEB_FRONTEND_URL
        )
        return urljoin(base_url, view_type.get_public_url_path(view))
