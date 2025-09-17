from django.db import transaction
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.api.two_factor_auth.errors import ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST
from baserow.core.two_factor_auth.exceptions import TwoFactorAuthTypeDoesNotExist
from drf_spectacular.utils import extend_schema


class TwoFactorAuthView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Auth"],
        operation_id="setup_two_factor_auth",
        description=(
            "Configures two-factor authentication for the authenticated user."
        ),
        request=None, # TODO:
        responses={
            # 200: Serializer,
            400: get_error_schema(
                [
                ]
            ),
            404: get_error_schema(["ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TwoFactorAuthTypeDoesNotExist: ERROR_TWO_FACTOR_AUTH_TYPE_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def post(self, request):
        """
        Configures two-factor authentication for the authenticated user.
        """

        serializer = None # Serializer(twofa)
        return Response(serializer.data)
