"""Tests for the field tools shared by MCP and Kuma."""

import json
from unittest.mock import patch

from django.db import DatabaseError, IntegrityError, connection, transaction
from django.test.utils import CaptureQueriesContext

import pytest
from asgiref.sync import async_to_sync
from loguru import logger as loguru_logger
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.database.fields.actions import (
    CreateFieldActionType,
    DeleteFieldActionType,
    UpdateFieldActionType,
)
from baserow.contrib.database.fields.models import Field
from baserow.contrib.database.table.models import Table
from baserow.contrib.database.tools import fields as fields_module
from baserow.contrib.database.tools.fields import (
    FieldItemCreate,
    FieldItemUpdate,
    create_fields,
    delete_fields,
    update_fields,
)
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.tools import ToolContext


@pytest.fixture
def table_ctx(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    return ToolContext(user=user, workspace=workspace), table


@pytest.mark.django_db
def test_create_fields_stores_a_raw_formula_unchanged(table_ctx):
    ctx, table = table_ctx

    result = create_fields(
        ctx,
        table.id,
        [FieldItemCreate(name="Joined", type="formula", formula="concat('a', 'b')")],
    )

    (created,) = result["created_fields"]
    assert created["name"] == "Joined"
    assert created["formula"] == "concat('a', 'b')"
    assert "errors" not in result
    field = table.field_set.get(name="Joined").specific
    assert field.formula == "concat('a', 'b')"


@pytest.mark.django_db
def test_create_fields_reports_an_invalid_formula_without_creating_it(table_ctx):
    ctx, table = table_ctx

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(name="Notes", type="text"),
            FieldItemCreate(name="Broken", type="formula", formula="concat("),
        ],
    )

    assert [field["name"] for field in result["created_fields"]] == ["Notes"]
    (error,) = result["errors"]
    assert (error["item"], error["code"]) == ("Broken", "invalid_formula")
    assert error["table_id"] == table.id
    assert error["field_name"] == "Broken"
    assert error["formula"] == "concat("
    assert "Invalid syntax" in error["message"]
    assert not Field.objects_and_trash.filter(table=table, name="Broken").exists()


@pytest.mark.django_db
def test_create_fields_rejects_a_formula_description(table_ctx):
    ctx, table = table_ctx

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(
                name="Full name", type="formula", formula="$formula: full name"
            )
        ],
    )

    assert result["created_fields"] == []
    assert result["errors"] == [
        {
            "item": "Full name",
            "code": "invalid_formula",
            "message": "'Full name' needs a formula, not a description. Write it in "
            "Baserow formula syntax.",
            "table_id": table.id,
            "field_name": "Full name",
            "formula": "$formula: full name",
        }
    ]
    assert not table.field_set.filter(name="Full name").exists()


@pytest.mark.django_db
def test_create_fields_hides_tables_of_other_workspaces(data_fixture, table_ctx):
    ctx, _table = table_ctx
    other_table = data_fixture.create_database_table(user=ctx.user)

    with pytest.raises(Table.DoesNotExist):
        create_fields(ctx, other_table.id, [FieldItemCreate(name="X", type="text")])
    assert not other_table.field_set.filter(name="X").exists()


@pytest.mark.django_db
def test_update_fields_stores_a_raw_formula_unchanged(data_fixture, table_ctx):
    ctx, table = table_ctx
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")

    result = update_fields(
        ctx, [FieldItemUpdate(field_id=field.id, formula="concat('a', 'b')")]
    )

    assert result["changed"] is True
    assert result["updated_fields"][0]["formula"] == "concat('a', 'b')"
    assert "errors" not in result
    field.refresh_from_db()
    assert field.formula == "concat('a', 'b')"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "formula,message",
    [
        ("concat(", "Invalid syntax"),
        (
            "$formula: full name",
            "'G' needs a formula, not a description. Write it in Baserow formula "
            "syntax.",
        ),
    ],
)
def test_update_fields_reports_an_invalid_formula_without_storing_it(
    data_fixture, table_ctx, formula, message
):
    ctx, table = table_ctx
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")

    result = update_fields(
        ctx, [FieldItemUpdate(field_id=field.id, name="G", formula=formula)]
    )

    assert result["updated_fields"] == []
    assert result["changed"] is False
    (error,) = result["errors"]
    assert (error["item"], error["code"]) == (field.id, "invalid_formula")
    assert error["table_id"] == table.id
    assert error["field_id"] == field.id
    assert error["field_name"] == "G"
    assert error["formula"] == formula
    assert message in error["message"]
    field.refresh_from_db()
    assert (field.name, field.formula) == ("F", "'x'")


@pytest.mark.django_db
def test_update_and_delete_treat_other_workspaces_as_missing(data_fixture, table_ctx):
    ctx, _table = table_ctx
    other_field = data_fixture.create_text_field(user=ctx.user, name="Other")
    missing_id = other_field.id + 1000

    updated = update_fields(
        ctx,
        [
            FieldItemUpdate(field_id=other_field.id, name="Renamed"),
            FieldItemUpdate(field_id=missing_id, name="Renamed"),
        ],
    )
    deleted = delete_fields(ctx, [other_field.id, missing_id])

    assert [(e["item"], e["code"]) for e in updated["errors"]] == [
        (other_field.id, "not_found"),
        (missing_id, "not_found"),
    ]
    assert deleted["deleted_field_ids"] == []
    assert [(e["item"], e["code"]) for e in deleted["errors"]] == [
        (other_field.id, "not_found"),
        (missing_id, "not_found"),
    ]
    other_field.refresh_from_db()
    assert other_field.name == "Other"
    assert not other_field.trashed


@pytest.mark.django_db
def test_delete_fields_trashes_the_fields(data_fixture, table_ctx):
    ctx, table = table_ctx
    field = data_fixture.create_text_field(table=table, name="Old")

    result = delete_fields(ctx, [field.id])

    assert result == {"deleted_field_ids": [field.id], "changed": True}
    assert Field.objects_and_trash.get(id=field.id).trashed


def _fail_after_doing(action_type, should_fail):
    """
    Patch an action's `do` so it applies the change and then raises, as a
    database error in the middle of an item would.
    """

    original = action_type.do

    def do(user, *args, **kwargs):
        result = original(user, *args, **kwargs)
        if should_fail(args, kwargs):
            raise IntegrityError("duplicate key value")
        return result

    return patch.object(action_type, "do", side_effect=do)


@pytest.mark.django_db
def test_create_fields_keeps_the_other_fields_when_one_fails(table_ctx):
    ctx, table = table_ctx

    with _fail_after_doing(CreateFieldActionType, lambda a, k: k["name"] == "Two"):
        result = create_fields(
            ctx,
            table.id,
            [
                FieldItemCreate(name="One", type="text"),
                FieldItemCreate(name="Two", type="text"),
                FieldItemCreate(name="Three", type="text"),
            ],
        )

    assert [f["name"] for f in result["created_fields"]] == ["One", "Three"]
    (error,) = result["errors"]
    assert error["item"] == "Two"
    assert set(table.field_set.values_list("name", flat=True)) == {
        "Name",
        "One",
        "Three",
    }


@pytest.mark.django_db
def test_update_fields_keeps_the_other_updates_when_one_fails(data_fixture, table_ctx):
    ctx, table = table_ctx
    fields = [
        data_fixture.create_text_field(table=table, name=name)
        for name in ("One", "Two", "Three")
    ]

    with _fail_after_doing(UpdateFieldActionType, lambda a, k: a[0].id == fields[1].id):
        result = update_fields(
            ctx,
            [FieldItemUpdate(field_id=f.id, name=f"{f.name} new") for f in fields],
        )

    assert [f["id"] for f in result["updated_fields"]] == [
        fields[0].id,
        fields[2].id,
    ]
    (error,) = result["errors"]
    assert error["item"] == fields[1].id
    assert [Field.objects.get(id=f.id).name for f in fields] == [
        "One new",
        "Two",
        "Three new",
    ]


@pytest.mark.django_db
def test_delete_fields_keeps_the_other_deletes_when_one_fails(data_fixture, table_ctx):
    ctx, table = table_ctx
    fields = [
        data_fixture.create_text_field(table=table, name=name)
        for name in ("One", "Two", "Three")
    ]

    with _fail_after_doing(DeleteFieldActionType, lambda a, k: a[0].id == fields[1].id):
        result = delete_fields(ctx, [f.id for f in fields])

    assert result["deleted_field_ids"] == [fields[0].id, fields[2].id]
    (error,) = result["errors"]
    assert error["item"] == fields[1].id
    assert [Field.objects_and_trash.get(id=f.id).trashed for f in fields] == [
        True,
        False,
        True,
    ]


@pytest.fixture
def error_records():
    records = []
    handler_id = loguru_logger.add(
        lambda m: records.append(m.record), level="ERROR", format="{message}"
    )
    yield records
    loguru_logger.remove(handler_id)


def _raise_unexpected(*args, **kwargs):
    raise RuntimeError("relation secret_table does not exist")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "action_type,run,errors_key",
    [
        (
            CreateFieldActionType,
            lambda ctx, table, field: create_fields(
                ctx, table.id, [FieldItemCreate(name="New", type="text")]
            ),
            "errors",
        ),
        (
            UpdateFieldActionType,
            lambda ctx, table, field: update_fields(
                ctx, [FieldItemUpdate(field_id=field.id, name="Renamed")]
            ),
            "errors",
        ),
        (
            DeleteFieldActionType,
            lambda ctx, table, field: delete_fields(ctx, [field.id]),
            "errors",
        ),
    ],
)
def test_field_tools_log_an_unexpected_error_and_hide_its_message(
    data_fixture, table_ctx, error_records, action_type, run, errors_key
):
    ctx, table = table_ctx
    field = data_fixture.create_text_field(table=table, name="Old")

    with patch.object(action_type, "do", side_effect=_raise_unexpected):
        result = run(ctx, table, field)

    (error,) = result[errors_key]
    assert error["code"] == "failed"
    assert error["message"] == "Internal error."
    (record,) = error_records
    assert record["exception"].type is RuntimeError


@pytest.mark.django_db
def test_field_tools_keep_the_message_of_an_expected_error(
    data_fixture, table_ctx, error_records
):
    ctx, table = table_ctx
    field = data_fixture.create_text_field(table=table, name="Old")
    primary = table.field_set.get(primary=True)

    created = create_fields(ctx, table.id, [FieldItemCreate(name="Old", type="text")])
    updated = update_fields(ctx, [FieldItemUpdate(field_id=field.id, name="Name")])
    deleted = delete_fields(ctx, [primary.id])

    (create_error,) = created["errors"]
    assert create_error["code"] == "conflict"
    assert create_error["message"].startswith("You cannot have two fields")
    (update_error,) = updated["errors"]
    assert (update_error["item"], update_error["code"]) == (field.id, "conflict")
    (delete_error,) = deleted["errors"]
    assert delete_error["item"] == primary.id
    assert delete_error["message"] == "Cannot delete the primary field of a table."
    assert error_records == []


@pytest.mark.django_db
@pytest.mark.parametrize("formula", [None, "", "  "])
def test_create_fields_reports_a_formula_field_without_a_formula(table_ctx, formula):
    ctx, table = table_ctx
    item = {"name": "Total", "type": "formula"}
    if formula is not None:
        item["formula"] = formula

    result = create_fields(ctx, table.id, [FieldItemCreate(**item)])

    assert result["created_fields"] == []
    assert result["errors"] == [
        {
            "item": "Total",
            "code": "invalid_formula",
            "message": "'Total' needs a formula.",
            "table_id": table.id,
            "field_name": "Total",
            "formula": formula or "",
        }
    ]
    assert not Field.objects_and_trash.filter(table=table, name="Total").exists()


@pytest.mark.django_db
def test_update_fields_reports_an_empty_formula(data_fixture, table_ctx):
    ctx, table = table_ctx
    field = data_fixture.create_formula_field(table=table, name="F", formula="'x'")

    result = update_fields(ctx, [FieldItemUpdate(field_id=field.id, formula="")])

    assert result["updated_fields"] == []
    assert result["errors"] == [
        {
            "item": field.id,
            "code": "invalid_formula",
            "message": "'F' needs a formula.",
            "table_id": table.id,
            "field_name": "F",
            "formula": "",
            "field_id": field.id,
            "index": 0,
        }
    ]
    field.refresh_from_db()
    assert field.formula == "'x'"


def test_create_fields_schema_has_no_default_formula():
    schema = FieldItemCreate.model_json_schema()["properties"]["formula"]

    assert schema.get("default") is None


def _call(endpoint, name, arguments):
    async def inner():
        token = current_key.set(endpoint.key)
        try:
            async with client_session(BaserowMCPServer()._mcp_server) as client:
                return await client.call_tool(name, arguments)
        finally:
            current_key.reset(token)

    with transaction.atomic():
        return async_to_sync(inner)()


FIELD_TOOLS = ["create_fields", "update_fields", "delete_fields"]


@pytest.mark.django_db
def test_field_tools_over_mcp(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=FIELD_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)

    created = _call(
        endpoint,
        "create_fields",
        {"table_id": table.id, "fields": [{"name": "Status", "type": "text"}]},
    )
    field_id = json.loads(created.content[0].text)["created_fields"][0]["id"]
    updated = _call(
        endpoint,
        "update_fields",
        {"fields": [{"field_id": field_id, "name": "State"}]},
    )
    deleted = _call(endpoint, "delete_fields", {"field_ids": [field_id]})

    assert created.isError is False
    assert json.loads(updated.content[0].text)["updated_fields"][0]["name"] == "State"
    assert json.loads(deleted.content[0].text) == {
        "deleted_field_ids": [field_id],
        "changed": True,
    }
    assert Field.objects_and_trash.get(id=field_id).trashed


@pytest.mark.django_db
def test_create_fields_over_mcp_table_in_other_workspace_is_not_found(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=FIELD_TOOLS)
    other_table = data_fixture.create_database_table(user=endpoint.user)

    result = _call(
        endpoint,
        "create_fields",
        {"table_id": other_table.id, "fields": [{"name": "X", "type": "text"}]},
    )

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."
    assert not other_table.field_set.filter(name="X").exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "tool,arguments",
    [
        (
            "update_fields",
            lambda field_id: {"fields": [{"field_id": field_id, "name": "Renamed"}]},
        ),
        ("delete_fields", lambda field_id: {"field_ids": [field_id]}),
    ],
)
def test_field_tools_over_mcp_treat_other_workspaces_as_missing(
    data_fixture, tool, arguments
):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=FIELD_TOOLS)
    other_field = data_fixture.create_text_field(user=endpoint.user, name="Other")
    missing_id = other_field.id + 1000

    other = json.loads(_call(endpoint, tool, arguments(other_field.id)).content[0].text)
    missing = json.loads(_call(endpoint, tool, arguments(missing_id)).content[0].text)

    assert [(e["item"], e["code"]) for e in other["errors"]] == [
        (other_field.id, "not_found")
    ]
    assert [(e["item"], e["code"]) for e in missing["errors"]] == [
        (missing_id, "not_found")
    ]
    assert other["errors"][0]["message"] == missing["errors"][0]["message"]
    other_field.refresh_from_db()
    assert other_field.name == "Other"
    assert not other_field.trashed


@pytest.mark.django_db
def test_update_fields_locks_the_field_like_the_rest_api(data_fixture, table_ctx):
    ctx, table = table_ctx
    field = data_fixture.create_single_select_field(table=table, name="Status")

    with CaptureQueriesContext(connection) as queries:
        update_fields(
            ctx, [FieldItemUpdate(field_id=field.id, add_options=[{"value": "New"}])]
        )

    locks = [
        q["sql"]
        for q in queries.captured_queries
        if "FOR UPDATE" in q["sql"] and '"database_field"' in q["sql"]
    ]
    assert locks
    assert list(field.select_options.values_list("value", flat=True)) == ["New"]


def _field_names(table):
    model = Table.objects.get(id=table.id).get_model()
    return sorted(f["field"].name for f in model._field_objects.values())


@pytest.mark.django_db
def test_update_fields_drops_the_model_cached_in_a_failed_update(
    data_fixture, table_ctx
):
    ctx, table = table_ctx
    field = data_fixture.create_number_field(table=table, name="Num")

    with _fail_after_doing(UpdateFieldActionType, lambda a, k: True):
        update_fields(ctx, [FieldItemUpdate(field_id=field.id, name="Renamed")])

    assert _field_names(table) == ["Name", "Num"]


@pytest.mark.django_db
def test_delete_fields_drops_the_model_cached_in_a_failed_delete(
    data_fixture, table_ctx
):
    ctx, table = table_ctx
    field = data_fixture.create_number_field(table=table, name="Num")

    with _fail_after_doing(DeleteFieldActionType, lambda a, k: True):
        delete_fields(ctx, [field.id])

    assert _field_names(table) == ["Name", "Num"]


@pytest.fixture
def linked_tables(data_fixture, table_ctx):
    ctx, table = table_ctx
    other = data_fixture.create_database_table(database=table.database, name="Other")
    data_fixture.create_text_field(table=other, name="Title", primary=True)
    return ctx, table, other


@pytest.mark.django_db
@pytest.mark.parametrize("key", ["through_field", "through_field_id"])
def test_create_fields_looks_up_through_the_named_link_field(
    data_fixture, linked_tables, key
):
    ctx, table, other = linked_tables
    data_fixture.create_link_row_field(table=table, name="First", link_row_table=other)
    second = data_fixture.create_link_row_field(
        table=table, name="Second", link_row_table=other
    )

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(
                **{"name": "Titles", "type": "lookup", key: second.id},
                target_field="Title",
            )
        ],
    )

    assert "errors" not in result
    (created,) = result["created_fields"]
    assert created["through_field"] == second.id
    assert table.field_set.get(name="Titles").specific.through_field_id == second.id


@pytest.mark.django_db
def test_create_fields_looks_up_through_a_link_field_named_by_name(
    data_fixture, linked_tables
):
    ctx, table, other = linked_tables
    link = data_fixture.create_link_row_field(
        table=table, name="Link", link_row_table=other
    )

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(
                name="Titles", type="lookup", through_field="Link", target_field="Title"
            )
        ],
    )

    assert [f["through_field"] for f in result["created_fields"]] == [link.id]


@pytest.mark.django_db
def test_create_fields_reports_a_through_field_that_is_no_link_of_the_table(
    data_fixture, linked_tables
):
    ctx, table, other = linked_tables
    text = data_fixture.create_text_field(table=table, name="Notes")

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(
                name="Titles",
                type="lookup",
                through_field=text.id,
                target_field="Title",
            )
        ],
    )

    assert result["created_fields"] == []
    (error,) = result["errors"]
    assert f"has no link_row field '{text.id}' for lookup 'Titles'" in error["message"]
    assert set(table.field_set.values_list("name", flat=True)) == {"Name", "Notes"}


@pytest.mark.django_db
def test_create_fields_returns_the_link_field_a_lookup_creates(linked_tables):
    ctx, table, other = linked_tables

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(
                name="Titles", type="lookup", linked_table="Other", target_field="Title"
            )
        ],
    )

    link, lookup = result["created_fields"]
    assert (link["name"], link["type"], link["linked_table"]) == (
        "Other",
        "link_row",
        other.id,
    )
    assert (lookup["name"], lookup["through_field"]) == ("Titles", link["id"])


@pytest.mark.django_db
def test_create_fields_matches_a_link_field_name_ignoring_case_and_outer_spaces(
    data_fixture, linked_tables
):
    ctx, table, other = linked_tables
    link = data_fixture.create_link_row_field(
        table=table, name="Link", link_row_table=other
    )

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(
                name="Titles",
                type="lookup",
                through_field=" link ",
                target_field="Title",
            )
        ],
    )

    assert [f["through_field"] for f in result["created_fields"]] == [link.id]


@pytest.mark.django_db
def test_update_fields_applies_a_rename_before_a_formula_that_uses_it(
    data_fixture, table_ctx
):
    ctx, table = table_ctx
    # The formula field has the lower id, so an id order would update it first.
    double = data_fixture.create_formula_field(table=table, name="Double", formula="1")
    price = data_fixture.create_number_field(table=table, name="Price")

    result = update_fields(
        ctx,
        [
            FieldItemUpdate(field_id=price.id, name="Cost"),
            FieldItemUpdate(field_id=double.id, formula="field('Cost') * 2"),
        ],
    )

    assert "errors" not in result
    assert [f["name"] for f in result["updated_fields"]] == ["Cost", "Double"]
    double.refresh_from_db()
    assert double.formula == "field('Cost') * 2"


@pytest.mark.django_db
def test_update_fields_locks_every_field_up_front_in_table_order(
    data_fixture, table_ctx
):
    ctx, table = table_ctx
    later = data_fixture.create_database_table(database=table.database)
    later_field = data_fixture.create_text_field(table=later, name="Later")
    first = data_fixture.create_text_field(table=table, name="First")

    with CaptureQueriesContext(connection) as queries:
        update_fields(
            ctx,
            [
                FieldItemUpdate(field_id=later_field.id, name="Later new"),
                FieldItemUpdate(field_id=first.id, name="First new"),
            ],
        )

    sqls = [q["sql"] for q in queries.captured_queries]
    lock = next(i for i, sql in enumerate(sqls) if "FOR UPDATE" in sql)
    assert (
        'ORDER BY "database_field"."table_id" ASC, "database_field"."id" ASC'
        in (sqls[lock])
    )
    assert not any(sql.startswith("UPDATE") for sql in sqls[:lock])


@pytest.mark.django_db
def test_update_fields_over_mcp_reports_a_lock_conflict(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=FIELD_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_text_field(table=table, name="Name")

    def locked(*args, **kwargs):
        raise DatabaseError("could not obtain lock on row in relation")

    with patch.object(fields_module, "_fields_to_lock", locked):
        result = _call(
            endpoint,
            "update_fields",
            {"fields": [{"field_id": field.id, "name": "Renamed"}]},
        )

    assert result.isError is True
    assert result.content[0].text == (
        "Invalid value. The requested field is already being updated or used by "
        "another operation, please try again after other concurrent operations "
        "have finished."
    )


@pytest.mark.django_db
@pytest.mark.parametrize("field_type", ["single_select", "multiple_select"])
def test_create_fields_rejects_options_that_share_a_value(table_ctx, field_type):
    ctx, table = table_ctx

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(
                name="Status", type=field_type, options=["Open", " open ", "Done"]
            ),
            FieldItemCreate(name="Notes", type="text"),
        ],
    )

    assert [f["name"] for f in result["created_fields"]] == ["Notes"]
    (error,) = result["errors"]
    assert error["item"] == "Status"
    assert "the new option 'Open' and the new option ' open '" in error["message"]
    assert not table.field_set.filter(name="Status").exists()


@pytest.mark.django_db
def test_create_fields_looks_up_through_the_only_link_field(
    data_fixture, linked_tables
):
    ctx, table, other = linked_tables
    link = data_fixture.create_link_row_field(
        table=table, name="Link", link_row_table=other
    )

    result = create_fields(
        ctx,
        table.id,
        [FieldItemCreate(name="Titles", type="lookup", target_field="Title")],
    )

    assert "errors" not in result
    assert [f["through_field"] for f in result["created_fields"]] == [link.id]


@pytest.mark.django_db
@pytest.mark.parametrize("links", [0, 2])
def test_create_fields_needs_the_link_when_the_table_has_not_exactly_one(
    data_fixture, linked_tables, links
):
    ctx, table, other = linked_tables
    for name in ["First", "Second"][:links]:
        data_fixture.create_link_row_field(table=table, name=name, link_row_table=other)

    result = create_fields(
        ctx,
        table.id,
        [FieldItemCreate(name="Titles", type="lookup", target_field="Title")],
    )

    assert result["created_fields"] == []
    (error,) = result["errors"]
    assert error["hint"] == "Set linked_table or through_field."
    if links:
        assert "'First', 'Second'" in error["message"]
    assert not table.field_set.filter(name="Titles").exists()


@pytest.mark.django_db
def test_create_fields_answers_an_error_when_no_field_was_created(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    other = data_fixture.create_database_table(user=user)
    ctx = ToolContext(user=user, workspace=table.database.workspace)

    result = create_fields(
        ctx,
        table.id,
        [FieldItemCreate(name="Link", type="link_row", linked_table=other.id)],
    )

    assert result["created_fields"] == [] and result["changed"] is False
    (error,) = result["errors"]
    assert error["item"] == "Link" and error["code"] == "invalid_input"
    assert result["error"] == {"code": "invalid_input", "message": error["message"]}
    assert "table_" not in error["message"]


@pytest.mark.django_db
def test_a_link_to_a_table_of_another_database_says_so(data_fixture, table_ctx):
    ctx, table = table_ctx
    data_fixture.create_database_table(
        database=data_fixture.create_database_application(workspace=ctx.workspace),
        name="Activity QA",
    )

    result = create_fields(
        ctx,
        table.id,
        [FieldItemCreate(name="Act", type="link_row", linked_table="Activity QA")],
    )

    (error,) = result["errors"]
    assert error["message"] == (
        "Table 'Activity QA' is in another database, and a link can only point to "
        "a table of the same database."
    )
    assert error["hint"] == "Link to a table of this database, by name or ID."


@pytest.mark.django_db
def test_partial_field_creation_is_a_change_with_item_errors(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    data_fixture.create_text_field(table=table, name="Taken")
    ctx = ToolContext(user=user, workspace=table.database.workspace)

    result = create_fields(
        ctx,
        table.id,
        [
            FieldItemCreate(name="Notes", type="text"),
            FieldItemCreate(name="Taken", type="text"),
            FieldItemCreate(name="Total", type="formula", formula="unknown("),
        ],
    )

    assert [f["name"] for f in result["created_fields"]] == ["Notes"]
    assert result["changed"] is True and "error" not in result
    assert [(e["item"], e["code"]) for e in result["errors"]] == [
        ("Taken", "conflict"),
        ("Total", "invalid_formula"),
    ]
    assert result["errors"][1]["formula"] == "unknown("


@pytest.mark.django_db
def test_update_fields_without_changes_is_unchanged_without_error(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    field = data_fixture.create_text_field(table=table, name="Name")
    ctx = ToolContext(user=user, workspace=table.database.workspace)

    result = update_fields(ctx, [FieldItemUpdate(field_id=field.id, name="Name")])

    assert result["changed"] is False
    assert "error" not in result and "errors" not in result


@pytest.mark.django_db
def test_delete_fields_answers_an_error_when_nothing_was_deleted(data_fixture):
    user = data_fixture.create_user()
    table = data_fixture.create_database_table(user=user)
    primary = data_fixture.create_text_field(table=table, name="Name", primary=True)
    ctx = ToolContext(user=user, workspace=table.database.workspace)

    result = delete_fields(ctx, [primary.id])

    assert result["deleted_field_ids"] == []
    assert result["errors"][0]["item"] == primary.id
    assert result["error"]["message"] == result["errors"][0]["message"]
