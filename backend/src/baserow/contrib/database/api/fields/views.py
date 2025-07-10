from typing import Any, Dict

from django.conf import settings
from django.contrib.auth.hashers import check_password
from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework import status
from rest_framework.decorators import permission_classes as method_permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import (
    map_exceptions,
    require_request_data_type,
    validate_body,
    validate_body_custom_fields,
    validate_query_parameters,
)
from baserow.api.errors import ERROR_USER_NOT_IN_GROUP
from baserow.api.jobs.errors import ERROR_MAX_JOB_COUNT_EXCEEDED
from baserow.api.jobs.serializers import JobSerializer
from baserow.api.schemas import (
    CLIENT_SESSION_ID_SCHEMA_PARAMETER,
    CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
    get_error_schema,
)
from baserow.api.trash.errors import ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM
from baserow.api.utils import (
    DiscriminatorCustomFieldsMappingSerializer,
    type_from_data_or_registry,
    validate_data_custom_fields,
)
from baserow.contrib.database.api.fields.errors import (
    ERROR_CANNOT_CHANGE_FIELD_TYPE,
    ERROR_CANNOT_CREATE_FIELD_TYPE,
    ERROR_CANNOT_DELETE_PRIMARY_FIELD,
    ERROR_DB_INDEX_NOT_SUPPORTED,
    ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT,
    ERROR_FIELD_CIRCULAR_REFERENCE,
    ERROR_FIELD_CONSTRAINT,
    ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE,
    ERROR_FIELD_DOES_NOT_EXIST,
    ERROR_FIELD_IS_ALREADY_PRIMARY,
    ERROR_FIELD_NOT_IN_TABLE,
    ERROR_FIELD_SELF_REFERENCE,
    ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS,
    ERROR_IMMUTABLE_FIELD_PROPERTIES,
    ERROR_IMMUTABLE_FIELD_TYPE,
    ERROR_INCOMPATIBLE_FIELD_TYPE_FOR_UNIQUE_VALUES,
    ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE,
    ERROR_INVALID_BASEROW_FIELD_NAME,
    ERROR_INVALID_FIELD_CONSTRAINT,
    ERROR_INVALID_PASSWORD_FIELD_PASSWORD,
    ERROR_MAX_FIELD_COUNT_EXCEEDED,
    ERROR_RESERVED_BASEROW_FIELD_NAME,
    ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD,
    ERROR_TABLE_HAS_NO_PRIMARY_FIELD,
)
from baserow.contrib.database.api.rows.errors import ERROR_ROW_DOES_NOT_EXIST
from baserow.contrib.database.api.tables.errors import (
    ERROR_FAILED_TO_LOCK_TABLE_DUE_TO_CONFLICT,
    ERROR_TABLE_DOES_NOT_EXIST,
)
from baserow.contrib.database.api.tokens.authentications import TokenAuthentication
from baserow.contrib.database.api.tokens.errors import ERROR_NO_PERMISSION_TO_TABLE
from baserow.contrib.database.fields.actions import (
    ChangePrimaryFieldActionType,
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.dependencies.exceptions import (
    CircularFieldDependencyError,
    SelfReferenceFieldDependencyError,
)
from baserow.contrib.database.fields.exceptions import (
    CannotChangeFieldType,
    CannotCreateFieldType,
    CannotDeletePrimaryField,
    DbIndexNotSupportedError,
    FailedToLockFieldDueToConflict,
    FieldConstraintDoesNotSupportDefaultValueError,
    FieldConstraintException,
    FieldDoesNotExist,
    FieldIsAlreadyPrimary,
    FieldNotInTable,
    FieldWithSameNameAlreadyExists,
    ImmutableFieldProperties,
    ImmutableFieldType,
    IncompatibleFieldTypeForUniqueValues,
    IncompatiblePrimaryFieldTypeError,
    InvalidBaserowFieldName,
    InvalidFieldConstraint,
    InvalidPasswordFieldPassword,
    MaxFieldLimitExceeded,
    ReservedBaserowFieldNameException,
    SelectOptionDoesNotBelongToField,
    TableHasNoPrimaryField,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.job_types import DuplicateFieldJobType
from baserow.contrib.database.fields.models import PasswordField
from baserow.contrib.database.fields.operations import (
    CreateFieldOperationType,
    ListFieldsOperationType,
    ReadFieldOperationType,
)
from baserow.contrib.database.fields.registries import field_type_registry
from baserow.contrib.database.rows.exceptions import RowDoesNotExist
from baserow.contrib.database.table.exceptions import (
    FailedToLockTableDueToConflict,
    TableDoesNotExist,
)
from baserow.contrib.database.table.handler import TableHandler
from baserow.contrib.database.tokens.exceptions import NoPermissionToTable
from baserow.contrib.database.tokens.handler import TokenHandler
from baserow.core.action.registries import action_type_registry
from baserow.core.db import atomic_with_retry_on_deadlock, specific_iterator
from baserow.core.exceptions import UserNotInWorkspace
from baserow.core.handler import CoreHandler
from baserow.core.jobs.exceptions import MaxJobCountExceeded
from baserow.core.jobs.handler import JobHandler
from baserow.core.jobs.registries import job_type_registry
from baserow.core.trash.exceptions import CannotDeleteAlreadyDeletedItem

from ...rows.handler import RowHandler
from .serializers import (
    ChangePrimaryFieldParamsSerializer,
    CreateFieldSerializer,
    DuplicateFieldParamsSerializer,
    FieldSerializer,
    FieldSerializerWithRelatedFields,
    PasswordFieldAuthenticationResponseSerializer,
    PasswordFieldAuthenticationSerializer,
    RelatedFieldsSerializer,
    UniqueRowValueParamsSerializer,
    UniqueRowValuesSerializer,
    UpdateFieldSerializer,
)


class FieldsView(APIView):
    authentication_classes = APIView.authentication_classes + [TokenAuthentication]
    permission_classes = (IsAuthenticated,)

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]

        return super().get_permissions()

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns only the fields of the table related to the "
                "provided value.",
            )
        ],
        tags=["Database table fields"],
        operation_id="list_database_table_fields",
        description=(
            "Lists all the fields of the table related to the provided parameter if "
            "the user has access to the related database's workspace. If the workspace is "
            "related to a template, then this endpoint will be publicly accessible. A "
            "table consists of fields and each field can have a different type. Each "
            "type can have different properties. A field is comparable with a regular "
            "table's column."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                field_type_registry, FieldSerializer, many=True
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
        }
    )
    @method_permission_classes([AllowAny])
    def get(self, request, table_id):
        """
        Responds with a list of serialized fields that belong to the table if the user
        has access to that workspace.
        """

        table = TableHandler().get_table(table_id)

        CoreHandler().check_permissions(
            request.user,
            ListFieldsOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        TokenHandler().check_table_permissions(
            request, ["read", "create", "update"], table, False
        )

        base_field_queryset = FieldHandler().get_base_fields_queryset()
        fields = specific_iterator(
            base_field_queryset.filter(table=table),
            per_content_type_queryset_hook=(
                lambda field, queryset: field_type_registry.get_by_model(
                    field
                ).enhance_field_queryset(queryset, field)
            ),
        )

        data = [
            field_type_registry.get_serializer(field, FieldSerializer).data
            for field in fields
        ]
        return Response(data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Creates a new field for the provided table related to the "
                "value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="create_database_table_field",
        description=(
            "Creates a new field for the table related to the provided `table_id` "
            "parameter if the authorized user has access to the related database's "
            "workspace. Depending on the type, different properties can optionally be "
            "set."
            "If creating the field causes other fields to change then the specific"
            "instances of those fields will be included in the related fields "
            "response key."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            field_type_registry, CreateFieldSerializer, request=True
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                field_type_registry, FieldSerializerWithRelatedFields
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_FIELD_COUNT_EXCEEDED",
                    "ERROR_RESERVED_BASEROW_FIELD_NAME",
                    "ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS",
                    "ERROR_INVALID_BASEROW_FIELD_NAME",
                    "ERROR_FIELD_SELF_REFERENCE",
                    "ERROR_FIELD_CIRCULAR_REFERENCE",
                    "ERROR_IMMUTABLE_FIELD_PROPERTIES",
                ]
            ),
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_TABLE"]),
            404: get_error_schema(["ERROR_TABLE_DOES_NOT_EXIST"]),
        },
    )
    @atomic_with_retry_on_deadlock()
    @validate_body_custom_fields(
        field_type_registry,
        base_serializer_class=CreateFieldSerializer,
    )
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaxFieldLimitExceeded: ERROR_MAX_FIELD_COUNT_EXCEEDED,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            FieldWithSameNameAlreadyExists: ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS,
            ReservedBaserowFieldNameException: ERROR_RESERVED_BASEROW_FIELD_NAME,
            InvalidBaserowFieldName: ERROR_INVALID_BASEROW_FIELD_NAME,
            SelfReferenceFieldDependencyError: ERROR_FIELD_SELF_REFERENCE,
            CircularFieldDependencyError: ERROR_FIELD_CIRCULAR_REFERENCE,
            FailedToLockTableDueToConflict: ERROR_FAILED_TO_LOCK_TABLE_DUE_TO_CONFLICT,
            CannotCreateFieldType: ERROR_CANNOT_CREATE_FIELD_TYPE,
            DbIndexNotSupportedError: ERROR_DB_INDEX_NOT_SUPPORTED,
            FieldConstraintException: ERROR_FIELD_CONSTRAINT,
            InvalidFieldConstraint: ERROR_INVALID_FIELD_CONSTRAINT,
            ImmutableFieldProperties: ERROR_IMMUTABLE_FIELD_PROPERTIES,
            FieldConstraintDoesNotSupportDefaultValueError: ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE,
        }
    )
    def post(self, request, data, table_id):
        """Creates a new field for a table."""

        type_name = data.pop("type")
        field_type = field_type_registry.get(type_name)
        table = TableHandler().get_table_for_update(
            table_id, nowait=settings.BASEROW_NOWAIT_FOR_LOCKS
        )
        CoreHandler().check_permissions(
            request.user,
            CreateFieldOperationType.type,
            workspace=table.database.workspace,
            context=table,
        )

        # field_create permission doesn't exists, so any call of this endpoint with a
        # token will be rejected.
        TokenHandler().check_table_permissions(request, "field_create", table, False)

        # Because each field type can raise custom exceptions while creating the
        # field we need to be able to map those to the correct API exceptions which are
        # defined in the type.
        with field_type.map_api_exceptions():
            field, updated_fields = action_type_registry.get_by_type(
                CreateFieldActionType
            ).do(request.user, table, type_name, return_updated_fields=True, **data)

        serializer = field_type_registry.get_serializer(
            field, FieldSerializerWithRelatedFields, related_fields=updated_fields
        )
        return Response(serializer.data)


class FieldView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the field related to the provided value.",
            )
        ],
        tags=["Database table fields"],
        operation_id="get_database_table_field",
        description=(
            "Returns the existing field if the authorized user has access to the "
            "related database's workspace. Depending on the type different properties "
            "could be returned."
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                field_type_registry, FieldSerializer
            ),
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
        }
    )
    def get(self, request, field_id):
        """Selects a single field and responds with a serialized version."""

        field = FieldHandler().get_field(field_id)
        CoreHandler().check_permissions(
            request.user,
            ReadFieldOperationType.type,
            workspace=field.table.database.workspace,
            context=field,
        )

        serializer = field_type_registry.get_serializer(field, FieldSerializer)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Updates the field related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="update_database_table_field",
        description=(
            "Updates the existing field if the authorized user has access to the "
            "related database's workspace. The type can also be changed and depending on "
            "that type, different additional properties can optionally be set. If you "
            "change the field type it could happen that the data conversion fails, in "
            "that case the `ERROR_CANNOT_CHANGE_FIELD_TYPE` is returned, but this "
            "rarely happens. If a data value cannot be converted it is set to `null` "
            "so data might go lost."
            "If updated the field causes other fields to change then the specific"
            "instances of those fields will be included in the related fields "
            "response key."
        ),
        request=DiscriminatorCustomFieldsMappingSerializer(
            field_type_registry,
            UpdateFieldSerializer,
            request=True,
        ),
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                field_type_registry, FieldSerializerWithRelatedFields
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_CANNOT_CHANGE_FIELD_TYPE",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_RESERVED_BASEROW_FIELD_NAME",
                    "ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS",
                    "ERROR_INVALID_BASEROW_FIELD_NAME",
                    "ERROR_FIELD_SELF_REFERENCE",
                    "ERROR_FIELD_CIRCULAR_REFERENCE",
                ]
            ),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @atomic_with_retry_on_deadlock()
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            CannotChangeFieldType: ERROR_CANNOT_CHANGE_FIELD_TYPE,
            FieldWithSameNameAlreadyExists: ERROR_FIELD_WITH_SAME_NAME_ALREADY_EXISTS,
            ReservedBaserowFieldNameException: ERROR_RESERVED_BASEROW_FIELD_NAME,
            InvalidBaserowFieldName: ERROR_INVALID_BASEROW_FIELD_NAME,
            SelfReferenceFieldDependencyError: ERROR_FIELD_SELF_REFERENCE,
            CircularFieldDependencyError: ERROR_FIELD_CIRCULAR_REFERENCE,
            FailedToLockFieldDueToConflict: ERROR_FAILED_TO_LOCK_FIELD_DUE_TO_CONFLICT,
            ImmutableFieldType: ERROR_IMMUTABLE_FIELD_TYPE,
            ImmutableFieldProperties: ERROR_IMMUTABLE_FIELD_PROPERTIES,
            SelectOptionDoesNotBelongToField: ERROR_SELECT_OPTION_DOES_NOT_BELONG_TO_FIELD,
            DbIndexNotSupportedError: ERROR_DB_INDEX_NOT_SUPPORTED,
            FieldConstraintException: ERROR_FIELD_CONSTRAINT,
            InvalidFieldConstraint: ERROR_INVALID_FIELD_CONSTRAINT,
            FieldConstraintDoesNotSupportDefaultValueError: ERROR_FIELD_CONSTRAINT_DOES_NOT_SUPPORT_DEFAULT_VALUE,
        }
    )
    @require_request_data_type(dict)
    def patch(self, request, field_id):
        """Updates the field if the user belongs to the workspace."""

        field = FieldHandler().get_specific_field_for_update(field_id)
        field_type = type_from_data_or_registry(
            request.data, field_type_registry, field
        )
        data = validate_data_custom_fields(
            field_type.type,
            field_type_registry,
            request.data,
            base_serializer_class=UpdateFieldSerializer,
        )

        # Because each field type can raise custom exceptions at while updating the
        # field we need to be able to map those to the correct API exceptions which are
        # defined in the type.
        with field_type.map_api_exceptions():
            field, related_fields = action_type_registry.get_by_type(
                UpdateFieldActionType
            ).do(request.user, field, field_type.type, **data)

        serializer = field_type_registry.get_serializer(
            field, FieldSerializerWithRelatedFields, related_fields=related_fields
        )
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Deletes the field related to the provided value.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="delete_database_table_field",
        description=(
            "Deletes the existing field if the authorized user has access to the "
            "related database's workspace. Note that all the related data to that field "
            "is also deleted. Primary fields cannot be deleted because their value "
            "represents the row. "
            "If deleting the field causes other fields to change then the specific"
            "instances of those fields will be included in the related fields "
            "response key."
        ),
        responses={
            200: RelatedFieldsSerializer,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_CANNOT_DELETE_PRIMARY_FIELD",
                    "ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM",
                ]
            ),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @atomic_with_retry_on_deadlock()
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            CannotDeletePrimaryField: ERROR_CANNOT_DELETE_PRIMARY_FIELD,
            CannotDeleteAlreadyDeletedItem: ERROR_CANNOT_DELETE_ALREADY_DELETED_ITEM,
        }
    )
    def delete(self, request, field_id):
        """Deletes an existing field if the user belongs to the workspace."""

        field = FieldHandler().get_field(field_id)
        field_type = field_type_registry.get_by_model(field.specific_class)
        with field_type.map_api_exceptions():
            updated_fields = action_type_registry.get_by_type(DeleteFieldActionType).do(
                request.user, field
            )

        return Response(RelatedFieldsSerializer({}, related_fields=updated_fields).data)


class UniqueRowValueFieldView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="Returns the values related to the provided field.",
            ),
            OpenApiParameter(
                name="limit",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.INT,
                description="Defines how many values should be returned.",
            ),
            OpenApiParameter(
                name="split_comma_separated",
                location=OpenApiParameter.QUERY,
                type=OpenApiTypes.BOOL,
                description="Indicates whether the original column values must be "
                "splitted by comma.",
            ),
        ],
        tags=["Database table fields"],
        operation_id="get_database_field_unique_row_values",
        description=(
            "Returns a list of all the unique row values for an existing field, sorted "
            "in order of frequency."
        ),
        responses={
            200: UniqueRowValuesSerializer,
            400: get_error_schema(["ERROR_USER_NOT_IN_GROUP"]),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            IncompatibleFieldTypeForUniqueValues: ERROR_INCOMPATIBLE_FIELD_TYPE_FOR_UNIQUE_VALUES,
        }
    )
    @validate_query_parameters(UniqueRowValueParamsSerializer)
    def get(self, request, field_id, query_params):
        field = FieldHandler().get_field(field_id)
        limit = query_params.get("limit")
        split_comma_separated = query_params.get("split_comma_separated")

        if not limit or limit > settings.BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT:
            limit = settings.BASEROW_UNIQUE_ROW_VALUES_SIZE_LIMIT

        values = FieldHandler().get_unique_row_values(
            field, limit, split_comma_separated=split_comma_separated
        )

        return Response(UniqueRowValuesSerializer({"values": values}).data)


class AsyncDuplicateFieldView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="field_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The field to duplicate.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="duplicate_table_field",
        description=(
            "Duplicates the table with the provided `table_id` parameter "
            "if the authorized user has access to the database's workspace."
        ),
        request=None,
        responses={
            202: DuplicateFieldJobType().response_serializer_class,
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_MAX_JOB_COUNT_EXCEEDED",
                ]
            ),
            404: get_error_schema(["ERROR_FIELD_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            MaxJobCountExceeded: ERROR_MAX_JOB_COUNT_EXCEEDED,
        }
    )
    @validate_body(DuplicateFieldParamsSerializer)
    def post(self, request: Request, field_id: int, data: Dict[str, Any]) -> Response:
        """Creates a job to duplicate a field in a table."""

        job = JobHandler().create_and_start_job(
            request.user,
            DuplicateFieldJobType.type,
            field_id=field_id,
            duplicate_data=data["duplicate_data"],
        )

        serializer = job_type_registry.get_serializer(job, JobSerializer)
        return Response(serializer.data, status=status.HTTP_202_ACCEPTED)


class ChangePrimaryFieldView(APIView):
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="table_id",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.INT,
                description="The table where to update the primary field in.",
            ),
            CLIENT_SESSION_ID_SCHEMA_PARAMETER,
            CLIENT_UNDO_REDO_ACTION_GROUP_ID_SCHEMA_PARAMETER,
        ],
        tags=["Database table fields"],
        operation_id="change_primary_field",
        description=(
            "Changes the primary field of a table to the one provided in the body "
            "payload."
        ),
        request=ChangePrimaryFieldParamsSerializer,
        responses={
            200: DiscriminatorCustomFieldsMappingSerializer(
                field_type_registry, FieldSerializer
            ),
            400: get_error_schema(
                [
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_REQUEST_BODY_VALIDATION",
                    "ERROR_USER_NOT_IN_GROUP",
                    "ERROR_FIELD_IS_ALREADY_PRIMARY",
                    "ERROR_FIELD_NOT_IN_TABLE",
                    "ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE",
                    "ERROR_TABLE_HAS_NO_PRIMARY_FIELD",
                ]
            ),
            404: get_error_schema(
                ["ERROR_TABLE_DOES_NOT_EXIST", "ERROR_FIELD_DOES_NOT_EXIST"]
            ),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            TableDoesNotExist: ERROR_TABLE_DOES_NOT_EXIST,
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            UserNotInWorkspace: ERROR_USER_NOT_IN_GROUP,
            FieldIsAlreadyPrimary: ERROR_FIELD_IS_ALREADY_PRIMARY,
            FieldNotInTable: ERROR_FIELD_NOT_IN_TABLE,
            IncompatiblePrimaryFieldTypeError: ERROR_INCOMPATIBLE_PRIMARY_FIELD_TYPE,
            TableHasNoPrimaryField: ERROR_TABLE_HAS_NO_PRIMARY_FIELD,
        }
    )
    @validate_body(ChangePrimaryFieldParamsSerializer)
    def post(self, request: Request, table_id: int, data: Dict[str, Any]) -> Response:
        """Changes the primary field of the given table."""

        # Get the table for update because we want to prevent other fields being
        # changed to the primary field.
        table = TableHandler().get_table_for_update(table_id)
        new_primary_field = FieldHandler().get_specific_field_for_update(
            data["new_primary_field_id"]
        )

        new_primary_field, old_primary_field = action_type_registry.get_by_type(
            ChangePrimaryFieldActionType
        ).do(request.user, table, new_primary_field)

        serializer = field_type_registry.get_serializer(
            new_primary_field,
            FieldSerializerWithRelatedFields,
            related_fields=[old_primary_field],
        )
        return Response(serializer.data)


class PasswordFieldAuthenticationView(APIView):
    authentication_classes = APIView.authentication_classes + [TokenAuthentication]
    permission_classes = (IsAuthenticated,)

    @extend_schema(
        tags=["Database table fields"],
        operation_id="password_field_authentication",
        description=(
            "Checks if the provided password and row matches what is stored in the "
            "cell. The field must have `allow_endpoint_authentication` set to `true` "
            "in order to work."
        ),
        request=PasswordFieldAuthenticationSerializer,
        responses={
            200: PasswordFieldAuthenticationResponseSerializer,
            400: get_error_schema(
                [
                    "ERROR_REQUEST_BODY_VALIDATION",
                ]
            ),
            401: get_error_schema(
                [
                    "ERROR_NO_PERMISSION_TO_TABLE",
                    "ERROR_INVALID_PASSWORD_FIELD_PASSWORD",
                ]
            ),
            404: get_error_schema(
                ["ERROR_FIELD_DOES_NOT_EXIST", "ERROR_ROW_DOES_NOT_EXIST"]
            ),
        },
    )
    @map_exceptions(
        {
            FieldDoesNotExist: ERROR_FIELD_DOES_NOT_EXIST,
            RowDoesNotExist: ERROR_ROW_DOES_NOT_EXIST,
            NoPermissionToTable: ERROR_NO_PERMISSION_TO_TABLE,
            InvalidPasswordFieldPassword: ERROR_INVALID_PASSWORD_FIELD_PASSWORD,
        }
    )
    @validate_body(PasswordFieldAuthenticationSerializer)
    def post(self, request: Request, data: Dict[str, Any]) -> Response:
        base_queryset = PasswordField.objects.filter(
            allow_endpoint_authentication=True
        ).select_related("table")
        field = FieldHandler().get_field(data["field_id"], base_queryset=base_queryset)
        table = field.table

        token_handler = TokenHandler()
        db_token = token_handler.get_token_from_request(request)
        if db_token is not None:
            token_handler.check_table_permissions(db_token, "read", table)

        model = field.table.get_model()
        row_id = data.get("row_id")
        row = RowHandler().get_row(request.user, table, row_id, model)
        raw_password = data.get("password")
        hashed_password = getattr(row, field.db_column)
        is_correct = bool(
            hashed_password and check_password(raw_password, hashed_password)
        )

        if not is_correct:
            raise InvalidPasswordFieldPassword()

        serializer = PasswordFieldAuthenticationResponseSerializer({"is_correct": True})
        return Response(serializer.data, status=status.HTTP_200_OK)
