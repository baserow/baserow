from typing import Dict
from urllib.request import Request

from django.db import transaction

from baserow_premium.api.views.errors import (
    ERROR_CANNOT_UPDATE_PREMIUM_ATTRIBUTES_ON_TEMPLATE,
)
from baserow_premium.api.views.exceptions import CannotUpdatePremiumAttributesOnTemplate
from baserow_premium.api.views.serializers import UpdatePremiumViewAttributesSerializer
from baserow_premium.api.views.signers import export_public_view_signer
from baserow_premium.license.features import PREMIUM
from baserow_premium.license.handler import LicenseHandler
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from itsdangerous.exc import BadData
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.schemas import get_error_schema
from baserow.contrib.database.api.export.errors import ERROR_EXPORT_JOB_DOES_NOT_EXIST
from baserow.contrib.database.api.export.serializers import ExportJobSerializer
from baserow.contrib.database.api.export.views import (
    CreateExportJobSerializer,
    _validate_options,
)
from baserow.contrib.database.api.fields.errors import (
    ERROR_FILTER_FIELD_NOT_FOUND,
    ERROR_ORDER_BY_FIELD_NOT_FOUND,
    ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
)
from baserow.contrib.database.api.views.errors import (
    ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    ERROR_VIEW_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
    ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
)
from baserow.contrib.database.api.views.serializers import ViewSerializer
from baserow.contrib.database.api.views.utils import get_public_view_authorization_token
from baserow.contrib.database.export.exceptions import ExportJobDoesNotExistException
from baserow.contrib.database.export.handler import ExportHandler
from baserow.contrib.database.export.models import ExportJob
from baserow.contrib.database.fields.exceptions import (
    FilterFieldNotFound,
    OrderByFieldNotFound,
    OrderByFieldNotPossible,
)
from baserow.contrib.database.views.actions import UpdateViewActionType
from baserow.contrib.database.views.exceptions import (
    NoAuthorizationToPubliclySharedView,
    ViewDoesNotExist,
    ViewFilterTypeDoesNotExist,
    ViewFilterTypeNotAllowedForField,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.registries import view_type_registry
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import UserNotInWorkspace


class PremiumViewAttributesView(APIView):
    """
    This view allows premium users to override attributes on a view which are only
    accessible to premium users. For example the logo can be hidden.
    """

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="view_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Sets show_logo of this view.",
            ),
        ],
        tags=["Database table views"],
        operation_id="premium_view_attributes_update",
        description="Sets view attributes only available for premium users.",
        request=UpdatePremiumViewAttributesSerializer,
        responses={
            200: ViewSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_FEATURE_NOT_AVAILABLE",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_CANNOT_UPDATE_PREMIUM_ATTRIBUTES_ON_TEMPLATE",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            CannotUpdatePremiumAttributesOnTemplate: ERROR_CANNOT_UPDATE_PREMIUM_ATTRIBUTES_ON_TEMPLATE,  # noqa
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
        }
    )
    @validate_body(UpdatePremiumViewAttributesSerializer)
    def patch(
        self,
        request: Request,
        view_id: int,
        data: Dict[str, any],
    ) -> Response:
        """
        Sets view attributes only available for premium users.
        """

        view_handler = ViewHandler()
        view = view_handler.get_view(view_id).specific
        workspace = view.table.database.workspace

        if workspace.has_template():
            raise CannotUpdatePremiumAttributesOnTemplate()

        LicenseHandler.raise_if_user_doesnt_have_feature(
            PREMIUM, request.user, workspace
        )

        view_type = view_type_registry.get_by_model(view)

        with view_type.map_api_exceptions():
            view = action_type_registry.get_by_type(UpdateViewActionType).do(
                request.user, view, **data
            )

        serializer = view_type_registry.get_serializer(
            view, ViewSerializer, context={"user": request.user}
        )
        return Response(serializer.data)


class ExportPublicViewView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Select the view you want to export.",
            ),
        ],
        tags=["Database table view export"],
        operation_id="export_publicly_shared_view",
        description=(
            "Creates and starts a new export job for a publicly shared view  given "
            "some exporter options. Returns an error if the view doesn't support "
            "exporting."
            "\n\nThis is a **premium** feature."
        ),
        request=CreateExportJobSerializer,
        responses={
            200: ExportJobSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_TABLE_ONLY_EXPORT_UNSUPPORTED",
                    "ERROR_VIEW_UNSUPPORTED_FOR_EXPORT_TYPE",
                    "ERROR_VIEW_NOT_IN_TABLE",
                    "ERROR_FILTER_FIELD_NOT_FOUND",
                    "ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST",
                    "ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD",
                    "ERROR_ORDER_BY_FIELD_NOT_FOUND",
                    "ERROR_ORDER_BY_FIELD_NOT_POSSIBLE",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
            FilterFieldNotFound: ERROR_FILTER_FIELD_NOT_FOUND,
            ViewFilterTypeDoesNotExist: ERROR_VIEW_FILTER_TYPE_DOES_NOT_EXIST,
            ViewFilterTypeNotAllowedForField: ERROR_VIEW_FILTER_TYPE_UNSUPPORTED_FIELD,
            OrderByFieldNotFound: ERROR_ORDER_BY_FIELD_NOT_FOUND,
            OrderByFieldNotPossible: ERROR_ORDER_BY_FIELD_NOT_POSSIBLE,
        }
    )
    def post(self, request, slug):
        """
        Starts a new export job for the provided table, view, export type and options.
        """

        view_handler = ViewHandler()
        authorization_token = get_public_view_authorization_token(request)
        view = view_handler.get_public_view_by_slug(
            request.user, slug, authorization_token=authorization_token
        ).specific
        table = view.table
        option_data = _validate_options(request.data)

        # Delete the provided view ID because it can be identified using the slug
        # path parameter.
        del option_data["view_id"]

        job = ExportHandler.create_and_start_new_job(None, table, view, option_data)
        serialized_job = ExportJobSerializer(job).data
        serialized_job["id"] = export_public_view_signer.dumps(serialized_job["id"])
        return Response(serialized_job)


class ExportPublicViewJobView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="job_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="The signed job id to lookup information about.",
            )
        ],
        tags=["Database table view export"],
        operation_id="get_public_view_export_job",
        description=(
            "Returns information such as export progress and state or the url of the "
            "exported file for the specified export job, only if the requesting user "
            "has access."
            "\n\nThis is a **premium** feature."
        ),
        request=None,
        responses={
            200: ExportJobSerializer,
            404: get_error_schema(["ERROR_EXPORT_JOB_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ExportJobDoesNotExistException: ERROR_EXPORT_JOB_DOES_NOT_EXIST,
            BadData: ERROR_EXPORT_JOB_DOES_NOT_EXIST,
        }
    )
    def get(self, request, job_id):
        """Retrieves the specified export job by serialized id."""

        job_id = export_public_view_signer.loads(job_id)

        try:
            job = ExportJob.objects.get(id=job_id, user=None)
        except ExportJob.DoesNotExist:
            raise ExportJobDoesNotExistException()

        serialized_job = ExportJobSerializer(job).data
        serialized_job["id"] = export_public_view_signer.dumps(serialized_job["id"])
        return Response(serialized_job)
