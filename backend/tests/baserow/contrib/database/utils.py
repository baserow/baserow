import asyncio
import dataclasses
from dataclasses import dataclass
from typing import Callable, Iterable

from django.contrib.auth.models import AbstractUser

from channels.testing import WebsocketCommunicator

from baserow.contrib.database.fields.models import (
    Field,
    FormulaField,
    LinkRowField,
    LookupField,
)
from baserow.contrib.database.rows.handler import RowHandler
from baserow.contrib.database.table.models import GeneratedTableModel, Table
from baserow.contrib.database.views.handler import ViewHandler
from baserow.contrib.database.views.models import GridView
from baserow.test_utils.fixtures import Fixtures


async def received_message(communicator: WebsocketCommunicator, message_type: str):
    """
    Can be called to check if a specific type of message has been sent
    to a communicator.

    :param communicator: The communicator receiving the message
    :param message_type: The type of message you are looking for
    :returns: If the message has been received
    """

    return await get_message(communicator, message_type) is not None


async def get_message(communicator: WebsocketCommunicator, message_type: str):
    """
    Can be called to find the next message of the specified type

    :param communicator: The communicator receiving the message
    :param message_type: The type of message you are looking for
    :return: The received message
    """

    while True:
        try:
            message = await communicator.receive_json_from()
            if message["type"] == message_type:
                return message
        except asyncio.exceptions.TimeoutError:  # No more messages
            return None


@dataclass
class LookupFieldSetup:
    user: AbstractUser
    table: Table
    other_table: Table
    model: GeneratedTableModel
    other_table_model: GeneratedTableModel
    grid_view: GridView
    link_row_field: LinkRowField
    lookup_field: LookupField
    target_field: Field
    row_handler: RowHandler
    view_handler: ViewHandler


@dataclasses.dataclass
class FormulaFieldSetup:
    user: AbstractUser
    table: Table
    formula_field: FormulaField
    model: GeneratedTableModel
    grid_view: GridView
    data_source_field: Field
    row_handler: RowHandler
    view_handler: ViewHandler
    formula: str
    formula_type: str
    extra_fields: dict[str, Field]


def boolean_field_factory(data_fixture, table, user):
    return data_fixture.create_boolean_field(name="target", user=user, table=table)


def text_field_factory(data_fixture, table, user, name: str | None = None):
    return data_fixture.create_text_field(name=name or "target", user=user, table=table)


def long_text_field_factory(data_fixture, table, user):
    return data_fixture.create_long_text_field(name="target", user=user, table=table)


def url_field_factory(data_fixture, table, user):
    return data_fixture.create_url_field(name="target", user=user, table=table)


def email_field_factory(data_fixture, table, user):
    return data_fixture.create_email_field(name="target", user=user, table=table)


def phone_number_field_factory(data_fixture, table, user):
    return data_fixture.create_phone_number_field(name="target", user=user, table=table)


def uuid_field_factory(data_fixture, table, user):
    return data_fixture.create_uuid_field(name="target", user=user, table=table)


def single_select_field_factory(data_fixture, table, user):
    return data_fixture.create_single_select_field(
        name="target", user=user, table=table
    )


def single_select_field_value_factory(data_fixture, target_field, value=None):
    return (
        data_fixture.create_select_option(field=target_field, value=value)
        if value
        else None
    )


def duration_field_factory(
    data_fixture, table, user, duration_format: str = "d h mm", name: str | None = None
):
    return data_fixture.create_duration_field(
        name=name or "target", user=user, table=table, duration_format=duration_format
    )


def number_field_factory(data_fixture: Fixtures, table, user, **kwargs):
    return data_fixture.create_number_field(
        name="target", table=table, user=user, **kwargs
    )


def text_field_value_factory(data_fixture, target_field, value=None):
    return value or ""


def setup_linked_table_and_lookup(
    data_fixture, target_field_factory
) -> LookupFieldSetup:
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    other_table = data_fixture.create_database_table(user=user, database=database)
    target_field = target_field_factory(data_fixture, other_table, user)
    link_row_field = data_fixture.create_link_row_field(
        name="link", table=table, link_row_table=other_table
    )
    lookup_field = data_fixture.create_lookup_field(
        table=table,
        through_field=link_row_field,
        target_field=target_field,
        through_field_name=link_row_field.name,
        target_field_name=target_field.name,
        setup_dependencies=False,
    )
    grid_view = data_fixture.create_grid_view(table=table)
    view_handler = ViewHandler()
    row_handler = RowHandler()
    model = table.get_model()
    other_table_model = other_table.get_model()
    return LookupFieldSetup(
        user=user,
        table=table,
        other_table=other_table,
        other_table_model=other_table_model,
        target_field=target_field,
        row_handler=row_handler,
        grid_view=grid_view,
        link_row_field=link_row_field,
        lookup_field=lookup_field,
        view_handler=view_handler,
        model=model,
    )


def setup_formula_field(
    data_fixture,
    formula_text: str,
    formula_type: str,
    data_field_factory,
    extra_fields: Iterable[Callable],
    formula_extra_kwargs: dict | None = None,
) -> FormulaFieldSetup:
    """
    Create a table with duration formula field.

    :param data_fixture:
    :param formula_text:
    :param formula_type:
    :param data_field_factory:
    :param extra_fields: iterable with field factory functions.
    :param formula_extra_kwargs: optional dict with additional keyword args for
        formula field creation
    :return:
    """

    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    data_source_field = data_field_factory(data_fixture, table, user)

    formula_field = data_fixture.create_formula_field(
        table=table,
        user=user,
        formula=formula_text,
        formula_type=formula_type,
        **{k: v for k, v in (formula_extra_kwargs or {}).items()},
    )

    extra_fields_map = {}
    for field_factory in extra_fields:
        extra_field = field_factory(data_fixture, table=table, user=user)
        extra_fields_map[extra_field.name] = extra_field

    grid_view = data_fixture.create_grid_view(table=table)
    view_handler = ViewHandler()
    row_handler = RowHandler()
    model = table.get_model()

    return FormulaFieldSetup(
        user=user,
        table=table,
        data_source_field=data_source_field,
        formula_field=formula_field,
        row_handler=row_handler,
        grid_view=grid_view,
        view_handler=view_handler,
        model=model,
        formula=formula_text,
        formula_type=formula_type,
        extra_fields=extra_fields_map,
    )
