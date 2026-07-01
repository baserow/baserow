import json
from typing import Dict

from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_body_custom_fields,
)
from baserow.api.schemas import CLIENT_SESSION_ID_SCHEMA_PARAMETER, get_error_schema
from baserow.api.utils import (
    CustomFieldRegistryMappingSerializer,
    DiscriminatorCustomFieldsMappingSerializer,
    type_from_data_or_registry,
    validate_data_custom_fields,
)
from baserow.contrib.builder.api.data_sources.errors import (
    ERROR_DATA_SOURCE_DOES_NOT_EXIST,
)
from baserow.contrib.builder.api.elements.errors import (
    ERROR_ELEMENT_DOES_NOT_EXIST,
    ERROR_ELEMENT_INVALID_FORMULA,
    ERROR_ELEMENT_MOVE_NOT_ALLOWED,
    ERROR_ELEMENT_NOT_IN_SAME_PAGE,
    ERROR_ELEMENT_PROPERTY_OPTIONS_NOT_UNIQUE,
    ERROR_ELEMENT_TYPE_DEACTIVATED,
)
from baserow.contrib.builder.api.elements.serializers import (
    CreateElementSerializer,
    DuplicateElementSerializer,
    ElementSerializer,
    MoveElementSerializer,
    UpdateElementSerializer,
)
from baserow.contrib.builder.api.pages.errors import (
    ERROR_PAGE_DOES_NOT_EXIST,
    ERROR_PAGE_NOT_IN_BUILDER,
)
from baserow.contrib.builder.application_types import BuilderApplicationType
from baserow.contrib.builder.data_sources.exceptions import DataSourceDoesNotExist
from baserow.contrib.builder.elements.actions import (
    CreateElementActionType,
    DeleteElementActionType,
    DuplicateElementActionType,
    MoveElementActionType,
    UpdateElementActionType,
)
from baserow.contrib.builder.elements.exceptions import (
    CollectionElementPropertyOptionsNotUnique,
    ElementDoesNotExist,
    ElementMoveNotAllowed,
    ElementNotInSamePage,
    ElementTypeDeactivated,
)
from baserow.contrib.builder.elements.handler import ElementHandler
from baserow.contrib.builder.elements.registries import element_type_registry
from baserow.contrib.builder.elements.service import ElementService
from baserow.contrib.builder.pages.exceptions import PageDoesNotExist, PageNotInBuilder
from baserow.contrib.builder.pages.handler import PageHandler
from baserow.core.formula.exceptions import InvalidRuntimeFormula
from baserow.core.graph.exceptions import GraphPointReferencePointInvalid


class ElementsView(APIView):
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the elements of the page related to the "
                "provided Id.",
            )
        ],
        tags=["Builder elements"],
        operation_id="list_builder_page_elements",
        description=(
            "Lists all the elements of the page related to the provided parameter if "
            "the user has access to the related builder's workspace. "
            "If the workspace is related to a template, then this endpoint will be "
            "publicly accessible."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                element_type_registry, ElementSerializer, many=True
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
        }
    )
    def get(self, request, page_id):
        """
        Responds with a list of serialized elements that belong to the page if the user
        has access to that page.
        """

        page = PageHandler().get_page(page_id)

        service = ElementService()

        # Repair the graph if any elements are missing from it (orphans). The patch
        # is returned so the requesting client can apply it to its already-loaded
        # graph in-band — connected clients are updated via the realtime broadcast.
        graph_patch = service.heal_orphan_elements(request.user, page)

        elements = service.get_elements(request.user, page)

        data = [
            element_type_registry.get_serializer(element, ElementSerializer).data
            for element in elements
        ]
        response = Response(data)

        # A small, page-scoped delta (a handful of graph entries) — kept in a header
        # so the list response body stays a bare array. Tiny by construction, so it
        # never risks a reverse proxy's response-header size limit.
        if graph_patch:
            response["X-Baserow-Builder-Graph-Patch"] = json.dumps(graph_patch)

        return response

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="page_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates an element for the builder page related to the "
                "provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder elements"],
        operation_id="create_builder_page_element",
        description="Creates a new builder element",
        request=DiscriminatorCustomFieldsMappingSerializer(
            element_type_registry,
            CreateElementSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                element_type_registry, ElementSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_ELEMENT_INVALID_FORMULA",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_PAGE_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            PageDoesNotExist: ERROR_PAGE_DOES_NOT_EXIST,
            ElementDoesNotExist: ERROR_ELEMENT_DOES_NOT_EXIST,
            ElementNotInSamePage: ERROR_ELEMENT_NOT_IN_SAME_PAGE,
            ElementTypeDeactivated: ERROR_ELEMENT_TYPE_DEACTIVATED,
            InvalidRuntimeFormula: ERROR_ELEMENT_INVALID_FORMULA,
            GraphPointReferencePointInvalid: ERROR_ELEMENT_DOES_NOT_EXIST,
        }
    )
    @validate_body_custom_fields(
        element_type_registry,
        base_serializer_class=CreateElementSerializer,
        serializer_class_context={"application_type": BuilderApplicationType},
    )
    def post(self, request, data: Dict, page_id: int):
        """Creates a new element."""

        type_name = data.pop("type")
        page = PageHandler().get_page(page_id)

        element_type = element_type_registry.get(type_name)
        element = CreateElementActionType.do(request.user, element_type, page, data)

        serializer = element_type_registry.get_serializer(element, ElementSerializer)
        return Response(serializer.data)


class ElementView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="element_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the element",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder elements"],
        operation_id="update_builder_page_element",
        description="Updates an existing builder element.",
        request=CustomFieldRegistryMappingSerializer(
            element_type_registry,
            UpdateElementSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                element_type_registry, ElementSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_ELEMENT_INVALID_FORMULA",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(
                [
                    "ERROR_ELEMENT_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ElementDoesNotExist: ERROR_ELEMENT_DOES_NOT_EXIST,
            DataSourceDoesNotExist: ERROR_DATA_SOURCE_DOES_NOT_EXIST,
            CollectionElementPropertyOptionsNotUnique: ERROR_ELEMENT_PROPERTY_OPTIONS_NOT_UNIQUE,
            InvalidRuntimeFormula: ERROR_ELEMENT_INVALID_FORMULA,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, element_id: int):
        """
        Update an element.
        """

        element = ElementHandler().get_element_for_update(element_id)
        element_type = type_from_data_or_registry(
            request.data, element_type_registry, element
        )

        data = validate_data_custom_fields(
            element_type.type,
            element_type_registry,
            request.data,
            base_serializer_class=UpdateElementSerializer,
            serializer_class_context={"application_type": BuilderApplicationType},
            partial=True,
            return_validated=True,
        )

        element_updated = UpdateElementActionType.do(request.user, element, data)

        serializer = element_type_registry.get_serializer(
            element_updated, ElementSerializer
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="element_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the element",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder elements"],
        operation_id="delete_builder_page_element",
        description="Deletes the element related by the given id.",
        responses={
            204: None,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_ELEMENT_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ElementDoesNotExist: ERROR_ELEMENT_DOES_NOT_EXIST,
        }
    )
    @transaction.atomic
    def delete(self, request, element_id: int):
        """
        Deletes an element.
        """

        element = ElementHandler().get_element_for_update(element_id)

        DeleteElementActionType.do(request.user, element)

        return Response(status=204)


class MoveElementView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="element_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the element to move",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder elements"],
        operation_id="move_builder_page_element",
        description=(
            "Moves the element in the page before another element or at the end of "
            "the page if no before element is given. The elements must belong to the "
            "same page."
        ),
        request=MoveElementSerializer,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                element_type_registry, ElementSerializer
            ),
            400: get_error_schema(
                ["ERROR_REQUEST_BODY_VALIDATION", "ERROR_ELEMENT_NOT_IN_SAME_PAGE"]
            ),
            404: get_error_schema(
                [
                    "ERROR_ELEMENT_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ElementDoesNotExist: ERROR_ELEMENT_DOES_NOT_EXIST,
            PageNotInBuilder: ERROR_PAGE_NOT_IN_BUILDER,
            ElementMoveNotAllowed: ERROR_ELEMENT_MOVE_NOT_ALLOWED,
            ElementNotInSamePage: ERROR_ELEMENT_NOT_IN_SAME_PAGE,
            GraphPointReferencePointInvalid: ERROR_ELEMENT_DOES_NOT_EXIST,
        }
    )
    @validate_body(MoveElementSerializer)
    def patch(self, request, data: Dict, element_id: int):
        """
        Moves an `element` relative to the provided `reference_element` and `position`.
        """

        element = ElementHandler().get_element_for_update(element_id)
        reference_element_id = data.get("reference_element_id")
        target_page_id = data.pop("target_page_id", None)

        reference_element = None
        if reference_element_id is not None:
            reference_element = ElementHandler().get_element(reference_element_id)

        try:
            target_page = (
                reference_element.page
                if reference_element
                else PageHandler().get_page(target_page_id)
                if target_page_id
                else element.page
            )
        except PageDoesNotExist as e:
            raise PageNotInBuilder(target_page_id) from e

        moved_element = MoveElementActionType.do(
            request.user, element, target_page, **data
        )

        serializer = element_type_registry.get_serializer(
            moved_element, ElementSerializer
        )
        return Response(serializer.data)


class DuplicateElementView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="element_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The id of the element to duplicate",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
        ],
        tags=["Builder elements"],
        operation_id="duplicate_builder_page_element",
        description="Duplicates an element and all of the elements children and the "
        "associated workflow actions as well.",
        responses={
            200: DuplicateElementSerializer,
            400: get_error_schema(["ERROR_REQUEST_BODY_VALIDATION"]),
            404: get_error_schema(
                [
                    "ERROR_ELEMENT_DOES_NOT_EXIST",
                ]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            ElementDoesNotExist: ERROR_ELEMENT_DOES_NOT_EXIST,
        }
    )
    def post(self, request, element_id: int):
        """
        Duplicates the element and all of its children
        """

        element = ElementHandler().get_element_for_update(element_id)

        elements_and_workflow_actions_duplicated = DuplicateElementActionType.do(
            request.user, element
        )

        serializer = DuplicateElementSerializer(
            elements_and_workflow_actions_duplicated
        )

        return Response(serializer.data)
