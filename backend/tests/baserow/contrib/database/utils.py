import asyncio
import dataclasses
from dataclasses import dataclass
from typing import Callable, Iterable

from django.contrib.auth.models import AbstractUser
from django.db import OperationalError
from django.db.models import QuerySet

from channels.testing import WebsocketCommunicator

from baserow.contrib.database.field_rules.exceptions import FieldRuleAlreadyExistsError
from baserow.contrib.database.field_rules.models import FieldRule
from baserow.contrib.database.field_rules.registries import (
    FieldRuleType,
    FieldRuleValidity,
    RowRuleValidity,
)
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
from baserow.core.psycopg import errors
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
    extra: dict


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


def uuid_field_factory(data_fixture, table, user, **kwargs):
    return data_fixture.create_uuid_field(
        name="target", user=user, table=table, **kwargs
    )


def autonumber_field_factory(data_fixture, table, user, **kwargs):
    return data_fixture.create_autonumber_field(
        name="target", user=user, table=table, **kwargs
    )


def single_select_field_factory(data_fixture, table, user):
    field = data_fixture.create_single_select_field(
        name="target", user=user, table=table
    )
    data_fixture.create_select_option(field=field, value="1")
    data_fixture.create_select_option(field=field, value="2")
    return field


def single_select_field_value_factory(data_fixture, target_field, value=None):
    return (
        data_fixture.create_select_option(field=target_field, value=value)
        if value
        else None
    )


def multiple_select_field_factory(data_fixture, table, user):
    field = data_fixture.create_multiple_select_field(
        name="target", user=user, table=table
    )
    data_fixture.create_select_option(field=field, value="1")
    data_fixture.create_select_option(field=field, value="2")
    return field


def multiple_select_field_value_factory(data_fixture, target_field, value=None):
    if value is None:
        return []
    option = data_fixture.create_select_option(field=target_field, value=value)
    return [option.id]


def multiple_collaborators_field_factory(data_fixture, table, user):
    data_fixture.create_user(workspace=table.database.workspace)
    data_fixture.create_user(workspace=table.database.workspace)
    return data_fixture.create_multiple_collaborators_field(
        name="target", user=user, table=table
    )


def file_field_factory(data_fixture, table, user):
    data_fixture.create_user_file(
        original_name=f"a.txt",
        sha256_hash="a",
        uploaded_by=user,
    )
    data_fixture.create_user_file(
        original_name=f"b.txt",
        sha256_hash="b",
        uploaded_by=user,
    )
    return data_fixture.create_file_field(name="target", user=user, table=table)


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


def date_field_factory(data_fixture, table, user):
    return data_fixture.create_date_field(name="target", user=user, table=table)


def datetime_field_factory(data_fixture, table, user):
    return data_fixture.create_date_field(
        name="target", user=user, table=table, date_include_time=True
    )


def setup_linked_table_and_lookup(
    data_fixture,
    target_field_factory,
    helper_fields_other_table: Iterable[Callable] = frozenset(),
    helper_fields_table: Iterable[Callable] = frozenset(),
) -> LookupFieldSetup:
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    table = data_fixture.create_database_table(user=user, database=database)
    other_table = data_fixture.create_database_table(user=user, database=database)
    target_field = target_field_factory(data_fixture, other_table, user)
    for helper_field_factory in helper_fields_other_table:
        helper_field_factory(data_fixture, table=other_table, user=user)
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
    for helper_field_factory in helper_fields_table:
        helper_field_factory(data_fixture, table=table, user=user)
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
        extra={},
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


def get_deadlock_error(message: str = "Deadlock detected"):
    error = OperationalError(message)
    error.__cause__ = errors.DeadlockDetected()
    return error


class DummyFieldRuleType(FieldRuleType):
    type = "dummy"
    model_class = FieldRule

    def validate_row(
        self, row: GeneratedTableModel, rule: FieldRule
    ) -> RowRuleValidity:
        return RowRuleValidity(row_id=row.id, rule_id=rule.id, is_valid=True)

    def validate_rows(
        self, table: Table, rule: FieldRule, queryset: QuerySet | None = None
    ):
        return

    def validate_rule(self, rule: FieldRule) -> FieldRuleValidity:
        return FieldRuleValidity(
            table_id=rule.table_id,
            rule_id=rule.id,
            # one can inject rule validity by setting rule.set_is_valid
            is_valid=getattr(rule, "set_is_valid", True),
            error_text="",
        )


class DummyUniqueFieldRuleType(DummyFieldRuleType):
    type = "dummy_uniq"

    def before_rule_created(self, table: Table, in_data: dict):
        if table.field_rules.all().exists():
            raise FieldRuleAlreadyExistsError()
