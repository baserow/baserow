from typing import Any, Callable, List, Optional, Union
from urllib.parse import urlparse

from django.contrib.auth.models import AbstractUser

from loguru import logger
from rest_framework.fields import Field
from rest_framework.serializers import Serializer

from baserow.contrib.database.fields.utils import (
    guess_json_type_from_response_serializer_field,
)
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
