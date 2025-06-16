from django.db import transaction

from drf_spectacular.openapi import OpenApiParameter, OpenApiTypes
from drf_spectacular.utils import extend_schema
from rest_framework.fields import empty
from rest_framework.parsers import MultiPartParser
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.response import Response
from rest_framework.views import APIView

from baserow.api.decorators import map_exceptions
from baserow.api.schemas import get_error_schema
from baserow.api.user_files.errors import ERROR_FILE_SIZE_TOO_LARGE, ERROR_INVALID_FILE
from baserow.api.user_files.serializers import UserFileSerializer
from baserow.api.utils import validate_data
from baserow.contrib.database.api.fields.errors import ERROR_FIELD_DATA_CONSTRAINT
from baserow.contrib.database.api.rows.errors import ERROR_CANNOT_CREATE_ROWS_IN_TABLE
from baserow.contrib.database.api.rows.serializers import (
    get_example_row_serializer_class,
    get_row_serializer_class,
)
from baserow.contrib.database.api.views.errors import (
    ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW,
    ERROR_VIEW_DOES_NOT_EXIST,
)
from baserow.contrib.database.api.views.utils import get_public_view_authorization_token
from baserow.contrib.database.fields.exceptions import FieldDataConstraintException
from baserow.contrib.database.fields.models import FileField, LongTextField
from baserow.contrib.database.rows.exceptions import CannotCreateRowsInTable
from baserow.contrib.database.views.actions import SubmitFormActionType
from baserow.contrib.database.views.exceptions import (
    NoAuthorizationToPubliclySharedView,
    ViewDoesNotExist,
)
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import FormView
from baserow.contrib.database.views.registries import view_ownership_type_registry
from baserow.contrib.database.views.validators import (
    allow_only_specific_select_options_factory,
    no_empty_form_values_when_required_validator,
)
from baserow.core.action.registries import action_type_registry
from baserow.core.user_files.exceptions import (
    FileSizeTooLargeError,
    InvalidFileStreamError,
)
from baserow.core.user_files.handler import UserFileHandler

from .errors import (
    ERROR_FORM_DOES_NOT_EXIST,
    ERROR_NO_PERMISSION_TO_PUBLICLY_SHARED_FORM,
    ERROR_VIEW_HAS_NO_PUBLIC_FILE_FIELD,
)
from .exceptions import ViewHasNoPublicFileFieldError
from .serializers import FormViewSubmittedSerializer, PublicFormViewSerializer


class SubmitFormViewView(APIView):
    permission_classes = (AllowAny,)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                required=True,
                description="The slug related to the form form.",
            )
        ],
        tags=["Database table form view"],
        operation_id="get_meta_database_table_form_view",
        description=(
            "Returns the metadata related to the form view if the form is publicly "
            "shared or if the user has access to the related workspace. This data can "
            "be used to construct a form with the right fields."
        ),
        responses={
            200: PublicFormViewSerializer,
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_PUBLICLY_SHARED_FORM"]),
            404: get_error_schema(["ERROR_FORM_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_FORM_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_PERMISSION_TO_PUBLICLY_SHARED_FORM,
        }
    )
    def get(self, request: Request, slug: str) -> Response:
        form = ViewHandler().get_public_view_by_slug(
            request.user,
            slug,
            view_model=FormView,
            authorization_token=get_public_view_authorization_token(request),
        )
        serializer = PublicFormViewSerializer(form)
        return Response(serializer.data)

    @extend_schema(
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                required=True,
                description="The slug related to the form.",
            )
        ],
        tags=["Database table form view"],
        operation_id="submit_database_table_form_view",
        description=(
            "Submits the form if the form is publicly shared or if the user has "
            "access to the related workspace. The provided data will be validated "
            "based on the fields that are in the form and the rules per field. If "
            "valid, a new row will be created in the table."
        ),
        request=get_example_row_serializer_class(example_type="post"),
        responses={
            200: FormViewSubmittedSerializer,
            401: get_error_schema(["ERROR_NO_PERMISSION_TO_PUBLICLY_SHARED_FORM"]),
            404: get_error_schema(["ERROR_FORM_DOES_NOT_EXIST"]),
        },
    )
    @map_exceptions(
        {
            ViewDoesNotExist: ERROR_FORM_DOES_NOT_EXIST,
            NoAuthorizationToPubliclySharedView: ERROR_NO_PERMISSION_TO_PUBLICLY_SHARED_FORM,
            CannotCreateRowsInTable: ERROR_CANNOT_CREATE_ROWS_IN_TABLE,
            FieldDataConstraintException: ERROR_FIELD_DATA_CONSTRAINT,
        }
    )
    @transaction.atomic
    def post(self, request: Request, slug: str) -> Response:
        handler = ViewHandler()
        form = handler.get_public_view_by_slug(
            request.user,
            slug,
            view_model=FormView,
            authorization_token=get_public_view_authorization_token(request),
        )
        view_ownership_type_registry.get(
            form.ownership_type
        ).before_form_view_submitted(form, request)
        model = form.table.get_model()

        options = form.active_field_options
        field_kwargs = {}
        for option in options:
            validators = []
            o = {}
            if option.is_required():
                o["required"] = True
                o["default"] = empty
                validators.append(no_empty_form_values_when_required_validator)
            if not option.include_all_select_options:
                validators.append(
                    allow_only_specific_select_options_factory(
                        [
                            allowed_select_option.id
                            for allowed_select_option in option.allowed_select_options.all()
                        ]
                    )
                )
            if len(validators) > 0 and len(o) > 0:
                name = model._field_objects[option.field_id]["name"]
                o["validators"] = validators
                field_kwargs[name] = o

        field_ids = [option.field_id for option in options]
        validation_serializer = get_row_serializer_class(
            model, field_ids=field_ids, field_kwargs=field_kwargs
        )
        values = validate_data(
            validation_serializer, request.data, return_validated=True
        )

        created_row = action_type_registry.get_by_type(SubmitFormActionType).do(
            request.user, form, values, model, options
        )
        form.row_id = created_row.id
        return Response(FormViewSubmittedSerializer(form).data)


class FormUploadFileView(APIView):
    permission_classes = (AllowAny,)
    parser_classes = (MultiPartParser,)

    @extend_schema(
        tags=["Database table form view"],
        operation_id="upload_file_form_view",
        description=(
            "Uploads a file anonymously to Baserow by uploading the file "
            "contents directly. A `file` multipart is expected containing the file "
            "contents."
        ),
        parameters=[
            OpenApiParameter(
                name="slug",
                location=OpenApiParameter.PATH,
                type=OpenApiTypes.STR,
                description="Submits files only if the view with the provided slug"
                "has a public file field.",
            ),
        ],
        request=None,
        responses={
            200: UserFileSerializer,
            401: get_error_schema(["ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW"]),
            400: get_error_schema(
                [
                    "ERROR_INVALID_FILE",
                    "ERROR_FILE_SIZE_TOO_LARGE",
                    "ERROR_VIEW_HAS_NO_PUBLIC_FILE_FIELD",
                ]
            ),
            404: get_error_schema(["ERROR_VIEW_DOES_NOT_EXIST"]),
        },
    )
    @transaction.atomic
    @map_exceptions(
        {
            InvalidFileStreamError: ERROR_INVALID_FILE,
            FileSizeTooLargeError: ERROR_FILE_SIZE_TOO_LARGE,
            ViewDoesNotExist: ERROR_VIEW_DOES_NOT_EXIST,
            ViewHasNoPublicFileFieldError: ERROR_VIEW_HAS_NO_PUBLIC_FILE_FIELD,
            NoAuthorizationToPubliclySharedView: (
                ERROR_NO_AUTHORIZATION_TO_PUBLICLY_SHARED_VIEW
            ),
        }
    )
    def post(self, request, slug):
        """Uploads a file anonymously using a public form view."""

        if "file" not in request.FILES:
            raise InvalidFileStreamError("No file was provided.")

        # Make sure that the form provided has a public file field.
        view = ViewHandler().get_public_view_by_slug(
            request.user,
            slug,
            FormView,
            authorization_token=get_public_view_authorization_token(request),
        )
        has_public_file_field = FileField.objects.filter(
            formview=view, formviewfieldoptions__enabled=True
        ).exists()
        has_public_rich_text_field = LongTextField.objects.filter(
            formview=view,
            formviewfieldoptions__enabled=True,
            long_text_enable_rich_text=True,
        ).exists()

        if not has_public_file_field and not has_public_rich_text_field:
            raise ViewHasNoPublicFileFieldError()

        file = request.FILES.get("file")

        # Setting user=None will upload the file anonymously.
        user_file = UserFileHandler().upload_user_file(None, file.name, file)

        serializer = UserFileSerializer(user_file)
        return Response(serializer.data)
