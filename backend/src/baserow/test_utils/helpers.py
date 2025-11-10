import json
import os
import uuid
from contextlib import ExitStack, contextmanager
from datetime import timedelta, timezone
from decimal import Decimal
from ipaddress import ip_network
from socket import AF_INET, AF_INET6, IPPROTO_TCP, SOCK_STREAM
from typing import Any, Dict, Generator, List, Optional, Type, Union
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.db import connection
from django.utils.dateparse import parse_date, parse_datetime

from freezegun import freeze_time
from pytest_unordered import unordered

from baserow.contrib.database.fields.field_helpers import (
    construct_all_possible_field_kwargs,
)
from baserow.contrib.database.fields.handler import FieldHandler
from baserow.contrib.database.fields.models import SelectOption
from baserow.contrib.database.models import Database
from baserow.contrib.database.rows.handler import RowHandler
from baserow.core.action.models import Action
from baserow.core.action.registries import ActionType
from baserow.core.models import Workspace
from baserow.core.psycopg import psycopg

User = get_user_model()


def _parse_datetime(datetime):
    return parse_datetime(datetime).replace(tzinfo=timezone.utc)


def _parse_date(date):
    return parse_date(date)


def is_dict_subset(subset: dict, superset: dict) -> bool:
    if isinstance(subset, dict):
        return all(
            key in superset and is_dict_subset(val, superset[key])
            for key, val in subset.items()
        )

    if isinstance(subset, list) or isinstance(subset, set):
        return all(
            any(is_dict_subset(subitem, superitem) for superitem in superset)
            for subitem in subset
        )

    return subset == superset


def uuid4_generator():
    """
    A generator that will yield a new uuid4 each time it is called. This is used to
    patch the uuid4 function so that we can predict the uuids that will be generated
    in tests.
    """

    base_uuid = uuid.UUID("00000000-0000-4000-8000-000000000000")
    counter = 0

    def mocked_uuid4():
        nonlocal counter
        counter += 1
        return uuid.UUID(int=base_uuid.int + counter)

    return mocked_uuid4


def setup_interesting_test_table(
    data_fixture,
    user: Optional[AbstractUser] = None,
    database: Optional[Database] = None,
    name: Optional[str] = None,
    file_suffix: Optional[str] = None,
    user_kwargs: Optional[Dict[str, Any]] = None,
):
    """
    Constructs a testing table with every field type, their sub types and any other
    interesting baserow edge cases worth testing when writing a comprehensive "does this
    feature work with all the baserow fields" test.

    :param data_fixture: The baserow testing data_fixture object
    :return:
    """

    if user_kwargs is None:
        user_kwargs = {}

    if user is None:
        user = data_fixture.create_user(**user_kwargs)

    if database is None:
        database = data_fixture.create_database_application(user=user)

    data_fixture.register_fake_generate_ai_type()

    file_suffix = file_suffix or ""

    try:
        user2, user3 = User.objects.filter(
            email__in=["user2@example.com", "user3@example.com"]
        ).order_by("id")
    except ValueError:
        user2 = data_fixture.create_user(
            workspace=database.workspace, first_name="User2", email="user2@example.com"
        )
        user3 = data_fixture.create_user(
            workspace=database.workspace, first_name="User3", email="user3@example.com"
        )

    linked_tables = {}
    table = data_fixture.create_database_table(
        database=database, user=user, name=name or "interesting_test_table"
    )
    linked_tables["link_table"] = link_table = data_fixture.create_database_table(
        database=database, user=user, name="link_table"
    )
    link_table_primary_text_field = data_fixture.create_text_field(
        table=link_table, name="text_field", primary=True
    )
    link_table_duration_field = data_fixture.create_duration_field(
        table=link_table, name="duration_field"
    )
    linked_tables[
        "decimal_link_table"
    ] = decimal_link_table = data_fixture.create_database_table(
        database=database, user=user, name="decimal_link_table"
    )
    linked_tables[
        "file_link_table"
    ] = file_link_table = data_fixture.create_database_table(
        database=database, user=user, name="file_link_table"
    )
    linked_tables[
        "multiple_collaborators_link_table"
    ] = multiple_collaborators_link_table = data_fixture.create_database_table(
        database=database, user=user, name="multiple_collaborators_link_table"
    )
    all_possible_kwargs_per_type = construct_all_possible_field_kwargs(
        table,
        link_table,
        decimal_link_table,
        file_link_table,
        multiple_collaborators_link_table,
    )
    name_to_field_id = {}
    i = 0
    decimal_table_primary_decimal_field = data_fixture.create_number_field(
        table=decimal_link_table,
        name="decimal_field",
        primary=True,
        number_decimal_places=3,
        number_negative=True,
    )
    file_link_table_primary_file_field = data_fixture.create_file_field(
        table=file_link_table,
        name="file_field",
        primary=True,
    )
    multiple_collaborators_table_primary_field = (
        data_fixture.create_multiple_collaborators_field(
            table=multiple_collaborators_link_table,
            name="multiple_collaborators",
            primary=True,
        )
    )
    handler = FieldHandler()
    fields = {}
    for field_type_name, all_possible_kwargs in all_possible_kwargs_per_type.items():
        for kwargs in all_possible_kwargs:
            field = handler.create_field(
                user=user,
                table=table,
                type_name=field_type_name,
                order=i,
                **kwargs,
            )
            i += 1
            name_to_field_id[kwargs["name"]] = field.id
            fields[field.id] = field
    row_handler = RowHandler()

    datetime = _parse_datetime("2020-02-01 01:23")
    date = _parse_date("2020-02-01")
    option_c, option_d, option_e = (
        SelectOption.objects.filter(field_id=name_to_field_id["multiple_select"])
        .order_by("id")
        .values_list("id", flat=True)
    )
    values = {
        "text": "text",
        "long_text": "long_text",
        "url": "https://www.google.com",
        "email": "test@example.com",
        "negative_int": -1,
        "positive_int": 1,
        "negative_decimal": Decimal("-1.2"),
        "positive_decimal": Decimal("1.2"),
        "decimal_with_default": None,
        "rating": 3,
        "boolean": "True",
        "boolean_with_default": None,
        "datetime_us": datetime,
        "date_us": date,
        "datetime_eu": datetime,
        "date_eu": date,
        "datetime_eu_tzone_visible": datetime,
        "datetime_eu_tzone_hidden": datetime,
        "last_modified_datetime_us": None,
        "last_modified_date_us": None,
        "last_modified_datetime_eu": None,
        "last_modified_date_eu": None,
        "last_modified_datetime_eu_tzone": None,
        "created_on_datetime_us": None,
        "created_on_date_us": None,
        "created_on_datetime_eu": None,
        "created_on_date_eu": None,
        "created_on_datetime_eu_tzone": None,
        "last_modified_by": None,
        "created_by": None,
        "duration_hm": timedelta(hours=1, minutes=1),
        "duration_hms": timedelta(hours=1, minutes=1, seconds=6),
        "duration_hms_s": timedelta(hours=1, minutes=1, seconds=6.6),
        "duration_hms_ss": timedelta(hours=1, minutes=1, seconds=6.66),
        "duration_hms_sss": timedelta(hours=1, minutes=1, seconds=6.666),
        "duration_dh": timedelta(days=1, hours=1),
        "duration_dhm": timedelta(days=1, hours=1, minutes=1),
        "duration_dhms": timedelta(days=1, hours=1, minutes=1, seconds=6),
        # We will setup link rows manually later
        "link_row": None,
        "self_link_row": None,
        "link_row_without_related": None,
        "decimal_link_row": None,
        "file_link_row": None,
        "multiple_collaborators_link_row": None,
        "file": [
            {
                "name": f"hashed{file_suffix}_name.txt",
                "visible_name": "a.txt",
                "is_image": False,
                "size": 0,
                "mime_type": "text/plain",
                "image_width": None,
                "image_height": None,
                "uploaded_at": "2020-02-01 01:23",
            },
            {
                "name": f"other{file_suffix}_name.txt",
                "visible_name": "b.txt",
                "is_image": False,
                "size": 0,
                "mime_type": "text/plain",
                "image_width": None,
                "image_height": None,
                "uploaded_at": "2020-02-01 01:23",
            },
        ],
        "single_select": SelectOption.objects.get(
            value="A", field_id=name_to_field_id["single_select"]
        ).id,
        "single_select_with_default": None,
        "multiple_select": [option_d, option_c, option_e],
        "multiple_collaborators": [
            {"id": user2.id, "name": user2.first_name},
            {"id": user3.id, "name": user3.first_name},
        ],
        "phone_number": "+4412345678",
        "password": "test",
        "ai": "I'm an AI.",
        "ai_choice": SelectOption.objects.get(
            value="Object", field_id=name_to_field_id["ai_choice"]
        ).id,
    }

    with freeze_time("2020-02-01 01:23"):
        data_fixture.create_user_file(
            original_name=f"a.txt",
            unique=f"hashed{file_suffix}",
            sha256_hash="name",
        )
        data_fixture.create_user_file(
            original_name=f"b.txt",
            unique=f"other{file_suffix}",
            sha256_hash="name",
        )

    missing_fields = (
        set(name_to_field_id.keys())
        - set(values.keys())
        - set([f["name"] for f in all_possible_kwargs_per_type["formula"]])
        - {
            "lookup",
            "count",
            "rollup",
            "uuid",
            "autonumber",
            "duration_rollup_avg",
            "duration_rollup_sum",
            "multiple_collaborators_lookup",
            "multiple_select_with_default",
        }
    )
    assert missing_fields == set(), (
        "Please update the dictionary above with interesting test values for your new "
        f"field type. In the values dict you are missing the fields {missing_fields}."
    )
    row_values = {}
    for field_type, val in values.items():
        if val is not None:
            row_values[f"field_{name_to_field_id[field_type]}"] = val
    # Make a blank row to test empty field conversion also.

    # We freeze time here so that we know what the values of the last_modified and
    # created_on field types are going to be. Freezing the datetime will also freeze
    # the current daylight savings time information.
    with freeze_time("2021-01-02 12:00"):
        model = table.get_model()

        uuid_field = getattr(model, f"field_{name_to_field_id['uuid']}")
        uuid_field.field.default = uuid4_generator()

        blank_row, row = row_handler.force_create_rows(
            user, table, [{}, row_values], model=model
        ).created_rows

    # Setup the link rows
    linked_row_1, linked_row_2, linked_row_3 = row_handler.force_create_rows(
        user=user,
        table=link_table,
        rows_values=[
            {
                link_table_primary_text_field.db_column: "linked_row_1",
                link_table_duration_field.db_column: timedelta(minutes=1),
            },
            {
                link_table_primary_text_field.db_column: "linked_row_2",
                link_table_duration_field.db_column: timedelta(minutes=3),
            },
            {
                link_table_primary_text_field.db_column: "",
            },
        ],
    ).created_rows
    linked_row_4, linked_row_5, linked_row_6 = row_handler.force_create_rows(
        user=user,
        table=decimal_link_table,
        rows_values=[
            {
                decimal_table_primary_decimal_field.db_column: "1.234",
            },
            {
                decimal_table_primary_decimal_field.db_column: "-123.456",
            },
            {
                decimal_table_primary_decimal_field.db_column: None,
            },
        ],
    ).created_rows
    with freeze_time("2020-01-01 12:00"):
        user_file_1 = data_fixture.create_user_file(
            original_name=f"name{file_suffix}.txt",
            unique=f"test{file_suffix}",
            sha256_hash=f"hash{file_suffix}",
        )
    linked_row_7, linked_row_8 = row_handler.force_create_rows(
        user=user,
        table=file_link_table,
        rows_values=[
            {
                file_link_table_primary_file_field.db_column: [
                    {"name": user_file_1.name}
                ],
            },
            {
                file_link_table_primary_file_field.db_column: None,
            },
        ],
    ).created_rows
    link_row_9, link_row_10 = row_handler.force_create_rows(
        user=user,
        table=multiple_collaborators_link_table,
        rows_values=[
            {
                multiple_collaborators_table_primary_field.db_column: [
                    {"id": user2.id, "name": user2.first_name},
                    {"id": user3.id, "name": user3.first_name},
                ],
            },
            {
                multiple_collaborators_table_primary_field.db_column: [
                    {"id": user2.id, "name": user2.first_name},
                ],
            },
        ],
    ).created_rows

    link_row_field_id = name_to_field_id["link_row"]
    link_row_field_without_related_id = name_to_field_id["link_row_without_related"]
    self_link_row_field_id = name_to_field_id["self_link_row"]
    decimal_row_field_id = name_to_field_id["decimal_link_row"]
    file_link_row_id = name_to_field_id["file_link_row"]
    multiple_collaborator_row_id = name_to_field_id["multiple_collaborators_link_row"]
    with freeze_time("2021-01-02 12:00"):
        handler = RowHandler()
        row = handler.update_row_by_id(
            user,
            table,
            row.id,
            {
                f"field_{link_row_field_id}": [
                    linked_row_1.id,
                    linked_row_2.id,
                    linked_row_3.id,
                ],
                f"field_{self_link_row_field_id}": [blank_row.id],
                f"field_{link_row_field_without_related_id}": [
                    linked_row_1.id,
                    linked_row_2.id,
                ],
                f"field_{decimal_row_field_id}": [
                    linked_row_4.id,
                    linked_row_5.id,
                    linked_row_6.id,
                ],
                f"field_{file_link_row_id}": [linked_row_7.id, linked_row_8.id],
                f"field_{multiple_collaborator_row_id}": [
                    link_row_9.id,
                    link_row_10.id,
                ],
            },
        )

    context = {
        "user2": user2,
        "user3": user3,
        "fields": fields,
        "tables": linked_tables,
        "name_to_field_id": name_to_field_id,
    }

    return table, user, row, blank_row, context


def setup_interesting_test_database(
    data_fixture,
    user: Optional[AbstractUser] = None,
    workspace: Optional[Workspace] = None,
    database: Optional[Database] = None,
    name: Optional[str] = None,
    user_kwargs=None,
):
    if user_kwargs is None:
        user_kwargs = {}

    if user is None:
        user = data_fixture.create_user(**user_kwargs)

    if database is None:
        database = data_fixture.create_database_application(
            user=user, workspace=workspace, name=name
        )

    for table_name in ["A", "B", "C"]:
        setup_interesting_test_table(
            data_fixture,
            user=user,
            database=database,
            name=table_name,
            file_suffix=table_name,
        )

    return database


@contextmanager
def defer_signals(dotted_names: List[str]):
    """Temporarily no-op a list of callable paths during test setup.

    Pass fully qualified dotted names of callables (e.g. Celery task .delay
    methods or websocket broadcasters). While inside the context these
    callables are patched to no-op to avoid a storm of side-effects while
    bulk-creating data. After exiting, perform any needed one-shot processing
    (e.g. initialize/process search data once per table).

    Example:
        with defer_signals([
            "baserow.ws.tasks.broadcast_to_channel_group.delay",
            "baserow.contrib.database.search.tasks.schedule_update_search_data.delay",
            "baserow.contrib.database.search.tasks.update_search_data.delay",
        ]):
            # create lots of data without triggering tasks/broadcasts
            ...
    """

    with ExitStack() as stack:
        for name in dotted_names:
            stack.enter_context(patch(name, lambda *args, **kwargs: None))
        yield


@contextmanager
def register_instance_temporarily(registry, instance):
    """
    A context manager to allow tests to register a new instance into a Baserow
    registry which will then unregister the instance afterwards to ensure the global
    registries are kept clean between tests.
    """

    registry.register(instance)
    try:
        yield instance
    finally:
        registry.unregister(instance)


def assert_undo_redo_actions_are_valid(
    actions: List[Action], expected_action_types: List[Type[ActionType]]
):
    assert len(actions) == len(
        expected_action_types
    ), f"Expected {len(actions)} actions but got {len(expected_action_types)} action_types"

    for action, expected_action_type in zip(actions, expected_action_types):
        assert (
            action.type == expected_action_type.type
        ), f"Action expected of type {expected_action_type} but got {action}"
        assert (
            action is not None
        ), f"Action is None, but should be of type {expected_action_type}"
        assert action.error is None, f"Action has error: {action.error}"


def assert_undo_redo_actions_fails_with_error(
    actions: List[Action], expected_action_types: List[Type[ActionType]]
):
    assert actions, "Actions list should not be empty"

    for action, expected_action_type in zip(actions, expected_action_types):
        assert action, f"Action is None, but should be of type {expected_action_type}"
        assert action.error is not None, "Action has no error, but should have one"


@contextmanager
def independent_test_db_connection():
    d = connection.settings_dict
    conn = psycopg.connect(
        host=d["HOST"],
        dbname=d["NAME"],
        user=d["USER"],
        password=d["PASSWORD"],
        port=d["PORT"],
    )
    conn.autocommit = False
    yield conn
    conn.close()


def assert_serialized_field_values_are_the_same(
    value_1, value_2, ordered=False, field_name=None
):
    if isinstance(value_1, list) and not ordered:
        assert unordered(value_1, value_2)
    else:
        assert value_1 == value_2, f"{field_name or 'error'}: {value_1} != {value_2}"


def extract_serialized_field_value(field_value):
    if not field_value:
        return field_value

    def extract_value(value):
        if isinstance(value, dict):
            if "name" in value:
                return value["name"]
            if "url" in value:
                return (value.get("label") or "") + " (" + value["url"] + ")"
            return value["value"]
        return value

    if isinstance(field_value, list):
        return [extract_value(value) for value in field_value]

    return extract_value(field_value)


def assert_serialized_rows_contain_same_values(row_1, row_2):
    for field_name, row_field_value in row_1.items():
        row_1_value = extract_serialized_field_value(row_field_value)
        row_2_value = extract_serialized_field_value(row_2[field_name])
        assert_serialized_field_values_are_the_same(
            row_1_value, row_2_value, field_name=field_name
        )


# The httpretty stub implementation of socket.getaddrinfo is incorrect and doesn't
# return an IP causing advocate to fail, instead we patch to fix this.
def stub_getaddrinfo(host, port, family=None, socktype=None, proto=None, flags=None):
    try:
        ip_network(host)
        ip = host
    except ValueError:
        ip = "1.1.1.1"
    return [
        (AF_INET, SOCK_STREAM, IPPROTO_TCP, host, (ip, port)),
        (AF_INET6, SOCK_STREAM, IPPROTO_TCP, "", (ip, port)),
    ]


class AnyInt(int):
    """
    A class that can be used to check if a value is an int. Useful in tests when
    you don't care about ID, but you want to check all other values.
    """

    def __eq__(self, other):
        return isinstance(other, int)


class AnyFloat(float):
    """A class that can be used to check if a value is a float."""

    def __eq__(self, other):
        return isinstance(other, float)


class AnyBool:
    """A class that can be used to check if a value is a boolean."""

    def __eq__(self, other):
        return isinstance(other, bool)


class AnyStr(str):
    """
    A class that can be used to check if a value is an str. Useful in tests when
    you don't care about a string, but you want to check all other values.
    """

    def __eq__(self, other):
        return isinstance(other, str)


class AnyDict(dict):
    """
    A class that can be used to check if a value is a dict. Useful in tests when
    you don't care about the contents.
    """

    def __eq__(self, other):
        return isinstance(other, dict)


class AnyList(dict):
    """
    A class that can be used to check if a value is a list. Useful in tests when
    you don't care about the contents.
    """

    def __eq__(self, other):
        return isinstance(other, list)


def load_test_cases(name: str) -> Union[List, Dict]:
    """
    Load test data from the global cases directory. These cases are used to run the
    same tests with the same data in both frontend and backend.
    :param name:
    :return:
    """

    current_file_path = os.path.abspath(__file__)
    current_directory = os.path.dirname(current_file_path)
    cases_path = os.path.join(current_directory, "../../../../tests/cases/")
    file_path = os.path.join(cases_path, f"{name}.json")

    with open(file_path, "r") as file:
        return json.load(file)


def counter_int(init: int = 0) -> Generator[int, None, None]:
    current = init
    while True:
        yield current
        current += 1


class ReplayValues:
    """
    Helper class to test replayability of values. When we do a copy of a structure,
    some fields may keep identifiers that should be unique per structure. When a copy
    is being created, those identifiers are replaced with other values.

    In such case we can't compare values directly, but we know that there's a certain
    patter of values. This class helps to match the pattern.

    >>> r = ReplayValues()
    >>> r.record(None)
    >>> r.record(1)
    >>> r.record('B')
    >>> r.record('C')
    >>> r.record('A')
    >>> r.record('A')
    >>> r.record('B')
    >>> assert r.stored == [0,1,2,3,1,1,2]
    >>> r.reset()
    >>> assert r.stored == []
    """

    def __init__(self):
        self.reset()

    def record(self, value: Any) -> Any:
        """
        Record a specific value. If a value wasn't recorded previously a new
        placeholder value is generated. If a value has been recorded, existing value
        is reused.

        :param value:
        :return: value
        """

        try:
            prev_idx = self.recorded.index(value)
            stored = self.stored[prev_idx]
        except ValueError:
            stored = next(self.i)
        self.stored.append(stored)
        self.recorded.append(value)
        return value

    def reset(self):
        """
        Resets the state.
        :return:
        """

        self.stored = []
        self.recorded = []
        self.i = iter(counter_int())
