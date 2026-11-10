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
    visible_table,
)
from baserow.contrib.database.table.models import Table
from baserow.core.models import Agent
from baserow.core.tools import ToolContext


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

    assert visible_table(accounts.ctx, accounts.table.id).name == "Accounts"
    assert database_name(accounts.ctx, accounts.database.id) == "Sales"
    assert named_fields(accounts.ctx, [accounts.secret.id, copy.id]) == {
        accounts.secret.id: ("Secret", "Accounts"),
        copy.id: ("Secret", copy.table.name),
    }
    assert row_names(
        accounts.ctx, accounts.table, [accounts.acme.id, accounts.unnamed.id]
    ) == {
        accounts.acme.id: "Acme",
        accounts.unnamed.id: f"unnamed row {accounts.unnamed.id}",
    }
    with pytest.raises(Table.DoesNotExist):
        visible_table(accounts.ctx, other.id)


@pytest.mark.django_db
def test_missing_hidden_and_trashed_fields_and_rows_are_left_out(
    accounts, data_fixture
):
    hidden = data_fixture.create_text_field(name="Elsewhere")
    trashed = data_fixture.create_text_field(table=accounts.table, trashed=True)
    accounts.table.get_model().objects.filter(id=accounts.unnamed.id).update(
        trashed=True
    )

    assert named_fields(accounts.ctx, [accounts.secret.id, hidden.id, trashed.id]) == {
        accounts.secret.id: ("Secret", "Accounts")
    }
    assert row_names(
        accounts.ctx, accounts.table, [accounts.acme.id, accounts.unnamed.id, 999999]
    ) == {accounts.acme.id: "Acme"}


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
def test_fields_and_rows_need_the_right_to_list_them(accounts):
    with patch(
        "baserow.contrib.agent.database_previews.permitted_tables", return_value=[]
    ):
        assert named_fields(accounts.ctx, [accounts.secret.id]) == {}
        assert table_field_names(accounts.ctx, accounts.table) == {}
        assert row_names(accounts.ctx, accounts.table, [accounts.acme.id]) == {}
