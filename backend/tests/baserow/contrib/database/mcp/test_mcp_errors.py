"""
Database tool input mistakes reach the client as readable error results and are not
logged as errors.
"""

import json
import logging

from django.db import transaction

import pytest
from asgiref.sync import async_to_sync
from loguru import logger as loguru_logger
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.constants import LEGACY_DEFAULT_TOOLS


@pytest.fixture
def error_records():
    records = []
    handler_id = loguru_logger.add(
        lambda m: records.append(m.record), level="ERROR", format="{message}"
    )
    yield records
    loguru_logger.remove(handler_id)


def _call(endpoint, name, arguments):
    async def inner():
        server = BaserowMCPServer()
        token = current_key.set(endpoint.key)
        try:
            async with client_session(server._mcp_server) as client:
                return await client.call_tool(name, arguments)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


def _assert_readable_error(result, caplog, error_records, *expected):
    text = result.content[0].text
    assert result.isError is True
    assert "Internal error" not in text
    assert "Not found" not in text
    for part in expected:
        assert part.lower() in text.lower(), text
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert error_records == []


def _assert_field_error(result, caplog, error_records, expected):
    # create_fields reports a field it could not create and goes on with the rest.
    assert result.isError is False
    (error,) = json.loads(result.content[0].text)["errors"]
    assert expected in error["message"].lower(), error
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert error_records == []


@pytest.fixture
def table_setup(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    endpoint = data_fixture.create_mcp_endpoint(
        user=user,
        workspace=workspace,
        allowed_tools=[*LEGACY_DEFAULT_TOOLS, "create_fields"],
    )
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    return data_fixture, endpoint, table


@pytest.mark.django_db
def test_invalid_single_select_value(table_setup, caplog, error_records):
    data_fixture, endpoint, table = table_setup
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=field, value="Open")

    result = _call(
        endpoint,
        "create_rows",
        {"table_id": table.id, "rows": [{"Status": "NoSuchOption"}]},
    )

    _assert_readable_error(result, caplog, error_records, "NoSuchOption")


@pytest.mark.django_db
def test_unknown_field_type(table_setup, caplog, error_records):
    data_fixture, endpoint, table = table_setup

    result = _call(
        endpoint,
        "create_fields",
        {"table_id": table.id, "fields": [{"name": "X", "type": "nonsense"}]},
    )

    _assert_readable_error(result, caplog, error_records, "fields.0.type")


@pytest.mark.django_db
def test_duplicate_field_name(table_setup, caplog, error_records):
    data_fixture, endpoint, table = table_setup
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    result = _call(
        endpoint,
        "create_fields",
        {"table_id": table.id, "fields": [{"name": "Name", "type": "text"}]},
    )

    _assert_field_error(result, caplog, error_records, "same name")


@pytest.mark.django_db
def test_reserved_field_name(table_setup, caplog, error_records):
    data_fixture, endpoint, table = table_setup

    result = _call(
        endpoint,
        "create_fields",
        {"table_id": table.id, "fields": [{"name": "id", "type": "text"}]},
    )

    _assert_field_error(result, caplog, error_records, "reserved")


@pytest.mark.django_db
def test_missing_row_names_the_ids(table_setup, caplog, error_records):
    data_fixture, endpoint, table = table_setup
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    result = _call(
        endpoint, "update_rows", {"table_id": table.id, "rows": [{"id": 9999}]}
    )

    _assert_readable_error(result, caplog, error_records, "9999")


def test_to_mcp_error_flattens_validation_errors():
    from django.core.exceptions import ValidationError as DjangoValidationError

    from rest_framework.exceptions import ValidationError as DRFValidationError

    from baserow.api.exceptions import RequestBodyValidationException
    from baserow.core.mcp.exceptions import to_mcp_error

    assert "Bad" in to_mcp_error(DjangoValidationError("Bad"))
    drf = to_mcp_error(DRFValidationError({"Status": ["Nope."]}))
    assert "Status: Nope." in drf
    body = to_mcp_error(
        RequestBodyValidationException({"items": [{"name": ["Required."]}]})
    )
    assert "items.0.name: Required." in body


@pytest.mark.django_db
def test_repeated_row_id(table_setup, caplog, error_records):
    data_fixture, endpoint, table = table_setup
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    row = table.get_model().objects.create()

    result = _call(
        endpoint,
        "update_rows",
        {"table_id": table.id, "rows": [{"id": row.id}, {"id": row.id}]},
    )

    _assert_readable_error(result, caplog, error_records, "not unique", str(row.id))


@pytest.mark.django_db
@pytest.mark.field_constraints
def test_duplicate_value_in_unique_field(table_setup, caplog, error_records):
    from baserow.contrib.database.fields.handler import FieldHandler

    data_fixture, endpoint, table = table_setup
    field = data_fixture.create_text_field(table=table, name="Name", primary=True)
    FieldHandler().update_field(
        endpoint.user,
        field,
        field_constraints=[{"type_name": "unique_with_empty"}],
    )

    result = _call(
        endpoint,
        "create_rows",
        {"table_id": table.id, "rows": [{"Name": "A"}, {"Name": "A"}]},
    )

    _assert_readable_error(result, caplog, error_records, "field constraint")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,arguments,expected",
    [
        ("create_rows", lambda row: {"rows": [{"Name": "A"}]}, "create a row"),
        ("delete_rows", lambda row: {"row_ids": [row.id]}, "delete a row"),
    ],
)
def test_data_synced_table(
    table_setup, caplog, error_records, tool, arguments, expected
):
    data_fixture, endpoint, table = table_setup
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    row = table.get_model().objects.create()
    data_fixture.create_ical_data_sync(table=table)

    result = _call(endpoint, tool, {"table_id": table.id, **arguments(row)})

    _assert_readable_error(result, caplog, error_records, "not possible", expected)


def test_input_errors_maps_subclasses():
    from baserow.contrib.database.fields.exceptions import FieldDataConstraintException
    from baserow.contrib.database.mcp.services import input_errors
    from baserow.core.mcp.exceptions import MCPToolInputError

    class UniqueValueTaken(FieldDataConstraintException):
        pass

    with pytest.raises(MCPToolInputError, match="field constraint"):
        with input_errors():
            raise UniqueValueTaken()


def test_to_mcp_error_reads_validate_data_errors():
    from baserow.api.exceptions import RequestBodyValidationException
    from baserow.core.mcp.exceptions import to_mcp_error

    body = to_mcp_error(
        RequestBodyValidationException(
            {"name": [{"error": "This field is required.", "code": "required"}]}
        )
    )

    assert body == "Invalid value. name: This field is required."


def test_to_mcp_error_hides_server_bugs():
    from django.contrib.auth.models import User

    from baserow.contrib.database.fields.registries import field_type_registry
    from baserow.core.exceptions import InstanceTypeDoesNotExist
    from baserow.core.mcp.exceptions import to_mcp_error

    with pytest.raises(InstanceTypeDoesNotExist) as by_model:
        field_type_registry.get_by_model(User)
    with pytest.raises(InstanceTypeDoesNotExist) as by_type:
        field_type_registry.get("nonsense")

    assert to_mcp_error(by_model.value) is None
    assert to_mcp_error(by_type.value) == "'nonsense' is not a valid type."
    assert to_mcp_error(User.profile.RelatedObjectDoesNotExist()) is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "make_field,value",
    [
        (lambda f, t: f.create_multiple_collaborators_field(table=t, name="V"), ["b"]),
        (lambda f, t: f.create_number_field(table=t, name="V"), "1e60"),
    ],
)
def test_invalid_row_value_names_the_field(
    table_setup, caplog, error_records, make_field, value
):
    data_fixture, endpoint, table = table_setup
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    make_field(data_fixture, table)

    result = _call(
        endpoint, "create_rows", {"table_id": table.id, "rows": [{"V": value}]}
    )

    _assert_readable_error(result, caplog, error_records, "Invalid value", "rows.0.V")


def test_input_errors_uses_the_rest_api_message():
    from baserow.contrib.database.fields.exceptions import MaxFieldNameLengthExceeded
    from baserow.contrib.database.mcp.services import input_errors
    from baserow.core.mcp.exceptions import MCPToolInputError

    with pytest.raises(MCPToolInputError, match="longer than 255 characters"):
        with input_errors():
            raise MaxFieldNameLengthExceeded(255)


def test_input_errors_names_the_fields_the_user_cannot_change():
    from types import SimpleNamespace

    from baserow.contrib.database.mcp.services import input_errors
    from baserow.contrib.database.rows.exceptions import FieldsNotWritable
    from baserow.core.exceptions import PermissionDenied
    from baserow.core.mcp.exceptions import MCPToolInputError

    exc = FieldsNotWritable(
        [SimpleNamespace(name="Secret"), SimpleNamespace(name="Pay")]
    )
    assert isinstance(exc, PermissionDenied)
    # REST keeps its message.
    assert "update the following fields: Secret, Pay" in str(exc)

    with pytest.raises(MCPToolInputError, match="change these fields: Secret, Pay."):
        with input_errors():
            raise exc
