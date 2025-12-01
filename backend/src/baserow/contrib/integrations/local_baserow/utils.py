from typing import Any, Callable, Dict, List, Optional, Union
from urllib.parse import urlparse

from django.contrib.auth.models import AbstractUser

from drf_spectacular.types import OPENAPI_TYPE_MAPPING
from loguru import logger
from rest_framework.fields import (
    BooleanField,
    CharField,
    ChoiceField,
    DateField,
    DateTimeField,
    DecimalField,
    Field,
    FloatField,
    IntegerField,
    ListField,
    SerializerMethodField,
    TimeField,
    UUIDField,
)
from rest_framework.serializers import ListSerializer, Serializer

from baserow.contrib.database.api.fields.serializers import DurationFieldSerializer
from baserow.contrib.integrations.local_baserow.models import LocalBaserowUpsertRow
from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_date,
    ensure_datetime,
    ensure_integer,
    ensure_string,
)
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.user_files.exceptions import (
    FileSizeTooLargeError,
    FileURLCouldNotBeReached,
)
from baserow.core.user_files.handler import UserFileHandler


def guess_json_type_from_response_serializer_field(
    serializer_field: Union[Field, Serializer]
) -> Dict[str, Any]:
    """
    Responsible for taking a serializer field, and guessing what its JSON
    type will be. If the field is a ListSerializer, and it has a child serializer,
    we add the child's type as well.

    :param serializer_field: The serializer field.
    :return: A dictionary to add to our schema.
    """

    if isinstance(serializer_field, (UUIDField, CharField, DecimalField, FloatField)):
        # DecimalField/FloatField values are returned as strings from the API.
        base_type = "string"
    elif isinstance(serializer_field, DateField):
        return {"type": "string", "format": "date"}
    elif isinstance(serializer_field, DateTimeField):
        return {"type": "string", "format": "date-time"}
    elif isinstance(serializer_field, (TimeField, DurationFieldSerializer)):
        base_type = "string"
    elif isinstance(serializer_field, ChoiceField):
        base_type = "string"
    elif isinstance(serializer_field, IntegerField):
        base_type = "number"
    elif isinstance(serializer_field, BooleanField):
        base_type = "boolean"
    elif isinstance(serializer_field, ListSerializer):
        # ListSerializer.child is required, so add its subtype.
        sub_type = guess_json_type_from_response_serializer_field(
            serializer_field.child
        )
        return {"type": "array", "items": sub_type}
    elif isinstance(serializer_field, ListField):
        # ListField.child is required, so add its subtype.
        sub_type = guess_json_type_from_response_serializer_field(
            serializer_field.child
        )
        return {"type": "array", "items": sub_type}
    elif isinstance(serializer_field, SerializerMethodField):
        # Try to guess the json type of SerializerMethodField based on the
        # OpenAPI annotations.
        #
        # When a method serializer uses @extend_schema_field decorator it will
        # include a dictionary called "_spectacular_annotation" that contains
        # the type of the field to return.
        #
        # NOTE: This only works for primitive types (e.g, string, boolean, etc.)
        # and not for composite ones (e.g, object, lists, etc.).
        base_type = None
        method = getattr(serializer_field.parent, serializer_field.method_name)
        if hasattr(method, "_spectacular_annotation"):
            field = method._spectacular_annotation.get("field")
            mapping = OPENAPI_TYPE_MAPPING.get(field)
            if isinstance(mapping, dict):
                base_type = mapping.get("type", None)

    elif issubclass(serializer_field.__class__, Serializer):
        properties = {}
        for name, child_serializer in serializer_field.fields.items():
            guessed_type = guess_json_type_from_response_serializer_field(
                child_serializer
            )
            if guessed_type["type"] is not None:
                properties[name] = {
                    "title": name,
                    **guessed_type,
                }

        return {"type": "object", "properties": properties}
    else:
        base_type = None

    return {"type": base_type}


def _handle_file(file_obj: dict, user: AbstractUser) -> dict:
    """
    Handles one file by:
    - uploading it if it comes from the frontend (uploaded)
    - uploading it from the url if it has one
    - loading the existing user file if the url match the pattern
    """

    if "url" in file_obj:
        # We have just the url of the file
        url = file_obj["url"]
        path = urlparse(url).path
        segments = [segment for segment in path.split("/") if segment]
        last_segment = segments[-1] if segments else None

        if UserFileHandler().is_user_file_name(last_segment):
            # it's a user file that was already uploaded, we can get it from the DB
            user_file = UserFileHandler().get_user_file_by_name(last_segment)
        else:
            # It's a random URL let's try to upload it as new user file
            user_file = UserFileHandler().upload_user_file_by_url(
                user,
                url,
                file_name=file_obj.get("name"),
            )
        return user_file.serialize()
    elif "file" in file_obj:
        # it's a file sent with the request so we upload it first
        user_file = UserFileHandler().upload_user_file(
            user,
            file_obj["name"],
            file_obj["file"],
        )
        return user_file.serialize()
    else:
        return file_obj


def prepare_files_for_db(value: Any, user: AbstractUser) -> List[dict]:
    """
    Transforms the generic files from the frontend into files that can be associated
    with rows.

    :param value: The value from the request.
    :param user: The user to store the file with.
    """

    # It must be an array
    data = ensure_array(value)
    result = []

    for f in data:
        if isinstance(f, dict) and f.get("__file__"):
            file_name = f.get("name", "unnamed")
            try:
                result.append(_handle_file(f, user))
            except FileURLCouldNotBeReached as exc:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The file {file_name} couldn't be reached."
                ) from exc
            except FileSizeTooLargeError as exc:
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The file {file_name} is too large."
                ) from exc
            except Exception as exc:
                logger.exception(f"Unprocessed file {file_name}")
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The file {file_name} couldn't "
                    f"be processed for unknown reason: {exc}"
                ) from exc

        else:
            # Otherwise we keep it as it as we don't know what to do
            result.append(f)
    return result


def guess_cast_function_from_response_serializer_field(
    serializer_field: Union[Field, Serializer], service: LocalBaserowUpsertRow
) -> Optional[Callable]:
    """
    Return the appropriate cast function for a serializer type.

    :param serializer_field: The serializer field.
    :return: A function that can be used to cast a value to this serializer field type.
    """

    from baserow.contrib.database.api.fields.serializers import (
        FileFieldRequestSerializer,
    )

    if isinstance(serializer_field, FileFieldRequestSerializer):
        # Special case for file field serializer, we want to convert files data to
        # match expected value. We have to upload the files first before we can
        # includes them in the row.
        return lambda value: prepare_files_for_db(
            value, service.integration.authorized_user
        )

    json_type = guess_json_type_from_response_serializer_field(serializer_field)

    ensure_map = {
        "string": {
            "date": ensure_date,
            "date-time": ensure_datetime,
            "default": ensure_string,
        },
        "number": {"default": ensure_integer},
        "boolean": {"default": ensure_boolean},
        "array": {"default": ensure_array},
    }
    json_type_choice = ensure_map.get(json_type["type"])
    return (
        json_type_choice[json_type.get("format") or "default"]
        if json_type_choice
        else None
    )
