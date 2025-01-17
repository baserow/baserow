from dataclasses import dataclass
from dataclasses import field as dataclass_field
from typing import List

from django.db.models import QuerySet

from rest_framework import serializers

from baserow.config.settings.utils import str_to_bool
from baserow.contrib.database.api.rows.exceptions import InvalidJoinParameterException
from baserow.contrib.database.fields.exceptions import (
    FieldDoesNotExist,
    IncompatibleField,
)
from baserow.contrib.database.fields.models import (
    DEFAULT_DECIMAL_SEPARATOR,
    DEFAULT_THOUSAND_SEPARATOR,
    NUMBER_SEPARATORS,
    Field,
)
from baserow.contrib.database.fields.utils import get_field_id_from_field_key
from baserow.core.db import specific_iterator
from baserow.core.utils import split_comma_separated_string


def get_include_exclude_field_ids(table, include=None, exclude=None):
    """
    Returns a list containing the field ids based on the value
    of the include and exclude parameters.

    :param table: The table where to select the fields from. Field id's that are
        not in the table won't be included.
    :type table: Table
    :param include: The field ids that must be included. Only the provided ones
        are going to be in the returned queryset. Multiple can be provided
        separated by comma
    :type include: Optional[str]
    :param exclude: The field ids that must be excluded. Only the ones that are not
        provided are going to be in the returned queryset. Multiple can be provided
        separated by comma.
    :type exclude: Optional[str]
    :rtype: None or List[str]
    """

    fields = get_include_exclude_fields(table, include, exclude)
    field_ids = None

    if include is not None or exclude is not None:
        if fields:
            field_ids = [field.get("id") for field in fields.values()]
        else:
            field_ids = []

    return field_ids


def get_include_exclude_fields(
    table, include=None, exclude=None, user_field_names=False, queryset=None
):
    """
    Returns a field queryset containing the requested fields based on the value
    and exclude parameter.

    :param table: The table where to select the fields from. Field id's that are
        not in the table won't be included.
    :type table: Table
    :param include: The field ids that must be included. Only the provided ones
        are going to be in the returned queryset. Multiple can be provided
        separated by comma
    :type include: Optional[str]
    :param exclude: The field ids that must be excluded. Only the ones that are not
        provided are going to be in the returned queryset. Multiple can be provided
        separated by comma.
    :type exclude: Optional[str]
    :return: A Field's QuerySet containing the allowed fields based on the provided
        input.
    :param user_field_names: If true then the value and exclude parameters are
        retreated as a comma separated list of user field names instead of id's
    :type user_field_names: bool
    :param queryset: Optional base fields queryset.
    :rtype: QuerySet
    """

    if queryset is None:
        queryset = Field.objects.filter(table=table)

    if user_field_names:
        includes = extract_field_names_from_string(include)
        excludes = extract_field_names_from_string(exclude)
        filter_type = "name__in"
    else:
        includes = extract_field_ids_from_string(include)
        excludes = extract_field_ids_from_string(exclude)
        filter_type = "id__in"

    if len(includes) == 0 and len(excludes) == 0:
        return None

    if len(includes) > 0:
        queryset = queryset.filter(**{filter_type: includes})

    if len(excludes) > 0:
        queryset = queryset.exclude(**{filter_type: excludes})

    return queryset


# noinspection PyMethodMayBeStatic
def extract_field_names_from_string(value):
    """
    Given a comma separated string of field names this function will split the
    string into a list of individual field names. For weird field names containing
    commas etc the field should be escaped with quotes.
    :param value: The string to split into a list of field names.
    :return: A list of field names.
    """

    if not value:
        return []

    return split_comma_separated_string(value)


def extract_field_ids_from_list(
    list_of_field_names: List[str], strict: bool = True
) -> List[int]:
    """
    Given a list of `Field.db_column`, this function will return a list of field ids.
    For example if you provide ['field_1', 'field_2'] then [1, 2] is returned.

    :param list_of_field_names: A list of field names.
    :param strict: If `true`, then the value must be a number or match the `field_3`
        pattern. If false, then it tries to extract any number from the value.
    :return: A list of field ids.
    """

    if not list_of_field_names:
        return []

    ids = [
        get_field_id_from_field_key(field_name, strict)
        for field_name in list_of_field_names
    ]
    return [_id for _id in ids if _id is not None]


def extract_field_ids_from_string(value):
    """
    Extracts the field ids from a string. Multiple ids can be separated by a comma.
    For example if you provide 'field_1,field_2' then [1, 2] is returned.

    :param value: A string containing multiple ids separated by comma.
    :type value: str
    :return: A list containing the field ids as integers.
    :rtype: list
    """

    if not value:
        return []

    ids = [get_field_id_from_field_key(v, False) for v in value.split(",")]
    return [_id for _id in ids if _id is not None]


def extract_user_field_names_from_params(query_params):
    """
    Extracts the user_field_names parameter from the query_params and returns
    boolean value
    """

    value = query_params.get("user_field_names", False)

    if value is False:
        return False

    if value is None or value == "":
        return True

    return str_to_bool(value)


def extract_send_webhook_events_from_params(query_params) -> bool:
    """
    Extracts the send_webhook_events parameter from the query_params and returns
    boolean value. Defaults to true if not provided or empty.
    """

    value = query_params.get("send_webhook_events")

    if value is None or value == "":
        return True

    return str_to_bool(value)


@dataclass
class LinkedTargetField:
    field_id: int
    field_ref: str  # field name or user field name
    field_serializer: serializers.Serializer

    def __eq__(self, other):
        # compare only field_id
        # for test purposes
        return self.field_id == other.field_id


@dataclass
class LinkRowJoin:
    link_row_field_id: int
    link_row_field_ref: str  # field name or user field name
    target_fields: list[LinkedTargetField] = dataclass_field(default_factory=list)


def extract_link_row_joins_from_request(
    request, link_row_fields: QuerySet["Field"], user_field_names: bool = False
) -> list[LinkRowJoin]:
    """
    Helper function to extract information about link row joins.

    :param request: The request object that should contain the requested
        lookups in the URL parameters.
    :param link_row_fields: The queryset of existing link row fields on the table
        that can be used.
    :param user_field_names: Whether user field names should be used both in
        the URL parameter and the output.
    :return: A list of valid link row joins with link row fields and their
        lookups.
    """

    requested_link_row_field_refs = [
        key.removesuffix("__join")
        for key in request.GET.keys()
        if key.endswith("__join")
    ]
    link_row_fields = specific_iterator(link_row_fields)
    existing_link_row_fields_by_ref = {
        link_row_field.get_field_ref(user_field_names): link_row_field
        for link_row_field in link_row_fields
    }
    all_link_row_field_exists = all(
        existing_link_row_fields_by_ref.get(link_param)
        for link_param in requested_link_row_field_refs
    )
    if not all_link_row_field_exists:
        raise FieldDoesNotExist()

    link_row_joins: dict[int, LinkRowJoin] = {}

    for link_row_field_ref in requested_link_row_field_refs:
        field = existing_link_row_fields_by_ref.get(link_row_field_ref)
        link_row_field = field.specific
        linked_table = link_row_field.link_row_table
        linked_table_model = linked_table.get_model()
        param_name = f"{link_row_field_ref}__join"
        if len(request.GET.getlist(param_name)) != 1:
            raise InvalidJoinParameterException()
        target_fields = request.GET.get(param_name, "").split(",")
        if len(target_fields) != len(set(target_fields)):
            raise InvalidJoinParameterException()
        for target_field_ref in target_fields:
            try:
                field_obj = (
                    linked_table_model.get_field_object_by_user_field_name(
                        target_field_ref
                    )
                    if user_field_names
                    else linked_table_model.get_field_object(target_field_ref)
                )
                field_type = field_obj["type"]
                if not field_type.can_be_target_of_adhoc_lookup:
                    raise IncompatibleField()
                serializer_kwargs = {}
                if user_field_names:
                    serializer_kwargs["source"] = f"field_{field_obj['field'].id}"
                linked_target_field = LinkedTargetField(
                    field_id=field_obj["field"].id,
                    field_ref=field_obj["field"].get_field_ref(user_field_names),
                    field_serializer=field_type.get_response_serializer_field(
                        field_obj["field"],
                        **serializer_kwargs,
                    ),
                )
                if link_row_field.id not in link_row_joins:
                    link_row_joins[link_row_field.id] = LinkRowJoin(
                        link_row_field_id=link_row_field.id,
                        link_row_field_ref=link_row_field_ref,
                        target_fields=[linked_target_field],
                    )
                else:
                    link_row_joins[link_row_field.id].target_fields.append(
                        linked_target_field
                    )
            except ValueError as ex:
                raise FieldDoesNotExist() from ex

    return list(link_row_joins.values())


def get_thousand_and_decimal_separator(value):
    thousand_sep, decimal_sep = NUMBER_SEPARATORS.get(value, {}).get("separators", None)
    if not thousand_sep or not decimal_sep:
        thousand_sep, decimal_sep = (
            DEFAULT_THOUSAND_SEPARATOR,
            DEFAULT_DECIMAL_SEPARATOR,
        )
    return thousand_sep.value, decimal_sep.value
