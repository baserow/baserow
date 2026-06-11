from typing import Any, Callable, List, Optional, Union

from django.contrib.auth.models import AbstractUser

from loguru import logger
from rest_framework.fields import Field
from rest_framework.serializers import Serializer

from baserow.contrib.database.fields.utils import (
    guess_json_type_from_response_serializer_field,
)
from baserow.contrib.integrations.local_baserow.models import LocalBaserowUpsertRow
from baserow.core.formula.service_file import ServiceFile
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


def prepare_files_for_db(
    value: Any,
    user: AbstractUser,
) -> List[dict]:
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
        if isinstance(f, ServiceFile):
            try:
                result.append(f.to_file_field_dict(user))
            except FileURLCouldNotBeReached as exc:
                file_name = f.visible_name or f.name or "unnamed"
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The file {file_name} couldn't be reached."
                ) from exc
            except FileSizeTooLargeError as exc:
                file_name = f.visible_name or f.name or "unnamed"
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The file {file_name} is too large."
                ) from exc
            except Exception as exc:
                file_name = f.visible_name or f.name or "unnamed"
                logger.exception(f"Unprocessed file {file_name}")
                raise ServiceImproperlyConfiguredDispatchException(
                    f"The file {file_name} couldn't "
                    f"be processed for unknown reason: {exc}"
                ) from exc
        elif isinstance(f, dict) and f.get("__file__"):
            file_name = f.get("name", "unnamed")
            try:
                service_file = ServiceFile.from_serialized(f)
                result.append(service_file.to_file_field_dict(user))
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
