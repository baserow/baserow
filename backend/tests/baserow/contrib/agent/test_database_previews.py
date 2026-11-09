from types import SimpleNamespace
from unittest.mock import patch

import pytest

from baserow.contrib.agent.database_previews import (
    database_name,
    named_fields,
    readable_names,
    row_names,
    table_field_names,
    table_names,
    table_with_rows,
    visible_table,
)
from baserow.contrib.database.table.models import Table
from baserow.core.exceptions import PermissionDenied
from baserow.core.models import Agent
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolNotFoundError


@pytest.fixture
def accounts(data_fixture):
    """An Accounts table with a password field, and an Agent identity to act as."""

    database = data_fixture.create_database_application(name="Sales")
    table = data_fixture.create_database_table(database=database, name="Accounts")
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    secret = data_fixture.create_password_field(table=table, name="Secret")
    model = table.get_model()
    identity = Agent.objects.create(workspace=database.workspace, name="Ops")
    return SimpleNamespace(
        ctx=ToolContext(user=identity, workspace=database.workspace),
        database=database,
        table=table,
        secret=secret,
        acme=model.objects.create(**{f"field_{name.id}": "Acme"}),
        unnamed=model.objects.create(),
    )


@pytest.mark.django_db
def test_names_are_resolved_as_the_agent_identity(accounts, data_fixture):
    other = data_fixture.create_database_table(name="Elsewhere")
    copy = data_fixture.create_text_field(
        table=data_fixture.create_database_table(database=accounts.database),
        name="Secret",
    )
    table = table_with_rows(accounts.ctx, accounts.table.id)

    assert visible_table(accounts.ctx, accounts.table.id).name == "Accounts"
    assert database_name(accounts.ctx, accounts.database.id) == "Sales"
    assert named_fields(accounts.ctx, [accounts.secret.id, copy.id]) == {
        accounts.secret.id: ("Secret", "Accounts"),
        copy.id: ("Secret", copy.table.name),
    }
    assert row_names(table, [accounts.acme.id, accounts.unnamed.id]) == {
        accounts.acme.id: "Acme",
        accounts.unnamed.id: f"unnamed row {accounts.unnamed.id}",
    }
    with pytest.raises(Table.DoesNotExist):
        visible_table(accounts.ctx, other.id)


@pytest.mark.django_db
def test_missing_fields_and_rows_are_named_to_the_model(accounts, data_fixture):
    hidden = data_fixture.create_text_field(name="Elsewhere")

    with pytest.raises(ToolNotFoundError) as fields:
        named_fields(accounts.ctx, [accounts.secret.id, hidden.id])
    with pytest.raises(ToolNotFoundError) as rows:
        row_names(accounts.table, [accounts.acme.id, 999999])

    assert fields.value.hint == (
        f"Fields [{hidden.id}] were not found. Call get_table_schema for the "
        "current field IDs."
    )
    assert rows.value.hint == (
        f"Rows [999999] were not found in table {accounts.table.id}. Call "
        "list_table_rows for the current row IDs."
    )


@pytest.mark.django_db
def test_readable_fields_leave_out_write_only_and_trashed_ones(accounts, data_fixture):
    data_fixture.create_text_field(table=accounts.table, name="Old", trashed=True)

    assert readable_names(accounts.table) == {"Name"}


@pytest.mark.django_db
def test_table_and_field_names_are_listed(accounts, data_fixture):
    other = data_fixture.create_database_table(name="Elsewhere")

    assert table_names(accounts.ctx, [accounts.table.id, other.id]) == {
        accounts.table.id: "Accounts"
    }
    assert set(table_field_names(accounts.ctx, accounts.table).values()) == {
        "Name",
        "Secret",
    }


@pytest.mark.django_db
def test_trashed_rows_are_not_found(accounts):
    accounts.table.get_model().objects.filter(id=accounts.acme.id).update(trashed=True)

    with pytest.raises(ToolNotFoundError):
        row_names(accounts.table, [accounts.acme.id])


@pytest.mark.django_db
def test_rows_need_the_right_to_list_them(accounts):
    with patch(
        "baserow.core.handler.CoreHandler.check_permissions",
        side_effect=PermissionDenied(),
    ):
        with pytest.raises(PermissionDenied):
            table_with_rows(accounts.ctx, accounts.table.id)


@pytest.mark.django_db
def test_fields_need_the_right_to_list_them(accounts):
    with patch(
        "baserow.contrib.agent.database_previews.permitted_tables", return_value=[]
    ):
        with pytest.raises(ToolNotFoundError) as named:
            named_fields(accounts.ctx, [accounts.secret.id])
        assert table_field_names(accounts.ctx, accounts.table) == {}
