from urllib.request import Request

from django.conf import settings
from django.http import FileResponse
from django.utils.encoding import smart_str

from baserow_premium.license.exceptions import FeaturesNotAvailableError
from baserow_premium.license.handler import LicenseHandler
from drf_spectacular.utils import extend_schema
from rest_framework.renderers import BaseRenderer
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow_enterprise.api.authentication import (
    AuthenticateFromUserSessionAuthentication,
)
from baserow_enterprise.features import SECURE_FILE_SERVE
from baserow_enterprise.secure_file_serve.constants import SecureFileServePermission
from baserow_enterprise.secure_file_serve.exceptions import SecureFileServeException
from baserow_enterprise.secure_file_serve.handler import SecureFileServeHandler

from .errors import ERROR_SECURE_FILE_SERVE_EXCEPTION


class BinaryRenderer(BaseRenderer):
    media_type = "application/octet-stream"
    format = "bin"
    charset = None
    render_style = "binary"

    def render(self, data, accepted_media_type=None, renderer_context=None):
        return data


class DownloadView(APIView):
    permission_classes = []

    @property
    def authentication_classes(self):
        if (
            settings.BASEROW_SERVE_FILES_THROUGH_BACKEND_PERMISSION
            != SecureFileServePermission.DISABLED
        ):
            return [AuthenticateFromUserSessionAuthentication]
        else:
            return []

    renderer_classes = [BinaryRenderer]

    @extend_schema(
        tags=["Secure file serve"],
        operation_id="secure_file_serve_download",
        description=(
            "Downloads a file using the backend and the secure file serve feature. "
            "The signed data is extracted from the URL and used to verify if the "
            "user has access to the file. If the permissions check passes and the "
            "file exists, the file is served to the user."
            "\n\nThis is a **enterprise** feature."
        ),
        responses={
            200: {"description": "File download"},
            403: get_error_schema(["ERROR_SECURE_FILE_SERVE_EXCEPTION"]),
        },
        auth=[],
    )
    @map_exceptions(
        {
            SecureFileServeException: ERROR_SECURE_FILE_SERVE_EXCEPTION,
        }
    )
    def get(self, request: Request, signed_data: str) -> FileResponse:
        if not LicenseHandler.instance_has_feature(SECURE_FILE_SERVE):
            raise FeaturesNotAvailableError()

        secure_file = SecureFileServeHandler().extract_file_info_or_raise(
            request.user, signed_data
        )

        download_file_name = request.GET.get("dl", "")
        as_attachment = bool(download_file_name)

        return FileResponse(
            secure_file.open(),
            as_attachment=as_attachment,
            filename=smart_str(download_file_name or secure_file.name),
        )
