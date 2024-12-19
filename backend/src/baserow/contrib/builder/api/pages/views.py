from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.status import HTTP_202_ACCEPTED
from rest_framework.views import APIView

from baserow.api.applications.errors import ERROR_APPLICATION_DOES_NOT_EXIST
from baserow.api.decorators import map_exceptions, validate_body
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.contrib.builder.api.pages.errors import (
    ERROR_DUPLICATE_PATH_PARAMS_IN_PATH,
    ERROR_DUPLICATE_QUERY_PARAMS,
    ERROR_INVALID_QUERY_PARAM_NAME,
    ERROR_PAGE_DOES_NOT_EXIST,
    ERROR_PAGE_NAME_NOT_UNIQUE,
    ERROR_PAGE_NOT_IN_BUILDER,
    ERROR_PAGE_PATH_NOT_UNIQUE,
    ERROR_PATH_PARAM_NOT_DEFINED,
    ERROR_PATH_PARAM_NOT_IN_PATH,
    ERROR_SHARED_PAGE_READ_ONLY,
)
from baserow.contrib.builder.api.pages.serializers import (
    CreatePageSerializer,
    OrderPagesSerializer,
    PageSerializer,
    UpdatePageSerializer,
)
from baserow.contrib.builder.handler import BuilderHandler
from baserow.contrib.builder.pages.exceptions import (
    DuplicatePageParams,
    DuplicatePathParamsInPath,
    InvalidQueryParamName,
    PageDoesNotExist,
    PageNameNotUnique,
    PageNotInBuilder,
    PagePathNotUnique,
    PathParamNotDefined,
    PathParamNotInPath,
    SharedPageIsReadOnly,
)
from baserow.contrib.builder.pages.job_types import DuplicatePageJobType
from baserow.contrib.builder.pages.service import PageService
from baserow.core.exceptions import ApplicationDoesNotExist
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry


class PagesView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="builder_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a page for the application builder related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder pages"],
        operation_id="create_builder_page",
        description="Creates a new page for an application builder",
        request=CreatePageSerializer,
        responses={
            200: PageSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_PAGE_NAME_NOT_UNIQUE",
                    "ERROR_PAGE_PATH_NOT_UNIQUE",
                    "ERROR_PATH_PARAM_NOT_IN_PATH",
                    "ERROR_PATH_PARAM_NOT_DEFINED",
                    "ERROR_INVALID_QUERY_PARAM_NAME",
                    "ERROR_DUPLICATE_QUERY_PARAMS",
                ]
            ),
            404: get_error_schema(["ERROR_APPLICATION_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            PageNameNotUnique: ERROR_PAGE_NAME_NOT_UNIQUE,
            PagePathNotUnique: ERROR_PAGE_PATH_NOT_UNIQUE,
            PathParamNotInPath: ERROR_PATH_PARAM_NOT_IN_PATH,
            PathParamNotDefined: ERROR_PATH_PARAM_NOT_DEFINED,
            DuplicatePathParamsInPath: ERROR_DUPLICATE_PATH_PARAMS_IN_PATH,
            InvalidQueryParamName: ERROR_INVALID_QUERY_PARAM_NAME,
            DuplicatePageParams: ERROR_DUPLICATE_QUERY_PARAMS,
        }
    )
    @validate_body(CreatePageSerializer, return_validated=True)
    def post(self, request, data: Dict, builder_id: int):
        builder = BuilderHandler().get_builder(builder_id)

        page = PageService().create_page(
            request.user,
            builder,
            data["name"],
            path=data["path"],
            path_params=data.get("path_params", None),
            query_params=data.get("query_params", None),
        )

        serializer = PageSerializer(page)
        return Response(serializer.data)


class PageView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the page",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder pages"],
        operation_id="update_builder_page",
        description="Updates an existing page of an application builder",
        request=UpdatePageSerializer,
        responses={
            200: PageSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_PAGE_NAME_NOT_UNIQUE",
                    "ERROR_PAGE_PATH_NOT_UNIQUE",
                    "ERROR_PATH_PARAM_NOT_IN_PATH",
                    "ERROR_PATH_PARAM_NOT_DEFINED",
                    "ERROR_SHARED_PAGE_READ_ONLY",
                    "ERROR_INVALID_QUERY_PARAM_NAME",
                    "ERROR_DUPLICATE_QUERY_PARAMS",
                ]
            ),
            404: get_error_schema(
                ["ERROR_PAGE_DOES_NOT_EXIST", "ERROR_APPLICATION_DOES_NOT_EXIST"]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
            PageNameNotUnique: ERROR_PAGE_NAME_NOT_UNIQUE,
            PagePathNotUnique: ERROR_PAGE_PATH_NOT_UNIQUE,
            PathParamNotInPath: ERROR_PATH_PARAM_NOT_IN_PATH,
            PathParamNotDefined: ERROR_PATH_PARAM_NOT_DEFINED,
            DuplicatePathParamsInPath: ERROR_DUPLICATE_PATH_PARAMS_IN_PATH,
            SharedPageIsReadOnly: ERROR_SHARED_PAGE_READ_ONLY,
            InvalidQueryParamName: ERROR_INVALID_QUERY_PARAM_NAME,
            DuplicatePageParams: ERROR_DUPLICATE_QUERY_PARAMS,
        }
    )
    @validate_body(UpdatePageSerializer, return_validated=True)
    def patch(self, request, data: Dict, page_id: int):
        page = PageService().get_page(request.user, page_id)

        page_updated = PageService().update_page(request.user, page, **data)

        serializer = PageSerializer(page_updated)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the page",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder pages"],
        operation_id="delete_builder_page",
        description="Deletes an existing page of an application builder",
        responses={
            204: None,
            400: get_error_schema(
                ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_SHARED_PAGE_READ_ONLY"]
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
            SharedPageIsReadOnly: ERROR_SHARED_PAGE_READ_ONLY,
        }
    )
    @transaction.atomic
    def delete(self, request, page_id: int):
        page = PageService().get_page(request.user, page_id)

        PageService().delete_page(request.user, page)

        return Response(status=204)


class OrderPagesView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="builder_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The builder the page belongs to",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder pages"],
        operation_id="order_builder_pages",
        description="Apply a new order to the pages of a builder",
        request=OrderPagesSerializer,
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_PAGE_NOT_IN_BUILDER",
                ]
            ),
            404: get_error_schema(
                ["ERROR_APPLICATION_DOES_NOT_EXIST", "ERROR_PAGE_DOES_NOT_EXIST"]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ApplicationDoesNotExist: ERROR_APPLICATION_DOES_NOT_EXIST,
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
            PageNotInBuilder: ERROR_PAGE_NOT_IN_BUILDER,
        }
    )
    @validate_body(OrderPagesSerializer)
    def post(self, request, data: Dict, builder_id: int):
        builder = BuilderHandler().get_builder(builder_id)

        PageService().order_pages(request.user, builder, data["page_ids"])

        return Response(status=204)


class AsyncDuplicatePageView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The page to duplicate.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder pages"],
        operation_id="duplicate_builder_page_async",
        description=(
            "Start a job to duplicate the page with the provided `page_id` parameter "
            "if the authorized user has access to the builder's workspace."
        ),
        request=None,
        responses={
            202: DuplicatePageJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    def post(self, request, page_id):
        """Creates a job to duplicate a page in a builder."""

        job = JobHandler().create_and_start_job(
            request.user, DuplicatePageJobType.type, page_id=page_id
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=HTTP_202_ACCEPTED)
