from typing import Any, Callable, Iterable, List, Optional, Union

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

    uploading_user = actor if isinstance(actor, AbstractUser) else None

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
    Whether a user may see the fields of the tables a service reads or writes.
    The schema and context data of such a service name the table's fields, so
    they are only shown to a user who may list them, whatever else they may see
    of the table, like a view of it. A table that no longer exists is one they
    may not see. Each table is checked once, so one instance can be shared by every
    service of a request.
    """

    operation = ListFieldsOperationType

    def __init__(self, user: Optional[AbstractUser]):
        self.user = user
        self._allowed: dict[int, bool] = {}
        self._tables: dict[int, Optional[Table]] = {}

    def _get_tables(self, table_ids: Iterable[int]) -> dict[int, Optional[Table]]:
        missing = {table_id for table_id in table_ids if table_id not in self._tables}
        if missing:
            self._tables.update(dict.fromkeys(missing))
            self._tables.update(
                {
                    table.id: table
                    for table in Table.objects_and_trash.select_related(
                        "database__workspace"
                    ).filter(id__in=missing)
                }
            )
        return {table_id: self._tables[table_id] for table_id in table_ids}

    def allows(self, service: Service) -> bool:
        """
        :param service: The specific service.
        :return: False when the service has a table whose fields the user may
            not list, True otherwise.
        """

        return all(
            self.allows_table(table_id)
            for table_id in service.get_type().get_table_ids(service)
        )

    def allows_table(self, table_id: int) -> bool:
        """Whether the user may list the fields of the table."""

        if self.user is None:
            return False

        if table_id not in self._allowed:
            table = self._get_tables([table_id])[table_id]
            self._allowed[table_id] = table is not None and (
                CoreHandler().check_permissions(
                    self.user,
                    self.operation.type,
                    workspace=table.database.workspace,
                    context=table,
                    raise_permission_exceptions=False,
                )
            )
        return self._allowed[table_id]

    def users_allowed_on(
        self, table_ids: Iterable[int], users: Iterable[AbstractUser]
    ) -> set[AbstractUser]:
        """
        :return: The users among the given ones who may list the fields of every
            one of the tables, with a check for all of them at once for each table.
        """

        table_ids = list(table_ids)
        tables = self._get_tables(table_ids)
        allowed = set(users) if all(tables.values()) else set()
        for table_id in table_ids:
            if not allowed:
                break
            table = tables[table_id]
            allowed &= set(
                CoreHandler().check_permission_for_multiple_actors(
                    list(allowed),
                    self.operation.type,
                    table.database.workspace,
                    context=table,
                )
            )
        return allowed
