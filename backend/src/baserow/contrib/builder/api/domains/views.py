from typing import Dict

from django.conf import settings
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_body_custom_fields,
)
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import (
    DiscriminatorCustomFieldsMappingSerializer,
    type_from_data_or_registry,
    validate_data_custom_fields,
)
from baserow.contrib.builder.api.domains.errors import (
    ERROR_DOMAIN_DOES_NOT_EXIST,
    ERROR_DOMAIN_NAME_NOT_UNIQUE,
    ERROR_DOMAIN_NOT_IN_BUILDER,
    ERROR_SUB_DOMAIN_HAS_INVALID_DOMAIN_NAME,
)
from baserow.contrib.builder.api.domains.serializers import (
    CreateDomainSerializer,
    DomainSerializer,
    OrderDomainsSerializer,
    UpdateDomainSerializer,
)
from baserow.contrib.builder.domains.exceptions import (
    DomainDoesNotExist,
    DomainNameNotUniqueError,
    DomainNotInBuilder,
    SubDomainHasInvalidDomainName,
)
from baserow.contrib.builder.domains.handler import DomainHandler
from baserow.contrib.builder.domains.models import Domain
from baserow.contrib.builder.domains.registries import domain_type_registry
from baserow.contrib.builder.domains.service import DomainService
from baserow.contrib.builder.exceptions import BuilderDoesNotExist
from baserow.contrib.builder.handler import BuilderHandler
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.jobs.registries import job_type_registry


class DomainsView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="builder_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a domain for the application builder related to"
                "the provided value",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder domains"],
        operation_id="create_builder_domain",
        description="Creates a new domain for an application builder",
        request=DiscriminatorCustomFieldsMappingSerializer(
            domain_type_registry, CreateDomainSerializer, request=True
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                domain_type_registry, DomainSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            SubDomainHasInvalidDomainName: ERROR_SUB_DOMAIN_HAS_INVALID_DOMAIN_NAME,
        }
    )
    @validate_body_custom_fields(
        domain_type_registry, base_serializer_class=CreateDomainSerializer
    )
    def post(self, request, data: Dict, builder_id: int):
        builder = BuilderHandler().get_builder(builder_id)
        type_name = data.pop("type")

        domain_type = domain_type_registry.get(type_name)
        domain = DomainService().create_domain(
            request.user, domain_type, builder, **data
        )

        serializer = domain_type_registry.get_serializer(domain, DomainSerializer)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="builder_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Gets all the domains for the specified builder",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder domains"],
        operation_id="get_builder_domains",
        description="Gets all the domains of a builder",
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                domain_type_registry, DomainSerializer, many=True
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
        }
    )
    def get(self, request, builder_id: int):
        builder = BuilderHandler().get_builder(builder_id)

        domains = DomainService().get_domains(
            request.user,
            builder,
        )

        data = [
            domain_type_registry.get_serializer(domain, DomainSerializer).data
            for domain in domains
        ]

        return Response(data)


class DomainView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="domain_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the domain",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder domains"],
        operation_id="update_builder_domain",
        description="Updates an existing domain of an application builder",
        request=UpdateDomainSerializer,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                domain_type_registry, DomainSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_DOMAIN_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DomainDoesNotExist: ERROR_DOMAIN_DOES_NOT_EXIST,
            DomainNameNotUniqueError: ERROR_DOMAIN_NAME_NOT_UNIQUE,
            SubDomainHasInvalidDomainName: ERROR_SUB_DOMAIN_HAS_INVALID_DOMAIN_NAME,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, domain_id: int):
        base_queryset = Domain.objects

        domain = (
            DomainService()
            .get_domain(
                request.user, domain_id, base_queryset=base_queryset, for_update=True
            )
            .specific
        )
        domain_type = type_from_data_or_registry(
            request.data, domain_type_registry, domain
        )

        data = validate_data_custom_fields(
            domain_type.type,
            domain_type_registry,
            request.data,
            base_serializer_class=UpdateDomainSerializer,
            partial=True,
        )

        domain_updated = DomainService().update_domain(request.user, domain, **data)

        serializer = domain_type_registry.get_serializer(
            domain_updated, DomainSerializer
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="domain_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the domain",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder domains"],
        operation_id="delete_builder_domain",
        description="Deletes an existing domain of an application builder",
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_DOMAIN_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            DomainDoesNotExist: ERROR_DOMAIN_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def delete(self, request, domain_id: int):
        domain = DomainService().get_domain(request.user, domain_id, for_update=True)

        DomainService().delete_domain(request.user, domain)

        return Response(status=204)


class OrderDomainsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="builder_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The builder the domain belongs to",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder domains"],
        operation_id="order_builder_domains",
        description="Apply a new order to the domains of a builder",
        request=OrderDomainsSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_DOMAIN_NOT_IN_BUILDER",
                ]
            ),
            404: get_error_schema(
                ["ERROR_APPLICATION_DOES_NOT_EXIST", "ERROR_DOMAIN_DOES_NOT_EXIST"]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            DomainDoesNotExist: ERROR_DOMAIN_DOES_NOT_EXIST,
            DomainNotInBuilder: ERROR_DOMAIN_NOT_IN_BUILDER,
        }
    )
    @validate_body(OrderDomainsSerializer)
    def post(self, request, data: Dict, builder_id: int):
        builder = BuilderHandler().get_builder(builder_id)

        DomainService().order_domains(request.user, builder, data["domain_ids"])

        return Response(status=204)


class AsyncPublishDomainView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="domain_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The builder application id the user wants to publish.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder domains"],
        operation_id="publish_builder_domain",
        description=(
            "This endpoint starts an asynchronous job to publish the builder. "
            "The job clones the current version of the given builder and publish it "
            "for the given domain."
        ),
        request=None,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            DomainDoesNotExist: ERROR_DOMAIN_DOES_NOT_EXIST,
        }
    )
    def post(self, request, domain_id: int):
        """
        Starts an async job to publish a builder to the given domain.
        """

        domain = DomainHandler().get_domain(domain_id)

        job = DomainService().async_publish(request.user, domain)

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=HTTP_202_ACCEPTED)


class AskPublicBuilderDomainExistsView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="domain",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="The domain name for which",
            )
        ],
        tags=["Builder domains"],
        operation_id="ask_public_builder_domain_exists",
        description=(
            "This endpoint can be used to check whether a domain exists for SSL "
            "certificate purposes. It's compatible with the Caddy on_demand TLS as "
            "described here: https://caddyserver.com/docs/json/apps/tls/automation"
            "/on_demand/ask/. It will respond with a 200 status code if it exists or "
            "a 404 if it doesn't exist."
        ),
        responses={
            200: None,
            404: None,
        },
    )
    def get(self, request):
        domain_name = request.GET.get("domain", "")

        # It's difficult to make an exception in the `Caddyfile` to always get an SSL
        # certificate for the one domain, and ask for the rest of the domains.
        # Because the backend and web-frontend hostname are not builder domains,
        # we must add these as accepted domains.
        allowed_domain = set(
            [
                settings.PUBLIC_BACKEND_HOSTNAME,
                settings.PUBLIC_WEB_FRONTEND_HOSTNAME,
            ]
            + settings.EXTRA_PUBLIC_BACKEND_HOSTNAMES
            + settings.EXTRA_PUBLIC_WEB_FRONTEND_HOSTNAMES
        )

        if domain_name in allowed_domain:
            return Response(None, status=200)

        try:
            DomainService().get_public_builder_by_domain_name(request.user, domain_name)
            return Response(None, status=200)
        except BuilderDoesNotExist:
            return Response(None, status=404)
