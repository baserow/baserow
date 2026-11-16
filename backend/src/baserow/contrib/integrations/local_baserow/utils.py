from typing import Any, Callable, List, Optional, Union

from django.contrib.auth.models import AbstractUser

from loguru import logger
from rest_framework.fields import Field
from rest_framework.serializers import Serializer

from baserow.contrib.database.fields.operations import ListFieldsOperationType
from baserow.contrib.database.fields.utils import (
    guess_json_type_from_response_serializer_field,
)
from baserow.contrib.database.table.models import Table
from baserow.core.formula.service_file import ServiceFile
from baserow.core.formula.validator import (
    ensure_array,
    ensure_boolean,
    ensure_date,
    ensure_datetime,
    ensure_integer,
    ensure_string,
)
from baserow.core.handler import CoreHandler
from baserow.core.registries import subject_type_registry
from baserow.core.services.exceptions import (
    ServiceImproperlyConfiguredDispatchException,
)
from baserow.core.services.models import Service
from baserow.core.types import Subject
from baserow.core.user_files.exceptions import (
    FileSizeTooLargeError,
    FileURLCouldNotBeReached,
)


def prepare_files_for_db(
    value: Any,
    actor: Subject,
) -> List[dict]:
    """
    Transforms the generic files from the frontend into files that can be associated
    with rows.

    :param value: The value from the request.
    :param actor: The subject dispatching the service.
    """

    uploading_user = (
        actor if subject_type_registry.get_by_model(actor).is_interactive_user else None
    )

    # It must be an array
    data = ensure_array(value)
    result = []

    for f in data:
        if isinstance(f, ServiceFile):
            try:
                result.append(f.to_file_field_dict(uploading_user))
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
                result.append(service_file.to_file_field_dict(uploading_user))
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
    serializer_field: Union[Field, Serializer], actor: Subject
) -> Optional[Callable]:
    """
    Return the appropriate cast function for a serializer type.

    :param serializer_field: The serializer field.
    :param actor: The subject dispatching the service.
    :return: A function that can be used to cast a value to this serializer field type.
    """

    from baserow.contrib.database.api.fields.serializers import (
        FileFieldRequestSerializer,
    )

    if isinstance(serializer_field, FileFieldRequestSerializer):
        # Special case for file field serializer, we want to convert files data to
        # match expected value. We have to upload the files first before we can
        # includes them in the row.
        return lambda value: prepare_files_for_db(value, actor)

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


class ServiceTableAccess:
    """
    Whether a user may see the fields of the table a service reads or writes.
    The schema and context data of such a service name the table's fields, so
    they are only shown to a user who may list them. Each table is checked once,
    so one instance can be shared by every service of a request.
    """

    def __init__(self, user: Optional[AbstractUser]):
        self.user = user
        self._allowed: dict[int, bool] = {}

    def allows(self, service: Service) -> bool:
        """
        :param service: The specific service.
        :return: False when the service has a table whose fields the user may
            not list, True otherwise.
        """

        table_id = getattr(service, "table_id", None)
        return table_id is None or self.allows_table(table_id)

    def allows_table(self, table_id: int) -> bool:
        """Whether the user may list the fields of the table."""

        if self.user is None:
            return False

        if table_id not in self._allowed:
            table = (
                Table.objects_and_trash.select_related("database__workspace")
                .filter(id=table_id)
                .first()
            )
            self._allowed[table_id] = (
                table is not None
                and CoreHandler().check_permissions(
                    self.user,
                    ListFieldsOperationType.type,
                    workspace=table.database.workspace,
                    context=table,
                    raise_permission_exceptions=False,
                )
            )
        return self._allowed[table_id]
