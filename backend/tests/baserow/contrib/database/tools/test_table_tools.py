"""Tests for the table tools shared by MCP and Kuma."""

import json
from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction

import pytest
from asgiref.sync import async_to_sync
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.database.fields.actions import CreateFieldActionType
from baserow.contrib.database.fields.models import Field, FormulaField, LinkRowField
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools.fields import FieldItem, FieldItemCreate
from baserow.contrib.database.tools.tables import (
    TableItem,
    TableItemCreate,
    create_tables,
    table_schema_conflict,
)
from baserow.core.exceptions import PermissionException
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.mcp.registries import mcp_tool_registry
from baserow.core.tools import ToolContext
from baserow.core.tools.errors import ToolInputError


def _session(endpoint, callback):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await callback(client)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


def _call_create_tables(endpoint, arguments):
    async def callback(client):
        return await client.call_tool("create_tables", arguments)

    return _session(endpoint, callback)


@pytest.mark.django_db
def test_create_tables_over_mcp_creates_linked_tables_and_a_raw_formula(
    data_fixture,
):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["create_tables"])
    database = data_fixture.create_database_application(workspace=endpoint.workspace)

    result = _call_create_tables(
        endpoint,
        {
            "database_id": database.id,
            "tables": [
                {"name": "Customers", "primary_field_name": "Name", "fields": []},
                {
                    "name": "Orders",
                    "primary_field_name": "Order",
                    "fields": [
                        {
                            "name": "Customer",
                            "type": "link_row",
                            "linked_table": "Customers",
                        },
                        {
                            "name": "Label",
                            "type": "formula",
                            "formula": "concat('#', field('Order'))",
                        },
                    ],
                },
            ],
        },
    )

    assert result.isError is False
    data = json.loads(result.content[0].text)
    customers = database.table_set.get(name="Customers")
    orders = database.table_set.get(name="Orders")
    assert [t["id"] for t in data["created_tables"]] == [customers.id, orders.id]
    assert data["reused_tables"] == []
    assert data["notes"] == []
    assert "errors" not in data
    link = LinkRowField.objects.get(table=orders, name="Customer")
    assert link.link_row_table_id == customers.id
    # The reverse link field is created in the other table.
    assert LinkRowField.objects.filter(table=customers, link_row_table=orders).exists()
    label = FormulaField.objects.get(table=orders, name="Label")
    assert label.formula == "concat('#', field('Order'))"


@pytest.mark.django_db
def test_create_tables_over_mcp_reports_a_formula_description(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["create_tables"])
    database = data_fixture.create_database_application(workspace=endpoint.workspace)

    result = _call_create_tables(
        endpoint,
        {
            "database_id": database.id,
            "tables": [
                {
                    "name": "People",
                    "primary_field_name": "Name",
                    "fields": [
                        {"name": "Notes", "type": "text"},
                        {
                            "name": "Full name",
                            "type": "formula",
                            "formula": "$formula: first and last name",
                        },
                    ],
                }
            ],
        },
    )

    assert result.isError is False
    data = json.loads(result.content[0].text)
    people = database.table_set.get(name="People")
    assert [t["id"] for t in data["created_tables"]] == [people.id]
    assert data["errors"] == [
        {
            "item": "Full name",
            "code": "invalid_formula",
            "message": "'Full name' needs a formula, not a description. Write it "
            "in Baserow formula syntax.",
            "table_id": people.id,
            "field_name": "Full name",
            "formula": "$formula: first and last name",
        }
    ]
    assert list(people.field_set.order_by("id").values_list("name", flat=True)) == [
        "Name",
        "Notes",
    ]
    assert not Field.objects_and_trash.filter(table=people, name="Full name").exists()


@pytest.mark.django_db
def test_create_tables_over_mcp_lists_only_the_shared_arguments(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["create_tables"])

    async def callback(client):
        return await client.list_tools()

    listed = _session(endpoint, callback)

    tool = next(t for t in listed.tools if t.name == "create_tables")
    assert set(tool.inputSchema["properties"]) == {"database_id", "tables"}
    assert tool.annotations.readOnlyHint is False
    assert tool.annotations.destructiveHint is False
    for kuma_only in ("ask_user", "navigate", "get_tables_schema", "sample"):
        assert kuma_only not in tool.description


@pytest.mark.django_db
def test_create_tables_database_in_other_workspace_is_not_found(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["create_tables"])
    other = data_fixture.create_database_application(user=endpoint.user)

    result = _call_create_tables(
        endpoint,
        {
            "database_id": other.id,
            "tables": [{"name": "Orders", "primary_field_name": "Name", "fields": []}],
        },
    )

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."
    assert not other.table_set.exists()


@pytest.mark.django_db
def test_create_tables_rejects_an_empty_table_list(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["create_tables"])
    database = data_fixture.create_database_application(workspace=endpoint.workspace)

    result = _call_create_tables(endpoint, {"database_id": database.id, "tables": []})

    assert result.isError is True
    assert "tables" in result.content[0].text


@pytest.mark.django_db
def test_endpoint_without_allow_list_does_not_get_create_tables(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=None)

    assert mcp_tool_registry.get_allowed_tool(endpoint, "create_tables") is None


@pytest.mark.django_db
def test_shared_create_tables_rejects_conflicting_same_name_requests(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    with pytest.raises(ValidationError, match="Conflicting table definitions"):
        create_tables(
            ToolContext(user, workspace),
            database.id,
            [
                TableItemCreate(name="Orders", primary_field_name="Order", fields=[]),
                TableItemCreate(name="Orders", primary_field_name="Ref", fields=[]),
            ],
        )

    assert not Table.objects.filter(database=database).exists()


@pytest.mark.django_db
def test_shared_create_tables_reports_an_incomplete_reused_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    orders = data_fixture.create_database_table(database=database, name="Orders")
    data_fixture.create_text_field(table=orders, name="Order", primary=True)
    statuses = []

    result = create_tables(
        ToolContext(user, workspace, statuses.append),
        database.id,
        [
            TableItemCreate(
                name="Orders",
                primary_field_name="Order",
                fields=[FieldItemCreate(name="Notes", type="text")],
            ),
            TableItemCreate(name="Customers", primary_field_name="Name", fields=[]),
        ],
    )

    assert [t["name"] for t in result["created_tables"]] == ["Customers"]
    assert [t["id"] for t in result["reused_tables"]] == [orders.id]
    (conflict,) = result["incomplete_reused_tables"]
    assert [f["name"] for f in conflict["missing_fields"]] == ["Notes"]
    assert "create_fields" in result["next_steps"]
    assert "ask_user" not in result["next_steps"]
    assert statuses == ["Creating table Customers..."]
    assert list(orders.field_set.values_list("name", flat=True)) == ["Order"]


@pytest.mark.django_db
def test_shared_create_tables_keeps_tables_and_fields_when_a_field_fails(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    original = CreateFieldActionType.do

    def do(user, table, field_type, **kwargs):
        field = original(user, table, field_type, **kwargs)
        if kwargs["name"] == "Two":
            raise IntegrityError("duplicate key value")
        return field

    with patch.object(CreateFieldActionType, "do", side_effect=do):
        result = create_tables(
            ToolContext(user, workspace),
            database.id,
            [
                TableItemCreate(
                    name="Orders",
                    primary_field_name="Order",
                    fields=[
                        FieldItemCreate(name="One", type="text"),
                        FieldItemCreate(name="Two", type="text"),
                        FieldItemCreate(name="Three", type="text"),
                    ],
                ),
                TableItemCreate(name="Customers", primary_field_name="Name", fields=[]),
            ],
        )

    assert [t["name"] for t in result["created_tables"]] == ["Orders", "Customers"]
    orders = Table.objects.get(database=database, name="Orders")
    assert set(orders.field_set.values_list("name", flat=True)) == {
        "Order",
        "One",
        "Three",
    }
    assert [(error["item"], error["table_id"]) for error in result["errors"]] == [
        ("Two", orders.id)
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "primary_field_name,reason",
    [
        ("id", "reserved"),
        ("", "must not be blank"),
        ("   ", "must not be blank"),
        ("x" * 300, "longer than 255 characters"),
    ],
)
def test_create_tables_over_mcp_reports_a_refused_primary_field_name(
    data_fixture, primary_field_name, reason
):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=["create_tables"])
    database = data_fixture.create_database_application(workspace=endpoint.workspace)

    result = _call_create_tables(
        endpoint,
        {
            "database_id": database.id,
            "tables": [
                {"name": "Fine", "primary_field_name": "Name", "fields": []},
                {
                    "name": "Orders",
                    "primary_field_name": primary_field_name,
                    "fields": [],
                },
            ],
        },
    )

    assert result.isError is True
    text = result.content[0].text
    assert text.startswith(
        "Invalid value. The primary_field_name of table 'Orders' is refused: "
    )
    assert reason in text
    assert not Table.objects.filter(database=database).exists()


@pytest.mark.django_db
def test_shared_create_tables_drops_the_model_cached_before_a_denied_field(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    original = CreateFieldActionType.do

    def do(user, table, field_type, **kwargs):
        if kwargs["name"] == "Two":
            raise PermissionException()
        return original(user, table, field_type, **kwargs)

    with patch.object(CreateFieldActionType, "do", side_effect=do):
        result = create_tables(
            ToolContext(user, workspace),
            database.id,
            [
                TableItemCreate(
                    name="Orders",
                    primary_field_name="Order",
                    fields=[
                        # A formula field builds the table model while created.
                        FieldItemCreate(name="One", type="formula", formula="1"),
                        FieldItemCreate(name="Two", type="formula", formula="2"),
                    ],
                )
            ],
        )

    assert "Permission denied" in result["notes"][0]
    model = Table.objects.get(database=database, name="Orders").get_model()
    assert [f["field"].name for f in model._field_objects.values()] == ["Order"]


def _reused_table_with_a_lookup():
    return TableItem(
        id=1,
        name="Orders",
        primary_field=FieldItem(id=10, name="Order", type="text"),
        fields=[
            FieldItem(id=11, name="Link", type="link_row", linked_table=2),
            FieldItem(
                id=12,
                name="Titles",
                type="lookup",
                through_field=11,
                through_field_name="Link",
                target_field=20,
                target_field_name="Title",
            ),
        ],
    )


# None: a lookup that names no link goes through the table's only link field.
@pytest.mark.parametrize("through_field", ["Link", 11, None])
def test_reused_table_matches_a_lookup_named_by_its_link_field(through_field):
    requested = TableItemCreate(
        name="Orders",
        primary_field_name="Order",
        fields=[
            FieldItemCreate(
                name="Titles",
                type="lookup",
                through_field=through_field,
                target_field="Title",
            )
        ],
    )

    assert table_schema_conflict(requested, _reused_table_with_a_lookup()) is None


def test_reused_table_reports_a_lookup_through_another_link_field():
    requested = TableItemCreate(
        name="Orders",
        primary_field_name="Order",
        fields=[
            FieldItemCreate(
                name="Titles",
                type="lookup",
                through_field="Other",
                target_field="Title",
            )
        ],
    )

    conflict = table_schema_conflict(requested, _reused_table_with_a_lookup())

    (mismatch,) = conflict["field_mismatches"]
    assert mismatch["relation_issues"] == {
        "through_field": {"actual": "Link", "requested": "Other"}
    }


@pytest.mark.django_db
def test_shared_create_tables_matches_reused_field_names_ignoring_case_and_spaces(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    people = data_fixture.create_database_table(database=database, name="People")
    data_fixture.create_text_field(table=people, name="Name", primary=True)
    data_fixture.create_text_field(table=people, name="Email")

    result = create_tables(
        ToolContext(user, workspace),
        database.id,
        [
            TableItemCreate(
                name="People",
                primary_field_name="name",
                fields=[FieldItemCreate(name=" email ", type="text")],
            )
        ],
    )

    assert [t["id"] for t in result["reused_tables"]] == [people.id]
    assert "incomplete_reused_tables" not in result
    assert "next_steps" not in result


@pytest.mark.django_db
def test_shared_create_tables_looks_up_a_field_of_a_later_table(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    result = create_tables(
        ToolContext(user, workspace),
        database.id,
        [
            TableItemCreate(
                name="Orders",
                primary_field_name="Order",
                fields=[
                    FieldItemCreate(
                        name="Customer", type="link_row", linked_table="Customers"
                    ),
                    FieldItemCreate(
                        name="Customer email",
                        type="lookup",
                        through_field="Customer",
                        target_field="Email",
                    ),
                    FieldItemCreate(
                        name="Emails",
                        type="formula",
                        formula="join(field('Customer email'), ',')",
                    ),
                ],
            ),
            TableItemCreate(
                name="Customers",
                primary_field_name="Name",
                fields=[FieldItemCreate(name="Email", type="text")],
            ),
        ],
    )

    assert result["notes"] == []
    assert "errors" not in result
    orders = Table.objects.get(database=database, name="Orders")
    email = Field.objects.get(table__name="Customers", name="Email")
    lookup = orders.field_set.get(name="Customer email").specific
    assert lookup.target_field_id == email.id
    assert orders.field_set.filter(name="Emails").exists()


@pytest.mark.django_db
def test_shared_create_tables_keeps_a_field_named_like_the_primary_with_spaces(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    create_tables(
        ToolContext(user, workspace),
        database.id,
        [
            TableItemCreate(
                name="People",
                primary_field_name="Name",
                fields=[
                    FieldItemCreate(name="Name", type="text"),
                    FieldItemCreate(name=" Name ", type="text"),
                ],
            )
        ],
    )

    people = Table.objects.get(database=database, name="People")
    assert sorted(people.field_set.values_list("name", flat=True)) == [" Name ", "Name"]


def test_reused_table_reports_a_field_named_like_the_primary_with_spaces():
    requested = TableItemCreate(
        name="Orders",
        primary_field_name="Order",
        fields=[
            FieldItemCreate(name="Order", type="text"),
            FieldItemCreate(name=" Order ", type="text"),
        ],
    )
    actual = TableItem(
        id=1,
        name="Orders",
        primary_field=FieldItem(id=10, name="Order", type="text"),
        fields=[],
    )

    conflict = table_schema_conflict(requested, actual)

    assert [f["name"] for f in conflict["missing_fields"]] == [" Order "]


@pytest.mark.django_db
def test_shared_create_tables_rejects_a_name_several_tables_share(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    for _ in range(2):
        tags = data_fixture.create_database_table(database=database, name="Tags")
        data_fixture.create_text_field(table=tags, name="Name", primary=True)

    with pytest.raises(ToolInputError) as exc_info:
        create_tables(
            ToolContext(user, workspace),
            database.id,
            [
                TableItemCreate(name="Tags", primary_field_name="Name", fields=[]),
                TableItemCreate(name="Posts", primary_field_name="Title", fields=[]),
            ],
        )

    assert str(exc_info.value) == (
        "Several tables in this database are named 'Tags'. No tables were created."
    )
    assert "create_fields" in exc_info.value.hint
    assert not Table.objects.filter(database=database, name="Posts").exists()


@pytest.mark.django_db
def test_shared_create_tables_does_not_link_to_a_name_several_tables_share(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    for _ in range(2):
        tags = data_fixture.create_database_table(database=database, name="Tags")
        data_fixture.create_text_field(table=tags, name="Name", primary=True)

    result = create_tables(
        ToolContext(user, workspace),
        database.id,
        [
            TableItemCreate(
                name="Posts",
                primary_field_name="Title",
                fields=[
                    FieldItemCreate(name="Tags", type="link_row", linked_table="Tags")
                ],
            )
        ],
    )

    (error,) = result["errors"]
    assert "Several tables in this database are named 'Tags'" in error["message"]
    assert not LinkRowField.objects.filter(table__name="Posts").exists()


@pytest.mark.parametrize("through_field", ["link", " LINK "])
def test_reused_table_matches_a_lookup_link_name_ignoring_case_and_spaces(
    through_field,
):
    requested = TableItemCreate(
        name="Orders",
        primary_field_name="Order",
        fields=[
            FieldItemCreate(
                name="Titles",
                type="lookup",
                through_field=through_field,
                target_field="Title",
            )
        ],
    )

    assert table_schema_conflict(requested, _reused_table_with_a_lookup()) is None


def test_reused_table_prefers_the_link_field_with_the_exact_name():
    actual = _reused_table_with_a_lookup()
    actual.fields.append(FieldItem(id=13, name="link", type="link_row", linked_table=2))
    requested = TableItemCreate(
        name="Orders",
        primary_field_name="Order",
        fields=[
            FieldItemCreate(
                name="Titles", type="lookup", through_field="link", target_field="Title"
            )
        ],
    )

    conflict = table_schema_conflict(requested, actual)

    (mismatch,) = conflict["field_mismatches"]
    assert mismatch["relation_issues"] == {
        "through_field": {"actual": "Link", "requested": "link"}
    }


@pytest.mark.django_db
def test_shared_create_tables_skips_a_field_named_like_the_primary_in_another_case(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    result = create_tables(
        ToolContext(user, workspace),
        database.id,
        [
            TableItemCreate(
                name="People",
                primary_field_name="Name",
                fields=[FieldItemCreate(name="name", type="text")],
            )
        ],
    )

    assert result["notes"] == []
    people = Table.objects.get(database=database, name="People")
    assert list(people.field_set.values_list("name", flat=True)) == ["Name"]


def test_reused_table_skips_a_field_named_like_the_primary_in_another_case():
    requested = TableItemCreate(
        name="Orders",
        primary_field_name="Order",
        fields=[FieldItemCreate(name="ORDER", type="text")],
    )
    actual = TableItem(
        id=1,
        name="Orders",
        primary_field=FieldItem(id=10, name="Order", type="text"),
        fields=[],
    )

    assert table_schema_conflict(requested, actual) is None


@pytest.mark.django_db
def test_create_tables_explains_a_lookup_to_a_formula_of_a_later_table(
    data_fixture,
):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)

    result = create_tables(
        ToolContext(user=user, workspace=workspace),
        database.id,
        [
            TableItemCreate(
                name="Orders",
                primary_field_name="Order",
                fields=[
                    FieldItemCreate(
                        name="Customer", type="link_row", linked_table="Customers"
                    ),
                    FieldItemCreate(
                        name="Customer total",
                        type="lookup",
                        through_field="Customer",
                        target_field="Total",
                    ),
                ],
            ),
            TableItemCreate(
                name="Customers",
                primary_field_name="Name",
                fields=[
                    FieldItemCreate(name="Amount", type="number"),
                    FieldItemCreate(
                        name="Total", type="formula", formula="field('Amount') * 2"
                    ),
                ],
            ),
        ],
    )

    (error,) = result["errors"]
    assert error["item"] == "Customer total"
    assert "The provided target field does not exist" in error["message"]
    orders = Table.objects.get(database=database, name="Orders")
    assert not orders.field_set.filter(name="Customer total").exists()


@pytest.mark.django_db
def test_create_tables_reports_field_failures_as_item_errors(data_fixture):
    user = data_fixture.create_user()
    database = data_fixture.create_database_application(user=user)
    ctx = ToolContext(user=user, workspace=database.workspace)

    result = create_tables(
        ctx,
        database.id,
        [
            TableItemCreate(
                name="Projects",
                primary_field_name="Title",
                fields=[FieldItemCreate(name="Total", type="formula", formula="x(")],
            )
        ],
    )

    assert result["changed"] is True and "error" not in result
    assert [(e["item"], e["code"]) for e in result["errors"]] == [
        ("Total", "invalid_formula")
    ]
