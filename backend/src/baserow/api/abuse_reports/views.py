from django.db import transaction

from drf_spectacular.utils import extend_schema
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.status import HTTP_204_NO_CONTENT
from rest_framework.views import APIView

from baserow.api.captcha.errors import ERROR_CAPTCHA_VERIFICATION_FAILED
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.schemas import get_error_schema
from baserow.core.abuse_reports.actions import SubmitAbuseReportActionType
from baserow.core.abuse_reports.exceptions import AbuseReportingDisabledException
from baserow.core.abuse_reports.registries import abuse_report_resource_type_registry
from baserow.core.action.registries import action_type_registry
from baserow.core.captcha.exceptions import CaptchaVerificationFailed
from baserow.core.captcha.handler import CaptchaHandler
from baserow.core.handler import CoreHandler
from baserow.core.utils import get_user_remote_ip_address_from_request

from .errors import ERROR_ABUSE_REPORTING_DISABLED
from .serializers import AbuseReportSerializer
from .throttling import AbuseReportRateThrottle


class AbuseReportsView(APIView):
    permission_classes = (AllowAny,)
    throttle_classes = (AbuseReportRateThrottle,)

    @extend_schema(
        tags=["Abuse reports"],
        operation_id="create_abuse_report",
        description=(
            "Reports a publicly shared resource, like a shared view or form, for "
            "abuse. This endpoint can be called by anonymous visitors."
        ),
        request=AbuseReportSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_ABUSE_REPORTING_DISABLED",
                    "ERROR_CAPTCHA_VERIFICATION_FAILED",
                ]
            ),
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            AbuseReportingDisabledException: ERROR_ABUSE_REPORTING_DISABLED,
            CaptchaVerificationFailed: ERROR_CAPTCHA_VERIFICATION_FAILED,
        }
    )
    @validate_body(AbuseReportSerializer)
    def post(self, request: Request, data) -> Response:
        if not CoreHandler().get_settings().allow_reporting_abuse:
            raise AbuseReportingDisabledException(
                "Reporting abuse has been disabled by the instance administrator."
            )

        # Deliberately not in the transaction below because it makes an external
        # request to the captcha provider, and this endpoint is publicly reachable.
        CaptchaHandler.validate_if_required(
            "abuse_report",
            data.get("captcha_token"),
            get_user_remote_ip_address_from_request(request),
        )

        resource_type = abuse_report_resource_type_registry.get(data["resource_type"])

        with transaction.atomic():
            with resource_type.map_api_exceptions():
                resource = resource_type.resolve(request, data["identifier"])

            action_type_registry.get_by_type(SubmitAbuseReportActionType).do(
                request.user,
                resource_type,
                resource,
                data["name"],
                data["email"],
                data["description"],
                ip_address=get_user_remote_ip_address_from_request(request),
            )

        return Response(status=HTTP_204_NO_CONTENT)
