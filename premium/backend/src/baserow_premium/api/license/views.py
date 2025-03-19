from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Q, Value

from baserow_premium.license.exceptions import (
    CantManuallyChangeSeatsError,
    InvalidLicenseError,
    LicenseAlreadyExistsError,
    LicenseHasExpiredError,
    LicenseInstanceIdMismatchError,
    NoSeatsLeftInLicenseError,
    UnsupportedLicenseError,
    UserAlreadyOnLicenseError,
)
from baserow_premium.license.handler import LicenseHandler
from baserow_premium.license.models import License
from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.api.user.errors import ERROR_USER_NOT_FOUND
from baserow.core.db import LockedAtomicTransaction
from baserow.core.user.handler import UserHandler

from .errors import (
    ERROR_CANT_MANUALLY_CHANGE_SEATS,
    ERROR_INVALID_LICENSE,
    ERROR_LICENSE_ALREADY_EXISTS,
    ERROR_LICENSE_DOES_NOT_EXIST,
    ERROR_LICENSE_HAS_EXPIRED,
    ERROR_NO_SEATS_LEFT_IN_LICENSE,
    ERROR_PREMIUM_LICENSE_INSTANCE_ID_MISMATCH,
    ERROR_UNSUPPORTED_LICENSE,
    ERROR_USER_ALREADY_ON_LICENSE,
)
from .serializers import (
    LicenseSerializer,
    LicenseUserLookupSerializer,
    LicenseUserSerializer,
    LicenseWithUsersSerializer,
    RegisterLicenseSerializer,
)

User = get_user_model()


class AdminLicensesView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_licenses",
        description=(
            "Lists all the valid licenses that are registered to this instance. A "
            "premium license can be used to unlock the premium features for a fixed "
            "amount of users. An enterprise license can similarly be used to "
            "unlock enterprise features. More information about self hosted licenses "
            "can be found on our pricing page https://baserow.io/pricing."
        ),
        responses={
            200: LicenseSerializer(many=True),
        },
    )
    def get(self, request):
        total_users = UserHandler().get_all_active_users_qs().count()
        licenses = License.objects.all().annotate(
            seats_taken=Count("users"), total_users=Value(total_users)
        )
        # We will sort the items in memory because we don't have access to the
        # `is_active` and `valid_from` property after the instance has been
        # generated. This is because it needs to decode the license. We first want to
        # show the active licenses because those are more important.
        licenses = sorted(licenses, key=lambda x: (not x.is_active, x.valid_from))
        return Response(LicenseSerializer(licenses, many=True).data)

    @extend_schema(
        tags=["Admin"],
        operation_id="admin_register_license",
        description=(
            "Registers a new license. After registering you can assign users to the "
            "license that will be able to use the license's features while the license "
            "is active. If an existing license with the same `license_id` already "
            "exists and the provided license has been issued later than that one, "
            "the existing one will be upgraded."
        ),
        request=RegisterLicenseSerializer,
        responses={
            200: LicenseSerializer,
            400: get_error_schema(
                [
                    "ERROR_INVALID_LICENSE",
                    "ERROR_UNSUPPORTED_LICENSE",
                    "ERROR_PREMIUM_LICENSE_INSTANCE_ID_MISMATCH",
                    "ERROR_LICENSE_HAS_EXPIRED",
                    "ERROR_LICENSE_ALREADY_EXISTS",
                ]
            ),
        },
    )
    @validate_body(RegisterLicenseSerializer)
    @map_exceptions(
        {
            InvalidLicenseError: ERROR_INVALID_LICENSE,
            UnsupportedLicenseError: ERROR_UNSUPPORTED_LICENSE,
            LicenseInstanceIdMismatchError: (
                ERROR_PREMIUM_LICENSE_INSTANCE_ID_MISMATCH
            ),
            LicenseHasExpiredError: ERROR_LICENSE_HAS_EXPIRED,
            LicenseAlreadyExistsError: ERROR_LICENSE_ALREADY_EXISTS,
        }
    )
    def post(self, request, data):
        with LockedAtomicTransaction(License):
            license_object = LicenseHandler.register_license(
                request.user, data["license"]
            )
        return Response(LicenseSerializer(license_object).data)


class AdminLicenseView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The internal identifier of the license.",
            ),
        ],
        tags=["Admin"],
        operation_id="admin_get_license",
        description=(
            "Responds with detailed information about the license related to the "
            "provided parameter."
        ),
        responses={
            200: LicenseWithUsersSerializer,
            404: get_error_schema(["ERROR_LICENSE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({License.DoesNotExist: ERROR_LICENSE_DOES_NOT_EXIST})
    def get(self, request, id):
        license_object = License.objects.prefetch_related("users__user").get(pk=id)
        license_data = LicenseWithUsersSerializer(license_object).data
        return Response(license_data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The internal identifier of the license, this is `id` and "
                "not `license_id`.",
            ),
        ],
        tags=["Admin"],
        operation_id="admin_remove_license",
        description=(
            "Removes the existing license related to the provided parameter. If the "
            "license is active, then all the users that are using the license will "
            "lose access to the features granted by that license."
        ),
        responses={
            204: None,
            404: get_error_schema(["ERROR_LICENSE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({License.DoesNotExist: ERROR_LICENSE_DOES_NOT_EXIST})
    @transaction.atomic
    def delete(self, request, id):
        license = License.objects.get(pk=id)
        LicenseHandler.remove_license(request.user, license)
        return Response(status=204)


class AdminLicenseUserView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The internal identifier of the license, this is `id` and "
                "not `license_id`.",
            ),
            OpenApiParameter(
                name="user_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the user that must be added to the license.",
            ),
        ],
        tags=["Admin"],
        operation_id="admin_add_user_to_license",
        description=(
            "Adds the user related to the provided parameter and to the license "
            "related to the parameter. This only happens if there are enough seats "
            "left on the license and if the user is not already on the license."
        ),
        request=None,
        responses={
            200: LicenseUserSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_ALREADY_ON_LICENSE",
                    "ERROR_NO_SEATS_LEFT_IN_LICENSE",
                    "ERROR_CANT_MANUALLY_CHANGE_SEATS",
                ]
            ),
            404: get_error_schema(
                ["ERROR_LICENSE_DOES_NOT_EXIST", "ERROR_USER_NOT_FOUND"]
            ),
        },
    )
    @map_exceptions(
        {
            License.DoesNotExist: ERROR_LICENSE_DOES_NOT_EXIST,
            User.DoesNotExist: ERROR_USER_NOT_FOUND,
            UserAlreadyOnLicenseError: ERROR_USER_ALREADY_ON_LICENSE,
            NoSeatsLeftInLicenseError: ERROR_NO_SEATS_LEFT_IN_LICENSE,
            CantManuallyChangeSeatsError: ERROR_CANT_MANUALLY_CHANGE_SEATS,
        }
    )
    @transaction.atomic
    def post(self, request, id, user_id):
        license = License.objects.select_for_update(of=("self",)).get(pk=id)
        user = User.objects.get(pk=user_id)
        LicenseHandler.add_user_to_license(request.user, license, user)
        return Response(LicenseUserSerializer(user).data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The internal identifier of the license, this is `id` and "
                "not `license_id`.",
            ),
            OpenApiParameter(
                name="user_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the user that must be removed from the license.",
            ),
        ],
        tags=["Admin"],
        operation_id="admin_remove_user_from_license",
        description=(
            "Removes the user related to the provided parameter and to the license "
            "related to the parameter. This only happens if the user is on the "
            "license, otherwise nothing will happen."
        ),
        request=None,
        responses={
            204: None,
            400: get_error_schema(["ERROR_CANT_MANUALLY_CHANGE_SEATS"]),
            404: get_error_schema(
                [
                    "ERROR_LICENSE_DOES_NOT_EXIST",
                    "ERROR_USER_NOT_FOUND",
                ]
            ),
        },
    )
    @map_exceptions(
        {
            License.DoesNotExist: ERROR_LICENSE_DOES_NOT_EXIST,
            User.DoesNotExist: ERROR_USER_NOT_FOUND,
            CantManuallyChangeSeatsError: ERROR_CANT_MANUALLY_CHANGE_SEATS,
        }
    )
    @transaction.atomic
    def delete(self, request, id, user_id):
        license = License.objects.select_for_update(of=("self",)).get(pk=id)
        user = User.objects.get(pk=user_id)
        LicenseHandler.remove_user_from_license(request.user, license, user)
        return Response(status=204)


class AdminLicenseFillSeatsView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The internal identifier of the license, this is `id` and "
                "not `license_id`.",
            ),
        ],
        tags=["Admin"],
        operation_id="admin_fill_remaining_seats_of_license",
        description=(
            "Fills the remaining empty seats of the license with the first users that "
            "are found."
        ),
        request=None,
        responses={
            200: LicenseUserSerializer(many=True),
            400: get_error_schema(["ERROR_CANT_MANUALLY_CHANGE_SEATS"]),
            404: get_error_schema(["ERROR_LICENSE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            License.DoesNotExist: ERROR_LICENSE_DOES_NOT_EXIST,
            CantManuallyChangeSeatsError: ERROR_CANT_MANUALLY_CHANGE_SEATS,
        }
    )
    @transaction.atomic
    def post(self, request, id):
        license = License.objects.get(pk=id)
        license_users = LicenseHandler.fill_remaining_seats_of_license(
            request.user, license
        )
        users = [license_user.user for license_user in license_users]
        return Response(LicenseUserSerializer(users, many=True).data)


class AdminRemoveAllUsersFromLicenseView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The internal identifier of the license, this is `id` and "
                "not `license_id`.",
            ),
        ],
        tags=["Admin"],
        operation_id="admin_remove_all_users_from_license",
        description=(
            "Removes all the users that are on the license. This will "
            "empty all the seats."
        ),
        request=None,
        responses={
            204: None,
            400: get_error_schema(["ERROR_CANT_MANUALLY_CHANGE_SEATS"]),
            404: get_error_schema(["ERROR_LICENSE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            License.DoesNotExist: ERROR_LICENSE_DOES_NOT_EXIST,
            CantManuallyChangeSeatsError: ERROR_CANT_MANUALLY_CHANGE_SEATS,
        }
    )
    @transaction.atomic
    def post(self, request, id):
        license = License.objects.get(pk=id)
        LicenseHandler.remove_all_users_from_license(request.user, license)
        return Response(status=204)


class AdminLicenseLookupUsersView(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The internal identifier of the license, this is `id` and "
                "not `license_id`.",
            ),
            OpenApiParameter(
                name="search",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.STR,
                description="If provided, only users where the name or email "
                "contains the value are returned.",
            ),
            OpenApiParameter(
                name="page",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines which page of users should be returned.",
            ),
            OpenApiParameter(
                name="size",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description=f"Defines how many users should be returned per page.",
            ),
        ],
        operation_id="admin_license_lookup_users",
        description=(
            "This endpoint can be used to lookup users that can be added to a "
            " license. Users that are already in the license are not returned "
            "here. Optionally a `search` query parameter can be provided to filter "
            "the results."
        ),
        responses={
            200: get_example_pagination_serializer_class(LicenseUserLookupSerializer),
            404: get_error_schema(["ERROR_LICENSE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({License.DoesNotExist: ERROR_LICENSE_DOES_NOT_EXIST})
    def get(self, request, id):
        baserow_license = License.objects.get(pk=id)
        search = request.GET.get("search")
        queryset = User.objects.filter(
            ~Q(id__in=baserow_license.users.all().values_list("user_id", flat=True))
        ).order_by("first_name")

        if search:
            queryset = queryset.filter(
                Q(first_name__icontains=search) | Q(email__icontains=search)
            )

        paginator = PageNumberPagination(limit_page_size=settings.ROW_PAGE_SIZE_LIMIT)
        page = paginator.paginate_queryset(queryset, request, self)
        serializer = LicenseUserLookupSerializer(page, many=True)
        return paginator.get_paginated_response(serializer.data)


class AdminCheckLicense(APIView):
    permission_classes = (IsAdminUser,)

    @extend_schema(
        tags=["Admin"],
        parameters=[
            OpenApiParameter(
                name="id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The internal identifier of the license, this is `id` and "
                "not `license_id`.",
            ),
        ],
        operation_id="admin_license_check",
        description=(
            "This endpoint checks with the authority if the license needs to be "
            "updated. It also checks if the license is operating within its limits "
            "and might take action on that. It could also happen that the license has "
            "been deleted because there is an instance id mismatch or because it's "
            "invalid. In that case a `204` status code is returned."
        ),
        responses={
            200: LicenseWithUsersSerializer,
            404: get_error_schema(["ERROR_LICENSE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions({License.DoesNotExist: ERROR_LICENSE_DOES_NOT_EXIST})
    def get(self, request, id):
        license_object = License.objects.get(pk=id)
        updated_licenses = LicenseHandler.check_licenses([license_object])
        if not updated_licenses[0].pk:
            # If the primary key is None, it means that the license has been deleted
            # which could happen when checking the license. In that case, we want to
            # respond with a 204 (empty response) respond to indicate that it was
            # deleted.
            return Response(status=204)
        else:
            return Response(LicenseWithUsersSerializer(updated_licenses[0]).data)
