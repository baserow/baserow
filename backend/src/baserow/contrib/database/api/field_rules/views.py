from urllib.request import Request

from django.conf import settings
from django.db import transaction

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions, require_request_data_type
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.pagination import PageNumberPagination
from baserow.api.schemas import get_error_schema
from baserow.api.serializers import get_example_pagination_serializer_class
from baserow.api.utils import DiscriminatorCustomFieldsMappingSerializer
from baserow.contrib.database.api.fields.errors import ERROR_FIELD_DOES_NOT_EXIST
from baserow.contrib.database.api.tables.errors import ERROR_TABLE_DOES_NOT_EXIST
from baserow.contrib.database.field_rules.actions import (
    CreateFieldRuleActionType,
    DeleteFieldRuleActionType,
    UpdateFieldRuleActionType,
)
from baserow.contrib.database.field_rules.exceptions import NoRuleError
from baserow.contrib.database.field_rules.handlers import FieldRuleHandler
from baserow.contrib.database.field_rules.operations import (
    ReadFieldRuleOperationType,
    SetFieldRuleOperationType,
)
from baserow.contrib.database.field_rules.registries import (
    FieldRuleType,
    field_rules_type_registry,
)
from baserow.contrib.database.fields.handler import FieldDoesNotExist
from baserow.contrib.database.table.exceptions import TableDoesNotExist
from baserow.contrib.database.table.handler import TableHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.exceptions import InstanceTypeDoesNotExist, UserNotInWorkspace
from baserow.core.handler import CoreHandler

from .errors import ERROR_RULE_DOES_NOT_EXIST, ERROR_RULE_TYPE_DOES_NOT_EXIST
from .serializers import (
    InvalidRowSerializer,
    RequestFieldRuleSerializer,
    RequestUpdateFieldRuleSerializer,
    ResponseFieldRuleSerializer,
)


class FieldRulesView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the table to get field rules.",
            ),
        ],
        tags=["Field rules"],
        operation_id="get_field_rules",
        description=("Get a list of field rules for the table"),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                field_rules_type_registry,
                many=True,
                base_class=ResponseFieldRuleSerializer,
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @transaction.atomic
    def get(self, request: Request, table_id: int) -> Response:
        """
        Get a list of field rules for the given table.
        """

        table = TableHandler().get_table(table_id)
        workspace = table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            ReadFieldRuleOperationType.type,
            workspace=workspace,
            context=table,
        )

        handler = FieldRuleHandler(table, request.user)
        rules = handler.get_rules()

        data = [
            rule.get_type().get_serializer(rule, ResponseFieldRuleSerializer).data
            for rule in rules
        ]

        return Response(data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the table to set a field rule.",
            ),
        ],
        tags=["Field rules"],
        operation_id="create_field_rule",
        description=(
            "Create a field rule for a table"
            "\n\nNote, that some field rule types"
            "require **enterprise** license."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            field_rules_type_registry,
            base_class=RequestFieldRuleSerializer,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                field_rules_type_registry,
                many=True,
                base_class=ResponseFieldRuleSerializer,
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_RULE_TYPE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            InstanceTypeDoesNotExist: ERROR_RULE_TYPE_DOES_NOT_EXIST,
        }
    )
    @require_request_data_type(dict)
    @transaction.atomic
    def post(self, request: Request, table_id: int) -> Response:
        """
        Create a new field rule.
        """

        table = TableHandler().get_table(table_id)
        workspace = table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            SetFieldRuleOperationType.type,
            workspace=workspace,
            context=table,
        )

        rule_type_name = request.data.get("type")

        rule_type: FieldRuleType = field_rules_type_registry.get(rule_type_name)

        serializer_class = rule_type.get_serializer_class(request_serializer=True)

        serializer = serializer_class(
            data=request.data,
            context={"table": table, "user": request.user, "request": request},
        )

        serializer.is_valid(raise_exception=True)

        rule = action_type_registry.get(CreateFieldRuleActionType.type).do(
            request.user,
            table=table,
            rule_type=rule_type_name,
            in_rule_data=serializer.validated_data,
        )

        serializer = rule_type.get_serializer(
            rule,
            context={"table": table, "request": request},
            request=False,
            base_class=ResponseFieldRuleSerializer,
        )
        return Response(serializer.data)


class FieldRuleView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the table.",
            ),
            OpenApiParameter(
                name="rule_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the rule to update.",
            ),
        ],
        tags=["Field rules"],
        operation_id="update_field_rule",
        description=(
            "Update a specific field rule\n\nNote, that operating on certain "
            "rule types may require **enterprise** license."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            field_rules_type_registry, base_class=RequestUpdateFieldRuleSerializer
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                field_rules_type_registry,
                base_class=ResponseFieldRuleSerializer,
                many=True,
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_RULE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            NoRuleError: ERROR_RULE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @transaction.atomic
    def put(self, request: Request, table_id: int, rule_id: int) -> Response:
        """
        Update an existing field rule.
        """

        table = TableHandler().get_table(table_id)
        workspace = table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            SetFieldRuleOperationType.type,
            workspace=workspace,
            context=table,
        )

        handler = FieldRuleHandler(table, request.user)

        rule = handler.get_rule(rule_id)

        rule_type = rule.get_type()
        serializer_class = rule_type.get_serializer_class()
        serializer = serializer_class(
            data=request.data,
            context={"table": table, "user": request.user, "request": request},
        )

        serializer.is_valid(raise_exception=True)

        rule = action_type_registry.get(UpdateFieldRuleActionType.type).do(
            request.user,
            table=table,
            rule_id=rule_id,
            in_rule_data=serializer.validated_data,
        )

        serializer = rule_type.get_serializer(
            rule,
            context={"table": table, "request": request},
            request=False,
            base_class=ResponseFieldRuleSerializer,
        )

        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the table.",
            ),
            OpenApiParameter(
                name="rule_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the rule to delete.",
            ),
        ],
        tags=["Field rules"],
        operation_id="delete_field_rule",
        description=("Delete a field rule."),
        responses={
            200: ResponseFieldRuleSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            NoRuleError: ERROR_RULE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @transaction.atomic
    def delete(self, request: Request, table_id: int, rule_id: int) -> Response:
        """
        Delete a field rule on a table.
        """

        table = TableHandler().get_table(table_id)
        workspace = table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            SetFieldRuleOperationType.type,
            workspace=workspace,
            context=table,
        )

        rule = action_type_registry.get(DeleteFieldRuleActionType.type).do(
            request.user, table=table, rule_id=rule_id
        )
        rule_type = rule.get_type()
        serializer = rule_type.get_serializer(rule, request=True)
        return Response(serializer.data)


class InvalidRowsView(APIView):
    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The ID of the table to get a list of invalid row ids.",
            ),
        ],
        tags=["Field rules"],
        operation_id="get_invalid_rows",
        description=("Get a list of invalid rows"),
        responses={
            200: get_example_pagination_serializer_class(InvalidRowSerializer),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    @transaction.atomic
    def get(self, request: Request, table_id: int) -> Response:
        """
        Get a list of field rules for the given table.
        """

        table = TableHandler().get_table(table_id)
        workspace = table.database.workspace
        CoreHandler().check_permissions(
            request.user,
            ReadFieldRuleOperationType.type,
            workspace=workspace,
            context=table,
        )

        handler = FieldRuleHandler(table, request.user)
        invalid_rows_queryset = handler.get_invalid_rows()

        paginator = PageNumberPagination(limit_page_size=settings.ROW_PAGE_SIZE_LIMIT)
        page = paginator.paginate_queryset(invalid_rows_queryset, request, self)
        serializer = InvalidRowSerializer(page, many=True)

        return paginator.get_paginated_response(serializer.data)
