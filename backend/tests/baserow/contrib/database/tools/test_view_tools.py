"""Tests for the view tools shared by MCP and Kuma."""

import json
import logging
from unittest.mock import patch

from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import connection, transaction

import pytest
from asgiref.sync import async_to_sync
from loguru import logger as loguru_logger
from mcp.shared.memory import (
    create_connected_server_and_client_session as client_session,
)

from baserow.contrib.database.tools import views as views_module
from baserow.contrib.database.tools.views import (
    ViewFilterItemCreate,
    ViewFiltersArgs,
    ViewItemCreate,
    create_view_filters,
    create_views,
)
from baserow.contrib.database.views.models import FormView, View, ViewFilter
from baserow.core.exceptions import PermissionException
from baserow.core.mcp import BaserowMCPServer, current_key
from baserow.core.tools import ToolContext

VIEW_TOOLS = ["create_views", "create_view_filters"]


@pytest.fixture
def table_ctx(data_fixture):
    user = data_fixture.create_user()
    workspace = data_fixture.create_workspace(user=user)
    database = data_fixture.create_database_application(workspace=workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)
    return ToolContext(user=user, workspace=workspace), table


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


def _call(endpoint, name, arguments):
    async def callback(client):
        return await client.call_tool(name, arguments)

    return _session(endpoint, callback)


@pytest.mark.django_db
def test_create_views_skips_names_already_used(data_fixture, table_ctx):
    ctx, table = table_ctx
    data_fixture.create_grid_view(table=table, name="Grid")

    result = create_views(
        ctx,
        table.id,
        [
            ViewItemCreate(name="Grid", type="grid"),
            ViewItemCreate(name="Open", type="grid"),
            ViewItemCreate(name="Open", type="grid"),
        ],
    )

    assert [view["name"] for view in result["created_views"]] == ["Open"]
    assert result["skipped_views"] == ["Grid", "Open"]
    assert sorted(View.objects.filter(table=table).values_list("name", flat=True)) == [
        "Grid",
        "Open",
    ]


@pytest.mark.django_db
def test_create_views_without_duplicates_lists_no_skipped_views(table_ctx):
    ctx, table = table_ctx

    result = create_views(ctx, table.id, [ViewItemCreate(name="All", type="grid")])

    assert "skipped_views" not in result


@pytest.mark.django_db
def test_create_view_filters_returns_the_skipped_filters(data_fixture, table_ctx):
    ctx, table = table_ctx
    number = data_fixture.create_number_field(table=table, name="Amount")
    view = data_fixture.create_grid_view(table=table)

    result = create_view_filters(
        ctx,
        [
            ViewFiltersArgs(
                view_id=view.id,
                filters=[
                    ViewFilterItemCreate(
                        field_id=number.id,
                        type="number",
                        operator="higher_than",
                        value=10,
                    ),
                    ViewFilterItemCreate(
                        field_id=number.id, type="text", operator="equal", value="x"
                    ),
                ],
            )
        ],
    )

    (entry,) = result["created_view_filters"]
    assert [f["field_id"] for f in entry["filters"]] == [number.id]
    (skipped,) = entry["skipped_filters"]
    assert skipped["field_id"] == number.id
    assert skipped["type"] == "text"
    assert "is type 'number'" in skipped["error"]
    assert result["changed"] is True
    assert ViewFilter.objects.filter(view=view).count() == 1


@pytest.mark.django_db
@pytest.mark.parametrize(
    "error", [PermissionException(), RuntimeError("the second view failed")]
)
def test_create_view_filters_writes_nothing_when_a_later_view_fails(
    data_fixture, table_ctx, error
):
    ctx, table = table_ctx
    number = data_fixture.create_number_field(table=table, name="Amount")
    first_view = data_fixture.create_grid_view(table=table)
    second_view = data_fixture.create_grid_view(table=table)
    original = views_module.create_view_filter

    def create_view_filter(user, view, fields, item, timezone=None):
        if view.id == second_view.id:
            raise error
        return original(user, view, fields, item, timezone)

    filters = [
        ViewFilterItemCreate(
            field_id=number.id, type="number", operator="higher_than", value=10
        )
    ]
    with (
        patch.object(views_module, "create_view_filter", create_view_filter),
        pytest.raises(type(error)),
    ):
        create_view_filters(
            ctx,
            [
                ViewFiltersArgs(view_id=first_view.id, filters=filters),
                ViewFiltersArgs(view_id=second_view.id, filters=filters),
            ],
        )

    assert not ViewFilter.objects.filter(view=first_view).exists()


@pytest.mark.django_db
def test_view_tools_over_mcp(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)

    async def callback(client):
        listed = await client.list_tools()
        created = await client.call_tool(
            "create_views",
            {"table_id": table.id, "views": [{"name": "Open", "type": "grid"}]},
        )
        view_id = json.loads(created.content[0].text)["created_views"][0]["id"]
        filtered = await client.call_tool(
            "create_view_filters",
            {
                "view_filters": [
                    {
                        "view_id": view_id,
                        "filters": [
                            {
                                "field_id": name.id,
                                "type": "text",
                                "operator": "contains",
                                "value": "a",
                            }
                        ],
                    }
                ]
            },
        )
        return listed, view_id, filtered

    listed, view_id, filtered = _session(endpoint, callback)

    tools = {tool.name: tool for tool in listed.tools}
    assert set(tools["create_views"].inputSchema["properties"]) == {
        "table_id",
        "views",
    }
    assert set(tools["create_view_filters"].inputSchema["properties"]) == {
        "view_filters"
    }
    for tool in (tools["create_views"], tools["create_view_filters"]):
        for kuma_only in ("ask_user", "navigate", "get_tables_schema", "sample"):
            assert kuma_only not in tool.description
    assert filtered.isError is False
    assert ViewFilter.objects.get(view_id=view_id).type == "contains"


@pytest.mark.django_db
def test_create_views_over_mcp_table_in_other_workspace_is_not_found(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    other_table = data_fixture.create_database_table(user=endpoint.user)

    result = _call(
        endpoint,
        "create_views",
        {"table_id": other_table.id, "views": [{"name": "Open", "type": "grid"}]},
    )

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."
    assert not View.objects.filter(table=other_table).exists()


@pytest.mark.django_db
def test_create_view_filters_over_mcp_view_in_other_workspace_is_not_found(
    data_fixture,
):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    other_table = data_fixture.create_database_table(user=endpoint.user)
    field = data_fixture.create_text_field(table=other_table, name="Name")
    other_view = data_fixture.create_grid_view(table=other_table)

    result = _call(
        endpoint,
        "create_view_filters",
        {
            "view_filters": [
                {
                    "view_id": other_view.id,
                    "filters": [
                        {
                            "field_id": field.id,
                            "type": "text",
                            "operator": "equal",
                            "value": "a",
                        }
                    ],
                }
            ]
        },
    )

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."
    assert not ViewFilter.objects.filter(view=other_view).exists()


@pytest.fixture
def error_records():
    records = []
    handler_id = loguru_logger.add(
        lambda m: records.append(m.record), level="ERROR", format="{message}"
    )
    yield records
    loguru_logger.remove(handler_id)


@pytest.fixture
def select_view(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_single_select_field(table=table, name="Status")
    data_fixture.create_select_option(field=field, value="Active")
    view = data_fixture.create_grid_view(table=table)
    return endpoint, field, view


def _select_filter(view, field, value):
    return {
        "view_filters": [
            {
                "view_id": view.id,
                "filters": [
                    {
                        "field_id": field.id,
                        "type": "single_select",
                        "operator": "is_any_of",
                        "value": value,
                    }
                ],
            }
        ]
    }


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["Active", 3, None, []])
def test_create_view_filters_over_mcp_rejects_a_select_value_that_is_not_a_list(
    select_view, caplog, error_records, value
):
    endpoint, field, view = select_view

    result = _call(endpoint, "create_view_filters", _select_filter(view, field, value))

    assert result.isError is True
    assert "list of option labels" in result.content[0].text
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert error_records == []
    assert not ViewFilter.objects.filter(view=view).exists()


@pytest.mark.django_db
def test_create_view_filters_over_mcp_skips_labels_that_match_no_option(
    select_view, caplog, error_records
):
    endpoint, field, view = select_view

    result = _call(
        endpoint, "create_view_filters", _select_filter(view, field, ["Closed"])
    )

    assert result.isError is False
    (entry,) = json.loads(result.content[0].text)["created_view_filters"]
    assert entry["filters"] == []
    (skipped,) = entry["skipped_filters"]
    assert "are not options of field 'Status'" in skipped["error"]
    assert "Active" in skipped["error"]
    assert [r for r in caplog.records if r.levelno >= logging.ERROR] == []
    assert error_records == []
    assert not ViewFilter.objects.filter(view=view).exists()


@pytest.mark.django_db
def test_create_view_filters_over_mcp_writes_nothing_when_a_view_is_not_found(
    select_view, data_fixture
):
    endpoint, field, view = select_view
    other_view = data_fixture.create_grid_view(
        table=data_fixture.create_database_table(user=endpoint.user)
    )
    arguments = _select_filter(view, field, ["Active"])
    arguments["view_filters"].append({"view_id": other_view.id, "filters": []})

    result = _call(endpoint, "create_view_filters", arguments)

    assert result.isError is True
    assert result.content[0].text == "Not found in this workspace."
    assert not ViewFilter.objects.filter(view=view).exists()


@pytest.mark.django_db
def test_create_view_filters_over_mcp_skips_the_filters_of_a_form_view(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)
    grid = data_fixture.create_grid_view(table=table)
    form = data_fixture.create_form_view(table=table)
    text_filter = {"field_id": name.id, "type": "text", "operator": "equal"}

    result = _call(
        endpoint,
        "create_view_filters",
        {
            "view_filters": [
                {"view_id": grid.id, "filters": [{**text_filter, "value": "a"}]},
                {"view_id": form.id, "filters": [{**text_filter, "value": "b"}]},
            ]
        },
    )

    assert result.isError is False
    grid_entry, form_entry = json.loads(result.content[0].text)["created_view_filters"]
    assert len(grid_entry["filters"]) == 1
    assert form_entry["filters"] == []
    (skipped,) = form_entry["skipped_filters"]
    assert skipped["error"] == "Filtering is not supported for form views."
    assert ViewFilter.objects.filter(view=grid).count() == 1
    assert not ViewFilter.objects.filter(view=form).exists()


@pytest.mark.django_db
def test_create_views_stores_the_form_submit_settings(table_ctx):
    ctx, table = table_ctx
    name = table.field_set.get(name="Name")

    result = create_views(
        ctx,
        table.id,
        [
            ViewItemCreate(
                name="Contact",
                type="form",
                submit_button_label="Go",
                submit_action="REDIRECT",
                submit_action_message="Thanks",
                submit_action_redirect_url="https://example.com",
                receive_notification_on_submit=True,
                field_options=[
                    {
                        "field_id": name.id,
                        "name": "Name",
                        "description": "",
                        "required": True,
                        "order": 1,
                    }
                ],
            )
        ],
    )

    (created,) = result["created_views"]
    form = FormView.objects.get(id=created["id"])
    assert form.submit_text == created["submit_button_label"] == "Go"
    assert form.submit_action == created["submit_action"] == "REDIRECT"
    assert form.submit_action_message == "Thanks"
    assert form.submit_action_redirect_url == "https://example.com"
    assert list(form.users_to_notify_on_submit.all()) == [ctx.user]


def _filter_view(data_fixture, table_ctx, field):
    ctx, table = table_ctx
    view = data_fixture.create_grid_view(table=table)

    def create(**item):
        result = create_view_filters(
            ctx,
            [
                ViewFiltersArgs(
                    view_id=view.id,
                    filters=[ViewFilterItemCreate(field_id=field.id, **item)],
                )
            ],
        )
        return result["created_view_filters"][0]

    return view, create


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mode,value,stored",
    [
        ("today", "", "UTC??today"),
        ("today", None, "UTC??today"),
        ("this_week", "", "UTC??this_week"),
        ("nr_days_ago", "7", "UTC?7?nr_days_ago"),
        ("nr_days_ago", 7, "UTC?7?nr_days_ago"),
        ("nr_months_from_now", " 2 ", "UTC?2?nr_months_from_now"),
        ("exact_date", "2024-01-05", "UTC?2024-01-05?exact_date"),
    ],
)
def test_create_view_filters_reads_the_date_value_by_mode(
    data_fixture, table_ctx, mode, value, stored
):
    field = data_fixture.create_date_field(table=table_ctx[1], name="Due")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="date", operator="equal", mode=mode, value=value)

    assert "skipped_filters" not in entry
    assert ViewFilter.objects.get(view=view).value == stored


@pytest.mark.django_db
@pytest.mark.parametrize(
    "mode,value",
    [("nr_days_ago", "a week"), ("nr_days_ago", -3), ("exact_date", 5)],
)
def test_create_view_filters_skips_a_date_value_the_mode_cannot_use(
    data_fixture, table_ctx, mode, value
):
    field = data_fixture.create_date_field(table=table_ctx[1], name="Due")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="date", operator="equal", mode=mode, value=value)

    (skipped,) = entry["skipped_filters"]
    assert f"'{mode}' needs" in skipped["error"]
    assert not ViewFilter.objects.filter(view=view).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "value,stored",
    [
        ("false", "0"),
        ("FALSE", "0"),
        ("0", "0"),
        ("no", "0"),
        ("", "0"),
        (False, "0"),
        ("true", "1"),
        ("Yes", "1"),
        ("1", "1"),
        (True, "1"),
    ],
)
def test_create_view_filters_reads_a_boolean_value(
    data_fixture, table_ctx, value, stored
):
    field = data_fixture.create_boolean_field(table=table_ctx[1], name="Done")
    view, create = _filter_view(data_fixture, table_ctx, field)

    create(type="boolean", operator="equal", value=value)

    assert ViewFilter.objects.get(view=view).value == stored


@pytest.mark.django_db
def test_create_view_filters_skips_a_boolean_value_that_is_not_true_or_false(
    data_fixture, table_ctx
):
    field = data_fixture.create_boolean_field(table=table_ctx[1], name="Done")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="boolean", operator="equal", value="maybe")

    (skipped,) = entry["skipped_filters"]
    assert skipped["error"] == "A boolean filter needs true or false, not 'maybe'."
    assert not ViewFilter.objects.filter(view=view).exists()


@pytest.mark.django_db
def test_create_view_filters_matches_labels_ignoring_case_and_outer_spaces(
    data_fixture, table_ctx
):
    field = data_fixture.create_single_select_field(table=table_ctx[1], name="Status")
    active = data_fixture.create_select_option(field=field, value="Active")
    done = data_fixture.create_select_option(field=field, value="Done")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(
        type="single_select", operator="is_any_of", value=["active", " Done "]
    )

    assert "skipped_filters" not in entry
    assert ViewFilter.objects.get(view=view).value == f"{active.id},{done.id}"


@pytest.mark.django_db
def test_create_view_filters_skips_a_select_filter_with_an_unknown_label(
    data_fixture, table_ctx
):
    field = data_fixture.create_single_select_field(table=table_ctx[1], name="Status")
    data_fixture.create_select_option(field=field, value="Active")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="single_select", operator="is_any_of", value=["Active", "Nope"])

    assert entry["filters"] == []
    (skipped,) = entry["skipped_filters"]
    assert skipped["error"] == (
        "['Nope'] are not options of field 'Status'. Options: Active."
    )
    assert not ViewFilter.objects.filter(view=view).exists()


@pytest.mark.django_db
def test_create_views_over_mcp_rejects_a_form_field_order_out_of_range(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)

    result = _call(
        endpoint,
        "create_views",
        {
            "table_id": table.id,
            "views": [
                {
                    "name": "Contact",
                    "type": "form",
                    "field_options": [
                        {
                            "field_id": name.id,
                            "name": "Name",
                            "description": "",
                            "required": True,
                            "order": 40000,
                        }
                    ],
                }
            ],
        },
    )

    assert result.isError is True
    assert result.content[0].text.startswith("Invalid arguments. views.0.")
    assert "less than or equal to 32767" in result.content[0].text
    assert not FormView.objects.filter(table=table).exists()


@pytest.mark.django_db
def test_create_views_reports_a_database_error_in_the_field_options(table_ctx):
    ctx, table = table_ctx
    name = table.field_set.get(name="Name")

    def fail(*args, **kwargs):
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1/0")

    with (
        patch.object(views_module.UpdateViewFieldOptionsActionType, "do", fail),
        pytest.raises(DjangoValidationError) as exc_info,
    ):
        create_views(
            ctx,
            table.id,
            [
                ViewItemCreate(
                    name="Contact",
                    type="form",
                    field_options=[
                        {
                            "field_id": name.id,
                            "name": "Name",
                            "description": "",
                            "required": True,
                            "order": 1,
                        }
                    ],
                )
            ],
        )

    assert "were rejected and no views were created" in exc_info.value.messages[0]
    assert f"{name.id} (Name, text)" in exc_info.value.messages[0]


def _form_view_arguments(table, name, **settings):
    return {
        "table_id": table.id,
        "views": [
            {
                "name": "Contact",
                "type": "form",
                "submit_action": "REDIRECT",
                "field_options": [
                    {
                        "field_id": name.id,
                        "name": "Name",
                        "description": "",
                        "required": True,
                        "order": 1,
                    }
                ],
                **settings,
            }
        ],
    }


@pytest.mark.django_db
@pytest.mark.parametrize(
    "url,error",
    [
        ("javascript:alert(1)", "is not a valid URL"),
        ("https://example.com/" + "a" * 2000, "at most 2000 characters"),
    ],
)
def test_create_views_over_mcp_rejects_an_unsafe_redirect_url(data_fixture, url, error):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)

    result = _call(
        endpoint,
        "create_views",
        _form_view_arguments(table, name, submit_action_redirect_url=url),
    )

    assert result.isError is True
    assert result.content[0].text.startswith("Invalid arguments. views.0.")
    assert error in result.content[0].text
    assert not FormView.objects.filter(table=table).exists()


@pytest.mark.django_db
def test_create_views_over_mcp_stores_an_https_redirect_url(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    name = data_fixture.create_text_field(table=table, name="Name", primary=True)

    result = _call(
        endpoint,
        "create_views",
        _form_view_arguments(
            table, name, submit_action_redirect_url="https://example.com/thanks"
        ),
    )

    assert result.isError is False
    form = FormView.objects.get(table=table)
    assert form.submit_action_redirect_url == "https://example.com/thanks"


@pytest.mark.django_db
@pytest.mark.parametrize("value", ["2024-01-05", 7])
def test_create_view_filters_reports_a_value_a_relative_date_mode_ignores(
    data_fixture, table_ctx, value
):
    field = data_fixture.create_date_field(table=table_ctx[1], name="Due")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="date", operator="equal", mode="today", value=value)

    (created,) = entry["filters"]
    assert created["value"] is None
    assert created["note"] == "The value was ignored: mode 'today' takes none."
    assert ViewFilter.objects.get(view=view).value == "UTC??today"


@pytest.mark.django_db
def test_create_view_filters_adds_no_note_without_a_value(data_fixture, table_ctx):
    field = data_fixture.create_date_field(table=table_ctx[1], name="Due")
    _, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="date", operator="equal", mode="this_week", value="")

    (created,) = entry["filters"]
    assert created["value"] is None
    assert "note" not in created


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operator,stored", [("gte", "higher_than_or_equal"), ("lte", "lower_than_or_equal")]
)
def test_create_view_filters_reads_gte_and_lte_as_inclusive(
    data_fixture, table_ctx, operator, stored
):
    field = data_fixture.create_number_field(table=table_ctx[1], name="Price")
    view, create = _filter_view(data_fixture, table_ctx, field)

    create(type="number", operator=operator, value=100)

    assert ViewFilter.objects.get(view=view).type == stored


@pytest.mark.django_db
@pytest.mark.parametrize("operator", ["has", "has_not"])
@pytest.mark.parametrize("value", [None, "", "row 5", "1.5", True])
def test_create_view_filters_skips_a_link_row_value_that_is_not_a_row_id(
    data_fixture, table_ctx, operator, value
):
    other = data_fixture.create_database_table(database=table_ctx[1].database)
    data_fixture.create_text_field(table=other, name="Title", primary=True)
    field = data_fixture.create_link_row_field(
        table=table_ctx[1], name="Link", link_row_table=other
    )
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="link_row", operator=operator, value=value)

    (skipped,) = entry["skipped_filters"]
    assert "needs a row id" in skipped["error"]
    assert not ViewFilter.objects.filter(view=view).exists()


@pytest.mark.django_db
@pytest.mark.parametrize("value", [5, "5", " 5 "])
def test_create_view_filters_stores_a_link_row_id(data_fixture, table_ctx, value):
    other = data_fixture.create_database_table(database=table_ctx[1].database)
    data_fixture.create_text_field(table=other, name="Title", primary=True)
    field = data_fixture.create_link_row_field(
        table=table_ctx[1], name="Link", link_row_table=other
    )
    view, create = _filter_view(data_fixture, table_ctx, field)

    create(type="link_row", operator="has", value=value)

    assert ViewFilter.objects.get(view=view).value == "5"


@pytest.mark.django_db
@pytest.mark.parametrize("operator", ["equal", "not_equal", "gt", "lte"])
@pytest.mark.parametrize("value", [None, "", "many", "nan", True])
def test_create_view_filters_skips_a_number_value_that_is_not_a_number(
    data_fixture, table_ctx, operator, value
):
    field = data_fixture.create_number_field(table=table_ctx[1], name="Price")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="number", operator=operator, value=value)

    (skipped,) = entry["skipped_filters"]
    assert "needs a number" in skipped["error"]
    assert not ViewFilter.objects.filter(view=view).exists()


@pytest.mark.django_db
@pytest.mark.parametrize(
    "operator,value,stored",
    [("equal", 1.5, "1.5"), ("higher_than", "-3", "-3")],
)
def test_create_view_filters_stores_a_number_value(
    data_fixture, table_ctx, operator, value, stored
):
    field = data_fixture.create_number_field(table=table_ctx[1], name="Price")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="number", operator=operator, value=value)

    assert "skipped_filters" not in entry
    assert ViewFilter.objects.get(view=view).value == stored


@pytest.mark.django_db
@pytest.mark.parametrize("operator", ["empty", "not_empty"])
def test_create_view_filters_takes_no_number_for_empty(
    data_fixture, table_ctx, operator
):
    field = data_fixture.create_number_field(table=table_ctx[1], name="Price")
    view, create = _filter_view(data_fixture, table_ctx, field)

    entry = create(type="number", operator=operator)

    assert "skipped_filters" not in entry
    view_filter = ViewFilter.objects.get(view=view)
    assert (view_filter.type, view_filter.value) == (operator, "")


@pytest.mark.django_db
@pytest.mark.parametrize(
    "timezone,stored",
    [
        (None, "UTC??today"),
        ("", "UTC??today"),
        ("Europe/Amsterdam", "Europe/Amsterdam??today"),
    ],
)
def test_create_view_filters_uses_the_context_timezone(
    data_fixture, table_ctx, timezone, stored
):
    ctx, table = table_ctx
    ctx.timezone = timezone
    field = data_fixture.create_date_field(table=table, name="Due")
    view, create = _filter_view(data_fixture, table_ctx, field)

    create(type="date", operator="equal", mode="today")

    assert ViewFilter.objects.get(view=view).value == stored


@pytest.mark.django_db
def test_create_view_filters_works_for_an_agent_identity(data_fixture, table_ctx):
    ctx, table = table_ctx
    agent = data_fixture.create_agent(
        workspace=ctx.workspace, name="Bot", role_uid="ADMIN"
    )
    field = table.field_set.get(name="Name")
    view, create = _filter_view(
        data_fixture, (ToolContext(user=agent, workspace=ctx.workspace), table), field
    )

    entry = create(type="text", operator="equal", value="x")

    assert "skipped_filters" not in entry
    assert ViewFilter.objects.get(view=view).value == "x"


@pytest.mark.django_db
def test_create_views_over_mcp_rejects_a_name_longer_than_the_column(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    data_fixture.create_text_field(table=table, name="Name", primary=True)

    result = _call(
        endpoint,
        "create_views",
        {"table_id": table.id, "views": [{"name": "x" * 256, "type": "grid"}]},
    )

    assert result.isError is True
    assert "at most 255 characters" in result.content[0].text
    assert not View.objects.filter(table=table).exists()


@pytest.mark.django_db
def test_create_view_filters_over_mcp_uses_the_user_timezone(data_fixture):
    endpoint = data_fixture.create_mcp_endpoint(allowed_tools=VIEW_TOOLS)
    endpoint.user.profile.timezone = "Europe/Amsterdam"
    endpoint.user.profile.save()
    database = data_fixture.create_database_application(workspace=endpoint.workspace)
    table = data_fixture.create_database_table(database=database)
    field = data_fixture.create_date_field(table=table, name="Due")
    view = data_fixture.create_grid_view(table=table)

    result = _call(
        endpoint,
        "create_view_filters",
        {
            "view_filters": [
                {
                    "view_id": view.id,
                    "filters": [
                        {
                            "field_id": field.id,
                            "type": "date",
                            "operator": "equal",
                            "mode": "today",
                        }
                    ],
                }
            ]
        },
    )

    assert result.isError is False
    assert ViewFilter.objects.get(view=view).value == "Europe/Amsterdam??today"
